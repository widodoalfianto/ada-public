from __future__ import annotations

from datetime import date, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.exc import IntegrityError

from src import main as data_main


class _ResultScalar:
    def __init__(self, value):
        self._value = value

    def scalar(self):
        return self._value


class _ResultRows:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows


class _FakeSession:
    def __init__(
        self,
        *,
        stock_id=1,
        rows=None,
        commit_error: Exception | None = None,
        execute_error: Exception | None = None,
    ):
        self.stock_id = stock_id
        self.rows = rows or []
        self.commit_error = commit_error
        self.execute_error = execute_error
        self.added = []
        self.rollback_called = False

    async def execute(self, _stmt):
        if self.execute_error:
            raise self.execute_error

        if self.rows:
            return _ResultRows(self.rows)

        return _ResultScalar(self.stock_id)

    def add(self, obj):
        self.added.append(obj)

    async def commit(self):
        if self.commit_error:
            raise self.commit_error

    async def rollback(self):
        self.rollback_called = True

    async def refresh(self, obj):
        if getattr(obj, "id", None) is None:
            obj.id = 99


class _SessionFactory:
    def __init__(self, session: _FakeSession):
        self._session = session

    def __call__(self):
        return self

    async def __aenter__(self):
        return self._session

    async def __aexit__(self, exc_type, exc, tb):
        return False


@pytest.mark.asyncio
async def test_root():
    result = await data_main.root()
    assert result == {"message": "Data Service is running"}


@pytest.mark.asyncio
async def test_daily_update_success(monkeypatch):
    fetch = AsyncMock(return_value={"status": "completed", "success_count": 3})
    monkeypatch.setattr(data_main, "fetch_daily_prices", fetch)

    payload = data_main.DatePayload(target_date=date(2026, 2, 10), lookback_days=2)
    result = await data_main.daily_update(payload)

    assert result["status"] == "completed"
    fetch.assert_awaited_once_with(target_date=date(2026, 2, 10), lookback_days=2)


@pytest.mark.asyncio
async def test_daily_update_failure(monkeypatch):
    fetch = AsyncMock(side_effect=RuntimeError("upstream outage"))
    monkeypatch.setattr(data_main, "fetch_daily_prices", fetch)

    result = await data_main.daily_update()

    assert result["status"] == "failed"
    assert "upstream outage" in result["error"]
    assert "timestamp" in result


@pytest.mark.asyncio
async def test_cleanup_success(monkeypatch):
    prune = AsyncMock(return_value={"status": "completed", "indicators_deleted": 10})
    monkeypatch.setattr(data_main, "prune_old_data", prune)

    result = await data_main.run_cleanup()

    assert result["status"] == "completed"
    prune.assert_awaited_once()


@pytest.mark.asyncio
async def test_cleanup_failure(monkeypatch):
    prune = AsyncMock(side_effect=RuntimeError("cleanup failed"))
    monkeypatch.setattr(data_main, "prune_old_data", prune)

    result = await data_main.run_cleanup()

    assert result["status"] == "failed"
    assert "cleanup failed" in result["error"]
    assert "timestamp" in result


@pytest.mark.asyncio
async def test_record_alert_skips_duplicate(monkeypatch):
    session = _FakeSession(
        stock_id=10,
        commit_error=IntegrityError("insert", {}, Exception("duplicate")),
    )
    monkeypatch.setattr(data_main, "AsyncSessionLocal", _SessionFactory(session))

    payload = data_main.AlertCreate(
        stock_symbol="AAPL",
        alert_config_id=None,
        triggered_at=datetime(2026, 2, 10, 16, 30),
        date=date(2026, 2, 10),
        condition_met="ESM Entry",
        crossover_type="esm_entry",
        direction="bullish",
        price=200.5,
        indicator_values={"ema_9": 200.0, "sma_20": 199.8},
    )

    result = await data_main.record_alert(payload)

    assert result == {"status": "skipped", "message": "Duplicate alert"}
    assert session.rollback_called is True


@pytest.mark.asyncio
async def test_record_alert_success_defaults_type(monkeypatch):
    session = _FakeSession(stock_id=42)
    monkeypatch.setattr(data_main, "AsyncSessionLocal", _SessionFactory(session))

    payload = data_main.AlertCreate(
        stock_symbol="MSFT",
        alert_config_id=None,
        triggered_at=datetime(2026, 2, 10, 16, 30),
        date=date(2026, 2, 10),
        condition_met="PF Exit",
        crossover_type=None,
        direction="bearish",
        price=410.0,
        indicator_values={"ema_9": 412.0, "sma_20": 414.0},
    )

    result = await data_main.record_alert(payload)

    assert result == {"status": "success", "id": 99}
    assert len(session.added) == 1
    assert session.added[0].crossover_type == "unknown"


@pytest.mark.asyncio
async def test_get_alert_history_success(monkeypatch):
    history = SimpleNamespace(
        crossover_type="esm_entry",
        direction="bullish",
        price=123.45,
        condition_met="ESM Entry",
        indicator_values={"ema_9": 123.0},
        triggered_at=datetime(2026, 2, 10, 16, 30),
    )
    rows = [(history, "AAPL")]
    session = _FakeSession(rows=rows)
    monkeypatch.setattr(data_main, "AsyncSessionLocal", _SessionFactory(session))

    result = await data_main.get_alert_history(target_date=date(2026, 2, 10))

    assert result["status"] == "success"
    assert len(result["alerts"]) == 1
    assert result["alerts"][0]["symbol"] == "AAPL"
    assert result["alerts"][0]["crossover_type"] == "esm_entry"


@pytest.mark.asyncio
async def test_get_alert_history_failure(monkeypatch):
    session = _FakeSession(execute_error=RuntimeError("db unavailable"))
    monkeypatch.setattr(data_main, "AsyncSessionLocal", _SessionFactory(session))

    result = await data_main.get_alert_history(target_date=date(2026, 2, 10))

    assert result["status"] == "error"
    assert "db unavailable" in result["message"]
