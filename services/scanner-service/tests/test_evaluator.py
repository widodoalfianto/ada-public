from src.evaluator import ConditionEvaluator

def test_sma_golden_cross():
    # Previous: EMA 9 (100) <= SMA 20 (105) -> EMA9 is below
    prev = {'indicators': {'ema_9': 100.0, 'sma_20': 105.0}, 'timestamp': '2024-01-01T00:00:00'}
    # Current: EMA 9 (106) > SMA 20 (104) -> EMA9 crossed above
    curr = {'indicators': {'ema_9': 106.0, 'sma_20': 104.0}, 'timestamp': '2024-01-02T00:00:00'}
    
    history = [curr, prev]
    alerts = ConditionEvaluator.evaluate(history)
    
    assert len(alerts) == 1
    assert alerts[0]['signal_code'] == "GOLDEN_CROSS"
    # Data contains specific values, not generic direction
    assert 'ema_9' in alerts[0]['data']
    assert 'sma_20' in alerts[0]['data']

def test_no_cross_still_below():
    prev = {'indicators': {'ema_9': 100.0, 'sma_20': 105.0}, 'timestamp': '2024-01-01T00:00:00'}
    curr = {'indicators': {'ema_9': 102.0, 'sma_20': 104.0}, 'timestamp': '2024-01-02T00:00:00'} # Still below
    
    history = [curr, prev]
    alerts = ConditionEvaluator.evaluate(history)
    assert len(alerts) == 0

def test_rsi_overbought_filtered():
    # RSI signals are intentionally filtered out
    curr = {'indicators': {'rsi_14': 75.0}, 'timestamp': '2024-01-01T00:00:00'}
    history = [curr]
    alerts = ConditionEvaluator.evaluate(history)
    assert len(alerts) == 0

def test_rsi_oversold_filtered():
    # RSI signals are intentionally filtered out
    curr = {'indicators': {'rsi_14': 25.0}, 'timestamp': '2024-01-01T00:00:00'}
    history = [curr]
    alerts = ConditionEvaluator.evaluate(history)
    assert len(alerts) == 0

def test_macd_bullish_filtered():
    # MACD signals are intentionally filtered out
    prev = {'indicators': {'macd_line': 0.5, 'macd_signal': 0.6}, 'timestamp': '2024-01-01T00:00:00'}
    curr = {'indicators': {'macd_line': 0.7, 'macd_signal': 0.65}, 'timestamp': '2024-01-02T00:00:00'}

    history = [curr, prev]
    alerts = ConditionEvaluator.evaluate(history)
    assert len(alerts) == 0

def test_volume_spike_filtered():
    # Volume spike signals are intentionally filtered out
    curr = {'volume': 2600, 'indicators': {'sma_vol_20': 1000.0}, 'timestamp': '2024-01-01T00:00:00'}
    history = [curr]
    alerts = ConditionEvaluator.evaluate(history)
    assert len(alerts) == 0
