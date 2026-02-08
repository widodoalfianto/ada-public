
import asyncio
import argparse
import sys
import os
from datetime import datetime
import pandas as pd
import yfinance as yf
from sqlalchemy import text

# Add parent dir to path to import src
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from src.database import init_db, AsyncSessionLocal

async def fetch_stock(symbol: str, days: int = 365):
    symbol = symbol.upper()
    print(f"🚀 Starting fetch for {symbol} ({days} days)...")
    
    # 1. Initialize DB
    await init_db()
    
    async with AsyncSessionLocal() as session:
        # 2. Ensure Stock Exists
        print(f"Checking/Creating stock record for {symbol}...")
        await session.execute(text("""
            INSERT INTO stocks (symbol, name, is_active) 
            VALUES (:symbol, :name, true) 
            ON CONFLICT (symbol) DO UPDATE SET is_active = true
        """), {"symbol": symbol, "name": symbol})  # Using symbol as name default
        await session.commit()
        
        # Get ID
        result = await session.execute(text("SELECT id FROM stocks WHERE symbol = :symbol"), {"symbol": symbol})
        stock_id = result.scalar()
        print(f"✅ Stock ID: {stock_id}")

    # 3. Fetch Data (yfinance)
    print(f"Fetching market data via yfinance...")
    ticker = yf.Ticker(symbol)
    no_data = False
    try:
        hist = ticker.history(period=f"{days}d") # yfinance interprets '365d' or similar
        # If 'days' is large, period='max' might be better, or just rely on '1y', '2y' etc formats.
        # But yfinance accepts '1d', '5d', '1mo', '3mo', '6mo', '1y', '2y', '5y', '10y', 'ytd', 'max'
        # Let's map days to period roughly or just use start/end dates if we want precision.
        # Using start date is safer.
        start_date = (datetime.now() - pd.Timedelta(days=days)).strftime('%Y-%m-%d')
        hist = ticker.history(start=start_date)
        
        if hist.empty:
            print("❌ No data found.")
            no_data = True
    except Exception as e:
        print(f"❌ Error fetching data: {e}")
        no_data = True
        
    if no_data:
        return

    print(f"✅ Fetched {len(hist)} candles.")

    # 4. Process & Store
    async with AsyncSessionLocal() as session:
        # Prepare Price Data
        prices_to_insert = []
        for date, row in hist.iterrows():
            prices_to_insert.append({
                "stock_id": stock_id,
                "date": date.date(),
                "open": float(row['Open']),
                "high": float(row['High']),
                "low": float(row['Low']),
                "close": float(row['Close']),
                "volume": int(row['Volume'])
            })

        print("Storing price data...")
        # Batch insert using executemany logic (or loop with single inserts for safety on upsert)
        # Using loop with ON CONFLICT for robustness
        for p in prices_to_insert:
            await session.execute(text("""
                INSERT INTO price_data (stock_id, date, open, high, low, close, volume)
                VALUES (:stock_id, :date, :open, :high, :low, :close, :volume)
                ON CONFLICT (stock_id, date) DO UPDATE SET
                    open = EXCLUDED.open,
                    high = EXCLUDED.high,
                    low = EXCLUDED.low,
                    close = EXCLUDED.close,
                    volume = EXCLUDED.volume
            """), p)
        
        # 5. Calculate Indicators
        print("Calculating indicators...")
        df = pd.DataFrame(prices_to_insert).sort_values('date')
        
        # SMAs
        df['sma_20'] = df['close'].rolling(window=20).mean()
        df['sma_50'] = df['close'].rolling(window=50).mean()
        df['sma_200'] = df['close'].rolling(window=200).mean()
        
        # EMA
        df['ema_9'] = df['close'].ewm(span=9, adjust=False).mean()
        
        # RSI 14
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df['rsi_14'] = 100 - (100 / (1 + rs))
        
        # MACD (12, 26, 9)
        exp12 = df['close'].ewm(span=12, adjust=False).mean()
        exp26 = df['close'].ewm(span=26, adjust=False).mean()
        macd = exp12 - exp26
        signal_line = macd.ewm(span=9, adjust=False).mean()
        df['macd'] = macd
        df['macd_signal'] = signal_line

        print("Storing indicators...")
        indicator_names = ['sma_20', 'sma_50', 'sma_200', 'ema_9', 'rsi_14', 'macd', 'macd_signal']
        
        for index, row in df.iterrows():
            d = row['date']
            for name in indicator_names:
                val = row.get(name)
                if pd.notna(val):
                    await session.execute(text("""
                        INSERT INTO indicators (stock_id, date, indicator_name, value)
                        VALUES (:id, :d, :name, :v)
                        ON CONFLICT (stock_id, date, indicator_name) DO UPDATE SET value = EXCLUDED.value
                    """), {"id": stock_id, "d": d, "name": name, "v": val})
        
        await session.commit()
        print(f"✨ Done! {symbol} is ready.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Fetch data for a single stock.')
    parser.add_argument('--symbol', required=True, help='Stock Symbol (e.g. AAPL)')
    parser.add_argument('--days', type=int, default=365, help='Days of history to fetch (default: 365)')
    
    args = parser.parse_args()
    
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        
    asyncio.run(fetch_stock(args.symbol, args.days))
