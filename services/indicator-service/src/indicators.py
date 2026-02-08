import pandas as pd

def calculate_sma(series: pd.Series, window: int) -> pd.Series:
    """Calculate Simple Moving Average"""
    return series.rolling(window=window).mean()

def calculate_ema(series: pd.Series, span: int) -> pd.Series:
    """Calculate Exponential Moving Average"""
    return series.ewm(span=span, adjust=False).mean()

def calculate_rsi(series: pd.Series, window: int = 14) -> pd.Series:
    """Calculate Relative Strength Index"""
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=window).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
    
    # Use exponential moving average for RSI smoothing (Wilder's smoothing) yields slightly different results
    # Standard RSI often uses EMA for gain/loss smoothing. 
    # Let's use pure Wilder's smoothing if we want exact match, or standard EMA.
    # For simplicity and standard implementations, EMA of gains/losses is common.
    
    # Re-implementing with EMA for gains/losses for standard smoothing
    gain = delta.where(delta > 0, 0).ewm(alpha=1/window, adjust=False).mean()
    loss = (-delta.where(delta < 0, 0)).ewm(alpha=1/window, adjust=False).mean()

    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

def calculate_macd(series: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.DataFrame:
    """Calculate MACD, Signal, and Histogram"""
    exp1 = calculate_ema(series, fast)
    exp2 = calculate_ema(series, slow)
    macd_line = exp1 - exp2
    signal_line = calculate_ema(macd_line, signal)
    histogram = macd_line - signal_line
    return pd.DataFrame({
        'macd': macd_line,
        'signal': signal_line,
        'histogram': histogram
    })

def calculate_bollinger_bands(series: pd.Series, window: int = 20, num_std: int = 2) -> pd.DataFrame:
    """Calculate Bollinger Bands (Upper, Middle, Lower)"""
    middle = calculate_sma(series, window)
    std = series.rolling(window=window).std()
    upper = middle + (std * num_std)
    lower = middle - (std * num_std)
    return pd.DataFrame({
        'bb_upper': upper,
        'bb_middle': middle,
        'bb_lower': lower
    })

def calculate_all_indicators(df: pd.DataFrame) -> dict:
    """
    Calculate all indicators for a dataframe containing a 'close' column.
    Returns a dictionary of {indicator_name: series/value}
    """
    if 'close' not in df.columns:
        raise ValueError("DataFrame must contain 'close' column")
    
    close = df['close']
    results = {}
    
    # SMAs
    for window in [9, 20, 50, 200]:
        results[f'sma_{window}'] = calculate_sma(close, window)
        
    # Volume SMA
    if 'volume' in df.columns:
        results['sma_vol_20'] = calculate_sma(df['volume'], 20)
        
    # EMAs
    for span in [9, 12, 20, 26, 50]:
        results[f'ema_{span}'] = calculate_ema(close, span)
        
    # RSI
    results['rsi_14'] = calculate_rsi(close, 14)
    
    # MACD
    macd_df = calculate_macd(close)
    results['macd_line'] = macd_df['macd']
    results['macd_signal'] = macd_df['signal']
    results['macd_hist'] = macd_df['histogram']
    
    # Bollinger Bands
    bb_df = calculate_bollinger_bands(close)
    results['bb_upper'] = bb_df['bb_upper']
    results['bb_middle'] = bb_df['bb_middle']
    results['bb_lower'] = bb_df['bb_lower']
    
    return results
