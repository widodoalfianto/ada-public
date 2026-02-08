import pandas as pd

class IndicatorCalculator:
    @staticmethod
    def calculate_sma(data: pd.DataFrame, period: int = 20) -> pd.Series:
        return data['close'].rolling(window=period).mean()

    @staticmethod
    def calculate_ema(data: pd.DataFrame, period: int = 20) -> pd.Series:
        return data['close'].ewm(span=period, adjust=False).mean()

    @staticmethod
    def calculate_rsi(data: pd.DataFrame, period: int = 14) -> pd.Series:
        delta = data['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        
        rs = gain / loss
        return 100 - (100 / (1 + rs))

    @staticmethod
    def calculate_macd(data: pd.DataFrame, slow=26, fast=12, signal=9):
        exp1 = data['close'].ewm(span=fast, adjust=False).mean()
        exp2 = data['close'].ewm(span=slow, adjust=False).mean()
        macd = exp1 - exp2
        signal_line = macd.ewm(span=signal, adjust=False).mean()
        return macd, signal_line

    @staticmethod
    def calculate_bollinger_bands(data: pd.DataFrame, period=20, std_dev=2):
        sma = data['close'].rolling(window=period).mean()
        std = data['close'].rolling(window=period).std()
        upper = sma + (std * std_dev)
        lower = sma - (std * std_dev)
        return upper, lower
