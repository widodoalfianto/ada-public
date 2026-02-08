import asyncio
import sys
import pandas as pd
import requests
from io import StringIO
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from src.config import settings
from src.models import Stock

# Database setup
engine = create_async_engine(settings.DATABASE_URL, echo=False)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

def fetch_sp500():
    print("Fetching S&P 500 list from Wikipedia...")
    url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    try:
        resp = requests.get(url, headers=headers)
        if resp.status_code != 200:
            print(f"Failed to fetch content: {resp.status_code}")
            return []
            
        tables = pd.read_html(StringIO(resp.text))
        df_sp500 = tables[0]
        # Ticker column 'Symbol'
        symbols = df_sp500['Symbol'].tolist()
        
        # Clean symbols (e.g. BRK.B -> BRK-B)
        cleaned_symbols = [s.replace('.', '-') for s in symbols]
        
        print(f"Found {len(cleaned_symbols)} stocks in S&P 500.")
        return cleaned_symbols
    except Exception as e:
        print(f"Error fetching S&P 500: {e}")
        return []

async def update_stocks():
    print("Connecting to database...")
    async with AsyncSessionLocal() as session:
        # 1. Fetch current S&P 500 list
        sp500_symbols = fetch_sp500()
        if not sp500_symbols:
            print("Aborting update due to fetch failure.")
            return

        print(f"Processing {len(sp500_symbols)} symbols...")
        
        # 2. Get all existing stocks in DB
        result = await session.execute(select(Stock))
        existing_stocks = result.scalars().all()
        # Map symbol -> Stock object
        existing_map = {s.symbol: s for s in existing_stocks}
        
        # 3. Upsert S&P 500 stocks (Activate)
        added_count = 0
        updated_count = 0
        active_symbols = set(sp500_symbols)
        
        for symbol in sp500_symbols:
            if symbol in existing_map:
                stock = existing_map[symbol]
                # If currently inactive, reactivate it
                if not stock.is_active:
                    stock.is_active = True
                    updated_count += 1
            else:
                # Add new
                new_stock = Stock(symbol=symbol, is_active=True, exchange="US", name="S&P 500 Member")
                session.add(new_stock)
                added_count += 1
        
        # 4. Deactivate stocks NOT in S&P 500
        deactivated_count = 0
        for stock in existing_stocks:
            if stock.symbol not in active_symbols and stock.is_active:
                stock.is_active = False
                deactivated_count += 1
                
        await session.commit()
        print("-" * 40)
        print(f"Update Summary:")
        print(f"  New Stocks Added: {added_count}")
        print(f"  Reactivated:      {updated_count}")
        print(f"  Deactivated:      {deactivated_count}")
        print(f"  Total Active:     {len(active_symbols)}")
        print("-" * 40)

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(update_stocks())
