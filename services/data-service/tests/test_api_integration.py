"""
Live integration checks for data-service.

These tests are intentionally opt-in because they hit the running API and DB:
set RUN_LIVE_DATA_SERVICE_INTEGRATION=1 to enable.
"""
from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass
from datetime import date, datetime, timedelta

import pytest
import requests
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

from shared.models import Indicator, PriceData, Stock
from src.config import settings
from src.models import AlertHistory


BASE_URL = os.getenv("DATA_SERVICE_BASE_URL", "http://localhost:8000")
ENABLE_LIVE = os.getenv("RUN_LIVE_DATA_SERVICE_INTEGRATION", "").lower() in {"1", "true", "yes"}
pytestmark = pytest.mark.asyncio(scope="module")

TEST_ENGINE = create_async_engine(settings.DATABASE_URL, echo=False, poolclass=NullPool)
TestSessionLocal = sessionmaker(TEST_ENGINE, class_=AsyncSession, expire_on_commit=False)


@dataclass(frozen=True)
class PriceSnapshot:
    stock_id: int
    day: date
    open: float
    high: float
    low: float
    close: float
    volume: int
    adjusted_close: float
    created_at: datetime | None


def _require_live_enabled() -> None:
    if not ENABLE_LIVE:
        pytest.skip("Set RUN_LIVE_DATA_SERVICE_INTEGRATION=1 to run live data-service integration checks")


@pytest.fixture(scope="module", autouse=True)
async def _dispose_test_engine_on_module_exit():
    yield
    await TEST_ENGINE.dispose()


async def _latest_snapshot() -> PriceSnapshot | None:
    async with TestSessionLocal() as session:
        result = await session.execute(select(PriceData).order_by(PriceData.date.desc()).limit(1))
        row = result.scalars().first()
        if row is None:
            return None

        return PriceSnapshot(
            stock_id=row.stock_id,
            day=row.date,
            open=row.open,
            high=row.high,
            low=row.low,
            close=row.close,
            volume=row.volume,
            adjusted_close=row.adjusted_close,
            created_at=row.created_at,
        )


async def _row_exists(snapshot: PriceSnapshot) -> bool:
    async with TestSessionLocal() as session:
        result = await session.execute(
            select(func.count())
            .select_from(PriceData)
            .where(PriceData.stock_id == snapshot.stock_id, PriceData.date == snapshot.day)
        )
        return bool(result.scalar() or 0)


async def _delete_row(snapshot: PriceSnapshot) -> None:
    async with TestSessionLocal() as session:
        await session.execute(
            delete(PriceData).where(
                PriceData.stock_id == snapshot.stock_id,
                PriceData.date == snapshot.day,
            )
        )
        await session.commit()


async def _restore_row_if_missing(snapshot: PriceSnapshot) -> None:
    async with TestSessionLocal() as session:
        exists_result = await session.execute(
            select(func.count())
            .select_from(PriceData)
            .where(PriceData.stock_id == snapshot.stock_id, PriceData.date == snapshot.day)
        )
        exists = bool(exists_result.scalar() or 0)
        if exists:
            return

        session.add(
            PriceData(
                stock_id=snapshot.stock_id,
                date=snapshot.day,
                open=snapshot.open,
                high=snapshot.high,
                low=snapshot.low,
                close=snapshot.close,
                volume=snapshot.volume,
                adjusted_close=snapshot.adjusted_close,
                created_at=snapshot.created_at,
            )
        )
        await session.commit()


async def _any_stock_id() -> int | None:
    async with TestSessionLocal() as session:
        result = await session.execute(select(Stock.id).where(Stock.is_active == True).limit(1))
        value = result.scalar()
        return int(value) if value is not None else None


async def _insert_cleanup_probe_rows(
    stock_id: int,
    *,
    indicator_name: str,
    indicator_day: date,
    alert_type: str,
    alert_day: date,
) -> None:
    async with TestSessionLocal() as session:
        next_alert_id_result = await session.execute(
            select((func.coalesce(func.max(AlertHistory.id), 0) + 1))
        )
        next_alert_id = int(next_alert_id_result.scalar() or 1)

        session.add(
            Indicator(
                stock_id=stock_id,
                date=indicator_day,
                indicator_name=indicator_name,
                value=1.0,
            )
        )
        session.add(
            AlertHistory(
                id=next_alert_id,
                alert_config_id=None,
                stock_id=stock_id,
                triggered_at=datetime.utcnow() - timedelta(days=100),
                date=alert_day,
                condition_met="cleanup probe",
                crossover_type=alert_type,
                direction="neutral",
                price=1.0,
                indicator_values={"probe": True},
                notified=False,
            )
        )
        await session.commit()


async def _count_indicator_probe_rows(stock_id: int, *, indicator_name: str, indicator_day: date) -> int:
    async with TestSessionLocal() as session:
        result = await session.execute(
            select(func.count())
            .select_from(Indicator)
            .where(
                Indicator.stock_id == stock_id,
                Indicator.date == indicator_day,
                Indicator.indicator_name == indicator_name,
            )
        )
        return int(result.scalar() or 0)


async def _count_alert_probe_rows(stock_id: int, *, alert_type: str, alert_day: date) -> int:
    async with TestSessionLocal() as session:
        result = await session.execute(
            select(func.count())
            .select_from(AlertHistory)
            .where(
                AlertHistory.stock_id == stock_id,
                AlertHistory.date == alert_day,
                AlertHistory.crossover_type == alert_type,
            )
        )
        return int(result.scalar() or 0)


async def _delete_cleanup_probe_rows(
    stock_id: int,
    *,
    indicator_name: str,
    indicator_day: date,
    alert_type: str,
    alert_day: date,
) -> None:
    async with TestSessionLocal() as session:
        await session.execute(
            delete(Indicator).where(
                Indicator.stock_id == stock_id,
                Indicator.date == indicator_day,
                Indicator.indicator_name == indicator_name,
            )
        )
        await session.execute(
            delete(AlertHistory).where(
                AlertHistory.stock_id == stock_id,
                AlertHistory.date == alert_day,
                AlertHistory.crossover_type == alert_type,
            )
        )
        await session.commit()


async def test_daily_update_rehydrates_deleted_row_live():
    """
    Proves end-to-end behavior against a live dev stack:
    1) remove one real price_data row
    2) call /api/daily-update for that specific date
    3) assert row is restored (idempotent repair)
    """
    _require_live_enabled()

    try:
        health = await asyncio.to_thread(requests.get, f"{BASE_URL}/", timeout=10)
    except requests.RequestException as exc:
        pytest.skip(f"data-service not reachable at {BASE_URL}: {exc}")

    assert health.status_code == 200

    snapshot = await _latest_snapshot()
    if snapshot is None:
        pytest.skip("No existing price_data rows found; run a backfill first")

    try:
        await _delete_row(snapshot)
        assert await _row_exists(snapshot) is False

        response = await asyncio.to_thread(
            requests.post,
            f"{BASE_URL}/api/daily-update",
            json={"target_date": snapshot.day.isoformat(), "lookback_days": 0},
            timeout=900,
        )
        assert response.status_code == 200
        body = response.json()
        assert body.get("status") == "completed"

        assert await _row_exists(snapshot) is True
    finally:
        await _restore_row_if_missing(snapshot)


async def test_cleanup_prunes_old_indicator_and_alert_rows_live():
    """
    Proves end-to-end cleanup behavior against a live dev stack:
    1) insert old indicator + old alert-history probe rows
    2) call /api/cleanup
    3) verify probe rows are deleted by retention policy
    """
    _require_live_enabled()

    try:
        health = await asyncio.to_thread(requests.get, f"{BASE_URL}/", timeout=10)
    except requests.RequestException as exc:
        pytest.skip(f"data-service not reachable at {BASE_URL}: {exc}")

    assert health.status_code == 200

    stock_id = await _any_stock_id()
    if stock_id is None:
        pytest.skip("No active stock found; run watchlist population first")

    probe_suffix = datetime.utcnow().strftime("%Y%m%d%H%M%S%f")
    indicator_name = f"cleanup_probe_{probe_suffix}"
    alert_type = f"cp_{probe_suffix[-12:]}"
    indicator_day = date.today() - timedelta(days=800)  # older than 2-year indicator retention
    alert_day = date.today() - timedelta(days=100)  # older than 90-day alert retention

    await _insert_cleanup_probe_rows(
        stock_id,
        indicator_name=indicator_name,
        indicator_day=indicator_day,
        alert_type=alert_type,
        alert_day=alert_day,
    )

    try:
        assert await _count_indicator_probe_rows(
            stock_id, indicator_name=indicator_name, indicator_day=indicator_day
        ) == 1
        assert await _count_alert_probe_rows(stock_id, alert_type=alert_type, alert_day=alert_day) == 1

        response = await asyncio.to_thread(
            requests.post,
            f"{BASE_URL}/api/cleanup",
            timeout=300,
        )
        assert response.status_code == 200
        body = response.json()
        assert body.get("status") == "completed"
        assert int(body.get("indicators_deleted", 0)) >= 1
        assert int(body.get("alerts_deleted", 0)) >= 1

        assert await _count_indicator_probe_rows(
            stock_id, indicator_name=indicator_name, indicator_day=indicator_day
        ) == 0
        assert await _count_alert_probe_rows(stock_id, alert_type=alert_type, alert_day=alert_day) == 0
    finally:
        await _delete_cleanup_probe_rows(
            stock_id,
            indicator_name=indicator_name,
            indicator_day=indicator_day,
            alert_type=alert_type,
            alert_day=alert_day,
        )
