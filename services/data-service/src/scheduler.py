import asyncio
from sqlalchemy import select
from src.database import AsyncSessionLocal
from src.models import Stock, PriceData
from src.finnhub_client import FinnhubClient
from datetime import datetime

class DataScheduler:
    def __init__(self):
        self.client = FinnhubClient()

    async def fetch_and_store_quotes(self):
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(Stock).where(Stock.is_active == True))
            stocks = result.scalars().all()
            
            for stock in stocks:
                try:
                    quote = await self.client.get_quote(stock.symbol)
                    # Maps Finnhub Quote to PriceData
                    # Finnhub Quote: c: Current price, h: High, l: Low, o: Open, pc: Previous close, t: Timestamp
                    price_data = PriceData(
                        stock_symbol=stock.symbol,
                        timestamp=datetime.fromtimestamp(quote['t']),
                        open=quote['o'],
                        high=quote['h'],
                        low=quote['l'],
                        close=quote['c'],
                        volume=0 # Quote endpoint doesn't return volume, need candle for that or separate call
                    )
                    session.add(price_data)
                    print(f"Stored data for {stock.symbol}")
                except Exception as e:
                    print(f"Error fetching {stock.symbol}: {e}")
            
            await session.commit()

    async def start(self, interval: int = 300):
        while True:
            print("Starting data fetch cycle...")
            await self.fetch_and_store_quotes()
            print(f"Cycle complete. Waiting {interval}s")
            await asyncio.sleep(interval)
