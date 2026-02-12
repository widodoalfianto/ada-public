"""
Strategy loader for scanner-service.

Loads scanner strategy definitions from JSON files so signal generation
behavior can be changed without code edits.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Tuple
import json


@dataclass(frozen=True)
class CrossRule:
    comparison: str
    fast_indicator: str
    slow_indicator: str


@dataclass(frozen=True)
class ConditionRule:
    indicator: str
    comparison: str
    params: Dict[str, Any]


@dataclass(frozen=True)
class ScanConfig:
    type: str
    entry: CrossRule
    exit: CrossRule
    entry_conditions: Tuple[ConditionRule, ...] = ()
    exit_conditions: Tuple[ConditionRule, ...] = ()


@dataclass(frozen=True)
class FilterConfig:
    top_n: int = 100
    min_price: float = 10.0


@dataclass(frozen=True)
class StrategyDefinition:
    strategy_code: str
    enabled: bool
    scan: ScanConfig
    filters: FilterConfig


def _validate_rule(rule: CrossRule, context: str) -> None:
    if rule.comparison not in {"cross_up", "cross_down"}:
        raise ValueError(f"{context}: unsupported comparison '{rule.comparison}'")
    if not rule.fast_indicator or not rule.slow_indicator:
        raise ValueError(f"{context}: fast_indicator and slow_indicator are required")


def _validate_condition(rule: ConditionRule, context: str) -> None:
    indicator = rule.indicator.lower()
    comparison = rule.comparison

    if indicator == "ma_cross":
        if comparison not in {"cross_up", "cross_down"}:
            raise ValueError(f"{context}: ma_cross only supports cross_up/cross_down")
        return
    if indicator == "rsi":
        if comparison not in {"<", ">", "between"}:
            raise ValueError(f"{context}: rsi only supports <, >, between")
        return
    if indicator == "volume":
        if comparison not in {"<", ">"}:
            raise ValueError(f"{context}: volume only supports <, >")
        return
    if indicator == "price_vs_sma":
        if comparison not in {"<", ">"}:
            raise ValueError(f"{context}: price_vs_sma only supports <, >")
        return

    raise ValueError(f"{context}: unsupported indicator '{rule.indicator}'")


def _parse_conditions(raw: list, context: str) -> Tuple[ConditionRule, ...]:
    parsed: list[ConditionRule] = []
    for idx, cond_raw in enumerate(raw or []):
        if not isinstance(cond_raw, dict):
            raise ValueError(f"{context}[{idx}]: condition must be an object")
        cond = ConditionRule(
            indicator=str(cond_raw.get("indicator", "")).strip(),
            comparison=str(cond_raw.get("comparison", "")).strip(),
            params=dict(cond_raw.get("params", {}) or {}),
        )
        if not cond.indicator or not cond.comparison:
            raise ValueError(f"{context}[{idx}]: indicator and comparison are required")
        _validate_condition(cond, f"{context}[{idx}]")
        parsed.append(cond)
    return tuple(parsed)


def _parse_strategy(raw: dict, filename: str) -> StrategyDefinition:
    strategy_code = str(raw.get("strategy_code", "")).upper().strip()
    if not strategy_code:
        raise ValueError(f"{filename}: missing strategy_code")

    enabled = bool(raw.get("enabled", True))
    scan_raw = raw.get("scan", {}) or {}
    if scan_raw.get("type") != "ma_cross":
        raise ValueError(f"{filename}: scan.type must be 'ma_cross'")

    entry_raw = scan_raw.get("entry", {}) or {}
    exit_raw = scan_raw.get("exit", {}) or {}

    entry = CrossRule(
        comparison=str(entry_raw.get("comparison", "")),
        fast_indicator=str(entry_raw.get("fast_indicator", "")),
        slow_indicator=str(entry_raw.get("slow_indicator", "")),
    )
    exit_rule = CrossRule(
        comparison=str(exit_raw.get("comparison", "")),
        fast_indicator=str(exit_raw.get("fast_indicator", "")),
        slow_indicator=str(exit_raw.get("slow_indicator", "")),
    )
    _validate_rule(entry, f"{filename} entry")
    _validate_rule(exit_rule, f"{filename} exit")
    entry_conditions = _parse_conditions(scan_raw.get("entry_conditions", []) or [], f"{filename} entry_conditions")
    exit_conditions = _parse_conditions(scan_raw.get("exit_conditions", []) or [], f"{filename} exit_conditions")

    filters_raw = raw.get("filters", {}) or {}
    filters = FilterConfig(
        top_n=int(filters_raw.get("top_n", 100)),
        min_price=float(filters_raw.get("min_price", 10.0)),
    )

    return StrategyDefinition(
        strategy_code=strategy_code,
        enabled=enabled,
        scan=ScanConfig(
            type="ma_cross",
            entry=entry,
            exit=exit_rule,
            entry_conditions=entry_conditions,
            exit_conditions=exit_conditions,
        ),
        filters=filters,
    )


def load_strategy_definitions(strategy_dir: Path | None = None) -> Dict[str, StrategyDefinition]:
    if strategy_dir is None:
        strategy_dir = Path(__file__).resolve().parent.parent / "strategies"

    if not strategy_dir.exists():
        raise FileNotFoundError(f"Strategy directory not found: {strategy_dir}")

    definitions: Dict[str, StrategyDefinition] = {}
    for path in sorted(strategy_dir.glob("*.json")):
        with path.open("r", encoding="utf-8") as f:
            raw = json.load(f)
        parsed = _parse_strategy(raw, path.name)
        definitions[parsed.strategy_code] = parsed

    return definitions
