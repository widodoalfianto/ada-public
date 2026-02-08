import asyncio
import sys
import random
from datetime import datetime, timedelta
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
import yfinance as yf
import pandas as pd

from src.config import settings
from src.models import Stock, PriceData
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Database setup
engine = create_async_engine(settings.DATABASE_URL, echo=False)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

async def backfill_history(days_back: int = 365, target_symbol: str = None):
    end_date = datetime.now().date()
    start_date = end_date - timedelta(days=days_back)
    
    logger.info(f"Starting backfill. Range: {start_date} to {end_date}. Target: {target_symbol or 'ALL'}")
    
    async with AsyncSessionLocal() as session:
        # Get all active stocks
        stmt = select(Stock.id, Stock.symbol).where(Stock.is_active == True)
        if target_symbol:
            stmt = stmt.where(Stock.symbol == target_symbol)
            
        result = await session.execute(stmt)
        stocks = result.all()
        
        total_stocks = len(stocks)
        processed = 0
        
        logger.info(f"Found {total_stocks} active stocks to backfill.")
        
        for stock_id, symbol in stocks:
            processed += 1
            if processed % 10 == 0:
                logger.info(f"[{processed}/{total_stocks}] Processing...")
            
            # Smart Resume Check
            try:
                stmt = select(func.max(PriceData.date)).where(PriceData.stock_id == stock_id)
                last_date_res = await session.execute(stmt)
                last_date = last_date_res.scalar()
                
                current_start = start_date
                
                if last_date:
                    if last_date >= (end_date - timedelta(days=1)):
                        # Verbose logging only for single target or infrequent
                        if target_symbol: 
                            logger.info(f"  > Skipping {symbol}, up to date ({last_date})")
                        continue
                    current_start = max(start_date, last_date + timedelta(days=1))
                
                if current_start >= end_date:
                     continue
                
                # RATE LIMITING:
                # Yahoo Finance unofficial limit is ~2000/hour (~33/min).
                # We aim for ~1.8s - 2.5s delay to be safe.
                delay = random.uniform(2.0, 3.0)
                await asyncio.sleep(delay)

                # Fetch (with retry for 429)
                max_retries = 3
                retry_count = 0
                success = False
                
                while retry_count < max_retries:
                    try:
                        def fetch_yf():
                            ticker = yf.Ticker(symbol)
                            # auto_adjust=True gives us adjusted close in the Close column usually
                            return ticker.history(start=current_start, end=end_date + timedelta(days=1), interval="1d", auto_adjust=False)

                        df = await asyncio.to_thread(fetch_yf)
                        
                        if df.empty:
                            if target_symbol: logger.warning(f"  > No data for {symbol}")
                            success = True # No data is technically a success in fetching
                            break
                        
                        new_records = []
                        for index, row in df.iterrows():
                            if pd.isna(row['Open']) or pd.isna(row['Close']):
                                continue

                            dt = index.date()
                            price = PriceData(
                                stock_id=stock_id,
                                date=dt,
                                open=float(row['Open']),
                                high=float(row['High']),
                                low=float(row['Low']),
                                close=float(row['Close']),
                                volume=int(row['Volume']), 
                                adjusted_close=float(row['Adj Close']) if 'Adj Close' in row else float(row['Close'])
                            )
                            new_records.append(price)
                        
                        if new_records:
                            session.add_all(new_records)
                            await session.commit()
                            logger.info(f"  > {symbol}: Saved {len(new_records)} days.")
                        
                        success = True
                        break
                        
                    except Exception as e:
                        err_str = str(e).lower()
                        if "too many requests" in err_str or "429" in err_str:
                            retry_count += 1
                            wait_time = 60 * (2 ** retry_count) # 2m, 4m, 8m
                            logger.warning(f"  ! 429 Rate Limit for {symbol}. Sleeping {wait_time}s...")
                            await asyncio.sleep(wait_time)
                        else:
                            logger.error(f"  > Failed {symbol}: {e}")
                            await session.rollback()
                            break # Non-limit error, skip
                
            except Exception as e:
                logger.error(f"  > Error processing {symbol}: {e}")
                await session.rollback()

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    # Allow override days
    days = 365
    target_symbol = None
    
    if len(sys.argv) > 1:
        days = int(sys.argv[1])
    
    if len(sys.argv) > 2:
        target_symbol = sys.argv[2]
        
    asyncio.run(backfill_history(days, target_symbol))