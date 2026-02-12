from src.signal_detector import StrategySignal, _detect_cross, _signal_strength


def test_detect_cross_up():
    assert _detect_cross(101.0, 99.0, 100.0, 100.0, "cross_up")


def test_detect_cross_down():
    assert _detect_cross(99.0, 101.0, 100.0, 100.0, "cross_down")


def test_signal_strength_positive():
    assert _signal_strength(102.0, 100.0) == 2.0


def test_strategy_signal_properties():
    signal = StrategySignal(
        strategy_code="ESM",
        signal_type="entry",
        symbol="AAPL",
        stock_id=1,
        fast_indicator="ema_9",
        slow_indicator="sma_20",
        fast_value=101.0,
        slow_value=100.0,
        close_price=200.0,
        signal_strength=1.0,
    )
    assert signal.signal_code == "ESM_ENTRY"
    assert signal.direction == "bullish"
    assert signal.signal_type_key == "esm_entry"
    assert signal.condition_met == "ESM Entry"
