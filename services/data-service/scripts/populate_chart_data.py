import asyncio
import os
import sys
from datetime import datetime, timedelta
import random
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

# Add parent dir to path to import src
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from src.config import settings

async def populate():
    print("Populating dummy chart data...")
    engine = create_async_engine(settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://"))
    
    async with engine.begin() as conn:
        # 1. Create Stock
        await conn.execute(text("""
            INSERT INTO stocks (symbol, name, is_active) 
            VALUES ('CHART-TEST', 'Chart Test Corp', true) 
            ON CONFLICT (symbol) DO NOTHING
        """))
        
        # Get ID
        result = await conn.execute(text("SELECT id FROM stocks WHERE symbol = 'CHART-TEST'"))
        stock_id = result.scalar()
        print(f"Stock ID: {stock_id}")
        
        # 2. Generate Price Data (120 days)
        # Clear old data
        await conn.execute(text("DELETE FROM price_data WHERE stock_id = :id"), {"id": stock_id})
        await conn.execute(text("DELETE FROM indicators WHERE stock_id = :id"), {"id": stock_id})
        
        prices = []
        indicators = []
        base_price = 100.0
        today = datetime.now().date()
        
        for i in range(120):
            date = today - timedelta(days=(120-i))
            change = random.uniform(-2, 2)
            base_price += change
            
            open_p = base_price - random.uniform(0, 1)
            close_p = base_price + random.uniform(0, 1)
            high_p = max(open_p, close_p) + random.uniform(0, 0.5)
            low_p = min(open_p, close_p) - random.uniform(0, 0.5)
            vol = int(random.uniform(100000, 2000000))
            
            prices.append({
                "stock_id": stock_id,
                "date": date,
                "open": open_p,
                "high": high_p,
                "low": low_p,
                "close": close_p,
                "volume": vol
            })
            
            # Indicators
            indicators.append({"stock_id": stock_id, "date": date, "name": "sma_50", "value": base_price * 0.95})
            indicators.append({"stock_id": stock_id, "date": date, "name": "sma_200", "value": base_price * 0.80})
            indicators.append({"stock_id": stock_id, "date": date, "name": "sma_20", "value": base_price * 0.98}) # Added SMA 20
            indicators.append({"stock_id": stock_id, "date": date, "name": "ema_9", "value": base_price * 0.99}) # Added EMA 9
            indicators.append({"stock_id": stock_id, "date": date, "name": "rsi_14", "value": 50 + (change*10)})
            indicators.append({"stock_id": stock_id, "date": date, "name": "macd", "value": change})
            indicators.append({"stock_id": stock_id, "date": date, "name": "macd_signal", "value": change * 0.9})
            
        # Insert Prices
        for p in prices:
            await conn.execute(text("""
                INSERT INTO price_data (stock_id, date, open, high, low, close, volume)
                VALUES (:stock_id, :date, :open, :high, :low, :close, :volume)
            """), p)
            
        # Insert Indicators
        for ind in indicators:
            await conn.execute(text("""
                INSERT INTO indicators (stock_id, date, indicator_name, value)
                VALUES (:stock_id, :date, :name, :value)
            """), ind)
            
    print("Done!")

if __name__ == "__main__":
    asyncio.run(populate())
