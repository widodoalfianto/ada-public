import asyncio
from sqlalchemy import select, delete
from src.database import AsyncSessionLocal
from src.models import Stock, PriceData, Indicator
from src.indicators import calculate_all_indicators
import pandas as pd
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def process_stock_indicators(stock_id: int, session):
    # Fetch price data
    result = await session.execute(
        select(PriceData)
        .where(PriceData.stock_id == stock_id)
        .order_by(PriceData.date.asc())
    )
    prices = result.scalars().all()
    
    if not prices or len(prices) < 10: # Need some minimum data
        return 0

    # Convert to DataFrame
    df = pd.DataFrame([{
        'date': p.date,
        'close': p.close,
        'high': p.high,
        'low': p.low,
        'open': p.open,
        'volume': p.volume
    } for p in prices])
    
    # Calculate all indicators
    indicators_map = calculate_all_indicators(df)
    
    # Prepare Indicator objects
    # We will overwrite existing or insert new. 
    # For efficiency, we might deletes all for this stock first or use upsert.
    # Given the volume, upsert per row is slow. Deleting all for the stock and re-inserting is risky if access is concurrent.
    # Let's just insert the LATEST computed indicators if we are running daily, 
    # BUT Phase 3 implies backfilling history of indicators too?
    # "Database storage for calculated indicators" -> usually implies storing the time series of indicators.
    
    # Let's prepare a list of Indicator objects
    new_indicators = []
    
    # indicators_map returns Series. 
    # df['date'] corresponds to the index of these series.
    
    # We iterate through the dataframe indices to align dates
    for i, row_date in enumerate(df['date']):
        for name, series in indicators_map.items():
            val = series.iloc[i]
            if pd.isna(val) or pd.isnull(val):
                continue
                
            new_indicators.append(Indicator(
                stock_id=stock_id,
                date=row_date,
                indicator_name=name,
                value=float(val)
            ))

    # Bulk save
    # To avoid PK conflicts, we should probably delete existing for this stock/range or use merge.
    # Merge is slow. Delete and re-insert is faster for full recalc.
    
    # Delete existing
    await session.execute(delete(Indicator).where(Indicator.stock_id == stock_id))
    
    # Insert in chunks
    chunk_size = 1000
    for k in range(0, len(new_indicators), chunk_size):
        session.add_all(new_indicators[k:k+chunk_size])
    
    await session.commit()
    return len(new_indicators)

async def run_indicator_update_for_all():
    async with AsyncSessionLocal() as session:
        # Get active stocks
        result = await session.execute(select(Stock).where(Stock.is_active == True))
        stocks = result.scalars().all()
        
        total = len(stocks)
        logger.info(f"Found {total} active stocks to process.")
        
        for i, stock in enumerate(stocks):
            try:
                count = await process_stock_indicators(stock.id, session)
                logger.info(f"[{i+1}/{total}] Processed {stock.symbol}: {count} indicators.")
            except Exception as e:
                logger.error(f"Error processing {stock.symbol}: {e}")

if __name__ == "__main__":
    import sys
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(run_indicator_update_for_all())
