"""
Generic signal worker for scanner-service.

Executes enabled strategy definitions and emits alerts.
"""
from __future__ import annotations

from datetime import date, datetime
import logging

import httpx

from src.database import AsyncSessionLocal
from src.stock_filter import get_top_stocks_by_volume
from src.config import settings
from src.strategy_loader import load_strategy_definitions
from src.signal_detector import StrategySignal, scan_for_strategy_signals

logger = logging.getLogger(__name__)


class SignalWorker:
    def __init__(self):
        self._strategies = load_strategy_definitions()

    def refresh_strategies(self) -> None:
        self._strategies = load_strategy_definitions()

    @property
    def strategy_codes(self) -> list[str]:
        return sorted(self._strategies.keys())

    async def run_all(
        self,
        target_date: date | None = None,
        send_notifications: bool = True,
    ) -> None:
        self.refresh_strategies()
        for strategy in sorted(self._strategies.values(), key=lambda s: s.strategy_code):
            if not strategy.enabled:
                continue
            await self.run_strategy(
                strategy.strategy_code,
                target_date=target_date,
                send_notifications=send_notifications,
            )

    async def run_strategy(
        self,
        strategy_code: str,
        target_date: date | None = None,
        send_notifications: bool = True,
    ) -> None:
        self.refresh_strategies()
        strategy = self._strategies.get(strategy_code.upper())
        if not strategy:
            logger.error(f"Unknown strategy code: {strategy_code}")
            return
        if not strategy.enabled:
            logger.info(f"Strategy {strategy.strategy_code} is disabled; skipping.")
            return

        start = datetime.now()
        logger.info(f"[{start}] Starting {strategy.strategy_code} scan for {target_date or date.today()}...")

        try:
            async with AsyncSessionLocal() as session:
                stocks = await get_top_stocks_by_volume(
                    session,
                    limit=strategy.filters.top_n,
                    min_price=strategy.filters.min_price,
                )
                if not stocks:
                    logger.warning(f"No stocks matched filters for strategy {strategy.strategy_code}.")
                    return

                signals = await scan_for_strategy_signals(
                    session,
                    stocks,
                    strategy,
                    target_date=target_date,
                )
                logger.info(f"{strategy.strategy_code}: found {len(signals)} signals.")

                if signals:
                    async with httpx.AsyncClient(timeout=10.0) as client:
                        for signal in signals:
                            await self._process_signal(
                                signal,
                                client,
                                target_date=target_date,
                                send_notifications=send_notifications,
                            )
        except Exception as e:
            logger.error(f"{strategy.strategy_code} scan failed: {e}", exc_info=True)
        finally:
            duration = (datetime.now() - start).total_seconds()
            logger.info(f"{strategy.strategy_code} scan finished in {duration:.2f}s")

    async def _process_signal(
        self,
        signal: StrategySignal,
        client: httpx.AsyncClient,
        target_date: date | None = None,
        send_notifications: bool = True,
    ) -> None:
        try:
            signal_date = target_date.isoformat() if target_date else date.today().isoformat()
            rounded_fast = round(signal.fast_value, 2) if signal.fast_value is not None else None
            rounded_slow = round(signal.slow_value, 2) if signal.slow_value is not None else None

            indicator_values = {
                signal.fast_indicator: rounded_fast,
                signal.slow_indicator: rounded_slow,
                "strength": round(signal.signal_strength, 2),
            }
            # Keep legacy keys for chart overlays/formatters that expect EMA/SMA names.
            if signal.fast_indicator == "ema_9":
                indicator_values["ema_9"] = rounded_fast
            if signal.slow_indicator == "sma_20":
                indicator_values["sma_20"] = rounded_slow

            record_payload = {
                "stock_symbol": signal.symbol,
                "triggered_at": datetime.utcnow().isoformat(),
                "date": signal_date,
                "condition_met": signal.condition_met,
                "crossover_type": signal.signal_type_key,
                "direction": signal.direction,
                "price": float(signal.close_price) if signal.close_price is not None else 0.0,
                "indicator_values": indicator_values,
            }

            record_resp = await client.post(f"{settings.DATA_SERVICE_URL}/api/record-alert", json=record_payload)
            record_data = record_resp.json() if record_resp.status_code == 200 else {}
            if record_resp.status_code != 200:
                logger.error(f"Failed to record {signal.signal_code} for {signal.symbol}: {record_resp.text}")
                return
            if record_data.get("status") != "success":
                logger.info(
                    f"Skipping notify for {signal.symbol} ({signal.signal_code}): "
                    f"{record_data.get('message', 'record skipped')}"
                )
                return

            if not send_notifications:
                logger.info(f"Recorded {signal.signal_code} for {signal.symbol} with notifications disabled.")
                return

            notify_payload = {
                "signal_code": signal.signal_code,
                "symbol": signal.symbol,
                "timestamp": int(datetime.now().timestamp()),
                "data": {
                    "price": signal.close_price,
                    signal.fast_indicator: rounded_fast,
                    signal.slow_indicator: rounded_slow,
                    "pct_diff": f"{signal.signal_strength:+.2f}%",
                },
            }

            notify_resp = await client.post(f"{settings.ALERT_SERVICE_URL}/signal", json=notify_payload)
            if notify_resp.status_code != 200:
                logger.error(f"Failed to notify {signal.signal_code} for {signal.symbol}: {notify_resp.text}")
        except Exception as e:
            logger.error(f"Error processing {signal.signal_code} for {signal.symbol}: {e}")
