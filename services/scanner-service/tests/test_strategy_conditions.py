from src.signal_detector import _conditions_match
from src.strategy_loader import ConditionRule, load_strategy_definitions


def _pf_conditions():
    return [
        ConditionRule(
            indicator="ma_cross",
            comparison="cross_up",
            params={"fast_period": 9, "slow_period": 20},
        ),
        ConditionRule(
            indicator="rsi",
            comparison=">",
            params={"period": 14, "threshold": 50},
        ),
        ConditionRule(
            indicator="volume",
            comparison=">",
            params={"multiplier": 1.2},
        ),
        ConditionRule(
            indicator="price_vs_sma",
            comparison=">",
            params={"sma_period": 50},
        ),
    ]


def test_pf_entry_condition_set_passes():
    curr_indicators = {
        "ema_9": 101.0,
        "sma_20": 100.0,
        "rsi_14": 55.0,
        "sma_vol_20": 1000.0,
        "sma_50": 98.0,
    }
    prev_indicators = {"ema_9": 99.0, "sma_20": 100.0}
    curr_price = {"close": 102.0, "volume": 1300.0}

    assert _conditions_match(_pf_conditions(), curr_indicators, prev_indicators, curr_price)


def test_pf_entry_condition_set_fails_when_volume_missing_threshold():
    curr_indicators = {
        "ema_9": 101.0,
        "sma_20": 100.0,
        "rsi_14": 55.0,
        "sma_vol_20": 1000.0,
        "sma_50": 98.0,
    }
    prev_indicators = {"ema_9": 99.0, "sma_20": 100.0}
    curr_price = {"close": 102.0, "volume": 1100.0}

    assert not _conditions_match(_pf_conditions(), curr_indicators, prev_indicators, curr_price)


def test_strategy_files_have_expected_entry_condition_counts():
    strategies = load_strategy_definitions()
    assert len(strategies["ESM"].scan.entry_conditions) == 0
    assert len(strategies["PF"].scan.entry_conditions) == 4
