"""
Generic signal detector for scanner-service.

Evaluates strategy rules from strategy JSON definitions and produces
strategy-scoped entry/exit signals.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any, List, Optional, Sequence
import logging

from sqlalchemy import desc, select
from shared.models import Indicator, PriceData
from src.strategy_loader import ConditionRule, StrategyDefinition

logger = logging.getLogger(__name__)


@dataclass
class StrategySignal:
    strategy_code: str
    signal_type: str  # entry | exit
    symbol: str
    stock_id: int
    fast_indicator: str
    slow_indicator: str
    fast_value: Optional[float]
    slow_value: Optional[float]
    close_price: float
    signal_strength: float

    @property
    def signal_code(self) -> str:
        return f"{self.strategy_code}_{self.signal_type.upper()}"

    @property
    def direction(self) -> str:
        return "bullish" if self.signal_type == "entry" else "bearish"

    @property
    def signal_type_key(self) -> str:
        return f"{self.strategy_code.lower()}_{self.signal_type}"

    @property
    def condition_met(self) -> str:
        return f"{self.strategy_code} {self.signal_type.capitalize()}"


def _detect_cross(
    fast_today: Optional[float],
    fast_prev: Optional[float],
    slow_today: Optional[float],
    slow_prev: Optional[float],
    comparison: str,
) -> bool:
    if any(v is None for v in (fast_today, fast_prev, slow_today, slow_prev)):
        return False

    if comparison == "cross_up":
        return fast_prev <= slow_prev and fast_today > slow_today
    if comparison == "cross_down":
        return fast_prev >= slow_prev and fast_today < slow_today
    return False


def _signal_strength(fast_value: Optional[float], slow_value: Optional[float]) -> float:
    if fast_value is None or slow_value in (None, 0):
        return 0.0
    return ((fast_value - slow_value) / slow_value) * 100


def _indicator_names_for_condition(condition: ConditionRule) -> set[str]:
    indicator = condition.indicator.lower()
    params = condition.params or {}

    if indicator == "ma_cross":
        fast_period = int(params.get("fast_period", 9))
        slow_period = int(params.get("slow_period", 20))
        return {f"ema_{fast_period}", f"sma_{slow_period}"}
    if indicator == "rsi":
        period = int(params.get("period", 14))
        return {f"rsi_{period}"}
    if indicator == "price_vs_sma":
        sma_period = int(params.get("sma_period", 50))
        return {f"sma_{sma_period}"}
    if indicator == "volume":
        window = int(params.get("window", 20))
        return {f"sma_vol_{window}"}

    return set()


def _evaluate_condition(
    condition: ConditionRule,
    curr_indicators: dict[str, Any],
    prev_indicators: dict[str, Any],
    curr_price: dict[str, Any],
) -> bool:
    indicator = condition.indicator.lower()
    comparison = condition.comparison
    params = condition.params or {}

    if indicator == "ma_cross":
        fast_period = int(params.get("fast_period", 9))
        slow_period = int(params.get("slow_period", 20))
        fast_name = f"ema_{fast_period}"
        slow_name = f"sma_{slow_period}"
        return _detect_cross(
            curr_indicators.get(fast_name),
            prev_indicators.get(fast_name),
            curr_indicators.get(slow_name),
            prev_indicators.get(slow_name),
            comparison,
        )

    if indicator == "rsi":
        period = int(params.get("period", 14))
        rsi_name = f"rsi_{period}"
        rsi_value = curr_indicators.get(rsi_name)
        if rsi_value is None:
            return False

        if comparison == ">":
            return rsi_value > float(params.get("threshold", 50))
        if comparison == "<":
            return rsi_value < float(params.get("threshold", 50))
        if comparison == "between":
            low = float(params.get("min", 30))
            high = float(params.get("max", 70))
            return low <= rsi_value <= high
        return False

    if indicator == "volume":
        volume_value = curr_price.get("volume")
        if volume_value is None:
            return False

        if "threshold" in params:
            threshold = float(params.get("threshold"))
            if comparison == ">":
                return volume_value > threshold
            if comparison == "<":
                return volume_value < threshold
            return False

        window = int(params.get("window", 20))
        sma_vol_name = f"sma_vol_{window}"
        sma_vol_value = curr_indicators.get(sma_vol_name)
        if sma_vol_value is None:
            return False

        multiplier = float(params.get("multiplier", 1.0))
        threshold = sma_vol_value * multiplier
        if comparison == ">":
            return volume_value > threshold
        if comparison == "<":
            return volume_value < threshold
        return False

    if indicator == "price_vs_sma":
        close_price = curr_price.get("close")
        sma_period = int(params.get("sma_period", 50))
        sma_value = curr_indicators.get(f"sma_{sma_period}")
        if close_price is None or sma_value is None:
            return False
        if comparison == ">":
            return close_price > sma_value
        if comparison == "<":
            return close_price < sma_value
        return False

    return False


def _conditions_match(
    conditions: Sequence[ConditionRule],
    curr_indicators: dict[str, Any],
    prev_indicators: dict[str, Any],
    curr_price: dict[str, Any],
) -> bool:
    for condition in conditions:
        if not _evaluate_condition(condition, curr_indicators, prev_indicators, curr_price):
            return False
    return True


def _resolve_close_price(
    by_date: dict[date, dict[str, Any]],
    curr_date: date,
) -> float:
    current = by_date.get(curr_date, {})
    close = current.get("close")
    if close is not None:
        return float(close)

    for dt in sorted(by_date.keys(), reverse=True):
        fallback = by_date[dt].get("close")
        if fallback is not None:
            return float(fallback)

    return 0.0


async def scan_for_strategy_signals(
    session,
    stocks: list,
    strategy: StrategyDefinition,
    target_date: date | None = None,
) -> List[StrategySignal]:
    if not stocks:
        return []

    stock_ids = [s.id for s in stocks]
    stock_map = {s.id: s for s in stocks}
    signals: List[StrategySignal] = []

    today = target_date if target_date else date.today()
    start_date = today - timedelta(days=7)

    entry = strategy.scan.entry
    exit_rule = strategy.scan.exit
    needed_indicators = {
        entry.fast_indicator,
        entry.slow_indicator,
        exit_rule.fast_indicator,
        exit_rule.slow_indicator,
    }
    for condition in strategy.scan.entry_conditions:
        needed_indicators.update(_indicator_names_for_condition(condition))
    for condition in strategy.scan.exit_conditions:
        needed_indicators.update(_indicator_names_for_condition(condition))

    try:
        ind_query = (
            select(Indicator.stock_id, Indicator.date, Indicator.indicator_name, Indicator.value)
            .where(Indicator.stock_id.in_(stock_ids))
            .where(Indicator.indicator_name.in_(sorted(needed_indicators)))
            .where(Indicator.date >= start_date)
            .where(Indicator.date <= today)
            .order_by(Indicator.stock_id, desc(Indicator.date))
        )
        ind_rows = (await session.execute(ind_query)).all()

        indicator_map: dict[int, dict[date, dict[str, Any]]] = {}
        for stock_id, dt, name, value in ind_rows:
            indicator_map.setdefault(stock_id, {}).setdefault(dt, {})[name] = value

        price_query = (
            select(PriceData.stock_id, PriceData.date, PriceData.close, PriceData.volume)
            .where(PriceData.stock_id.in_(stock_ids))
            .where(PriceData.date >= start_date)
            .where(PriceData.date <= today)
            .order_by(PriceData.stock_id, desc(PriceData.date))
        )
        price_rows = (await session.execute(price_query)).all()

        price_map: dict[int, dict[date, dict[str, Any]]] = {}
        for stock_id, dt, close, volume in price_rows:
            price_map.setdefault(stock_id, {})[dt] = {
                "close": close,
                "volume": float(volume) if volume is not None else None,
            }

        for stock_id, by_date in indicator_map.items():
            stock = stock_map.get(stock_id)
            if not stock:
                continue

            dates = sorted(by_date.keys(), reverse=True)
            if len(dates) < 2:
                continue

            curr_date = dates[0]
            prev_date = dates[1]
            curr = by_date[curr_date]
            prev = by_date[prev_date]
            curr_price = price_map.get(stock_id, {}).get(curr_date, {})

            entry_hit = _detect_cross(
                curr.get(entry.fast_indicator),
                prev.get(entry.fast_indicator),
                curr.get(entry.slow_indicator),
                prev.get(entry.slow_indicator),
                entry.comparison,
            )
            if strategy.scan.entry_conditions:
                entry_hit = _conditions_match(strategy.scan.entry_conditions, curr, prev, curr_price)

            exit_hit = _detect_cross(
                curr.get(exit_rule.fast_indicator),
                prev.get(exit_rule.fast_indicator),
                curr.get(exit_rule.slow_indicator),
                prev.get(exit_rule.slow_indicator),
                exit_rule.comparison,
            )
            if strategy.scan.exit_conditions:
                exit_hit = _conditions_match(strategy.scan.exit_conditions, curr, prev, curr_price)

            if entry_hit:
                fast_val = curr.get(entry.fast_indicator)
                slow_val = curr.get(entry.slow_indicator)
                signals.append(
                    StrategySignal(
                        strategy_code=strategy.strategy_code,
                        signal_type="entry",
                        symbol=stock.symbol,
                        stock_id=stock.id,
                        fast_indicator=entry.fast_indicator,
                        slow_indicator=entry.slow_indicator,
                        fast_value=fast_val,
                        slow_value=slow_val,
                        close_price=_resolve_close_price(price_map.get(stock_id, {}), curr_date),
                        signal_strength=_signal_strength(fast_val, slow_val),
                    )
                )

            if exit_hit:
                fast_val = curr.get(exit_rule.fast_indicator)
                slow_val = curr.get(exit_rule.slow_indicator)
                signals.append(
                    StrategySignal(
                        strategy_code=strategy.strategy_code,
                        signal_type="exit",
                        symbol=stock.symbol,
                        stock_id=stock.id,
                        fast_indicator=exit_rule.fast_indicator,
                        slow_indicator=exit_rule.slow_indicator,
                        fast_value=fast_val,
                        slow_value=slow_val,
                        close_price=_resolve_close_price(price_map.get(stock_id, {}), curr_date),
                        signal_strength=_signal_strength(fast_val, slow_val),
                    )
                )

    except Exception as e:
        logger.error(f"Error during strategy scan ({strategy.strategy_code}): {e}", exc_info=True)

    return signals
