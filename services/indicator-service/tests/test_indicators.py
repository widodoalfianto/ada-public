import pandas as pd

from src.indicators import (
    calculate_all_indicators,
    calculate_bollinger_bands,
    calculate_rsi,
    calculate_sma,
)


def test_sma_calculation():
    series = pd.Series([1, 2, 3, 4, 5, 6, 7, 8, 9, 10])
    sma = calculate_sma(series, window=5)
    assert sma.iloc[4] == 3.0
    assert sma.iloc[5] == 4.0


def test_rsi_bounds():
    series = pd.Series(range(1, 101))
    rsi = calculate_rsi(series, window=14)
    valid = rsi.dropna()
    assert (valid >= 0).all()
    assert (valid <= 100).all()


def test_bollinger_bands_constant_series():
    series = pd.Series([10, 10, 10, 10, 10])
    bb = calculate_bollinger_bands(series, window=5, num_std=2)
    assert bb["bb_upper"].iloc[-1] == 10.0
    assert bb["bb_lower"].iloc[-1] == 10.0


def test_calculate_all_indicators_includes_expected_keys():
    df = pd.DataFrame(
        {
            "close": [100 + i for i in range(250)],
            "volume": [1_000_000 + i for i in range(250)],
        }
    )
    indicators = calculate_all_indicators(df)
    expected = {
        "sma_9",
        "sma_20",
        "sma_50",
        "sma_200",
        "sma_vol_20",
        "ema_9",
        "ema_12",
        "ema_20",
        "ema_26",
        "ema_50",
        "rsi_14",
        "macd_line",
        "macd_signal",
        "macd_hist",
        "bb_upper",
        "bb_middle",
        "bb_lower",
    }
    assert expected.issubset(set(indicators.keys()))
