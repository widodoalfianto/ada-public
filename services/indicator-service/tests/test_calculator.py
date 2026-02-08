import pandas as pd
from src.calculator import IndicatorCalculator

def test_sma_calculation():
    data = pd.DataFrame({'close': [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]})
    sma = IndicatorCalculator.calculate_sma(data, period=5)
    # Expected SMA at index 4 (5th element): (1+2+3+4+5)/5 = 3.0
    assert sma.iloc[4] == 3.0
    # Expected SMA at index 5: (2+3+4+5+6)/5 = 4.0
    assert sma.iloc[5] == 4.0

def test_rsi_calculation():
    # Simple pattern: Up, Up, Up, Down, Down
    # Only need to check it returns values between 0 and 100
    data = pd.DataFrame({'close': range(100)})
    rsi = IndicatorCalculator.calculate_rsi(data, period=14)
    
    assert rsi.max() <= 100
    assert rsi.min() >= 0
    # RSI should be 100 for constantly increasing data
    assert rsi.iloc[-1] == 100

def test_bollinger_bands():
    data = pd.DataFrame({'close': [10, 10, 10, 10, 10]})
    upper, lower = IndicatorCalculator.calculate_bollinger_bands(data, period=5, std_dev=2)
    
    # Std dev of constant series is 0
    assert upper.iloc[-1] == 10.0
    assert lower.iloc[-1] == 10.0
