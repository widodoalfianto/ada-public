"""
Batch Indicator Calculation Script

Calculates technical indicators for all stocks with price data.
Designed to run as a one-time batch job to populate the indicators table.
"""
import sys
sys.path.insert(0, '/app')

import asyncio
import pandas as pd
from sqlalchemy import select, text
from src.database import AsyncSessionLocal
from src.models import PriceData, Indicator
from src.indicators import calculate_all_indicators
import logging
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def calculate_indicators_for_symbol(session, stock_id: int, symbol: str) -> int:
    """Calculate and save indicators for a single stock"""
    try:
        # Get price data
        query = select(PriceData).where(PriceData.stock_id == stock_id).order_by(PriceData.date.asc())
        result = await session.execute(query)
        prices = result.scalars().all()
        
        if not prices or len(prices) < 50:  # Need minimum data for indicators
            logger.warning(f"  {symbol}: Insufficient data ({len(prices)} days)")
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
        
        # Count inserted records
        inserted_count = 0
        
        # Save to database
        for idx, row in df.iterrows():
            indicator_values = {}
            
            # Extract all indicator values for this date
            for name, series in indicators_map.items():
                if idx in series.index:
                    val = series.loc[idx]
                    if pd.notna(val):
                        indicator_values[name] = float(val)
            
            # Skip if no indicators (early dates don't have enough data)
            if not indicator_values:
                continue
            
            # Create indicator record
            indicator = Indicator(
                stock_id=stock_id,
                date=row['date'],
                sma_9=indicator_values.get('sma_9'),
                sma_20=indicator_values.get('sma_20'),
                sma_50=indicator_values.get('sma_50'),
                sma_200=indicator_values.get('sma_200'),
                ema_9=indicator_values.get('ema_9'),
                ema_12=indicator_values.get('ema_12'),
                ema_20=indicator_values.get('ema_20'),
                ema_26=indicator_values.get('ema_26'),
                ema_50=indicator_values.get('ema_50'),
                rsi_14=indicator_values.get('rsi_14'),
                macd_line=indicator_values.get('macd_line'),
                macd_signal=indicator_values.get('macd_signal'),
                macd_hist=indicator_values.get('macd_hist'),
                bb_upper=indicator_values.get('bb_upper'),
                bb_middle=indicator_values.get('bb_middle'),
                bb_lower=indicator_values.get('bb_lower'),
                sma_vol_20=indicator_values.get('sma_vol_20')
            )
            
            session.add(indicator)
            inserted_count += 1
        
        await session.commit()
        logger.info(f"  ✅ {symbol}: {inserted_count} indicator records saved")
        return inserted_count
        
    except Exception as e:
        await session.rollback()
        logger.error(f"  ❌ {symbol}: Error - {e}")
        return 0


async def batch_calculate_all():
    """Calculate indicators for all stocks with price data"""
    logger.info("=" * 80)
    logger.info("BATCH INDICATOR CALCULATION")
    logger.info("=" * 80)
    
    async with AsyncSessionLocal() as session:
        # Get all stocks with price data
        query = text("""
            SELECT DISTINCT s.id, s.symbol 
            FROM stocks s
            INNER JOIN price_data pd ON s.id = pd.stock_id
            WHERE s.is_active = true
            ORDER BY s.symbol
        """)
        result = await session.execute(query)
        stocks = result.fetchall()
        
        total_stocks = len(stocks)
        logger.info(f"Found {total_stocks} stocks with price data\n")
        
        # Check existing indicators
        indicator_check = text("""
            SELECT COUNT(DISTINCT stock_id) as stocks_with_indicators
            FROM indicators
        """)
        result = await session.execute(indicator_check)
        existing = result.fetchone()[0]
        logger.info(f"Currently {existing} stocks have indicators")
        logger.info(f"Need to process {total_stocks - existing} stocks\n")
        
        # Process each stock
        total_indicators = 0
        processed = 0
        skipped = 0
        errors = 0
        
        for stock_id, symbol in stocks:
            processed += 1
            
            # Check if already has indicators
            check_query = select(Indicator).where(Indicator.stock_id == stock_id).limit(1)
            existing_result = await session.execute(check_query)
            if existing_result.scalars().first():
                logger.info(f"[{processed}/{total_stocks}] {symbol}: Already has indicators (skipping)")
                skipped += 1
                continue
            
            logger.info(f"[{processed}/{total_stocks}] Processing {symbol}...")
            count = await calculate_indicators_for_symbol(session, stock_id, symbol)
            
            if count > 0:
                total_indicators += count
            else:
                errors += 1
            
            # Progress update every 50 stocks
            if processed % 50 == 0:
                logger.info("")
                logger.info(f"--- Progress: {processed}/{total_stocks} stocks processed ---")
                logger.info(f"    Indicators created: {total_indicators}")
                logger.info(f"    Skipped: {skipped}, Errors: {errors}")
                logger.info("")
        
        # Final summary
        logger.info("")
        logger.info("=" * 80)
        logger.info("BATCH CALCULATION COMPLETE")
        logger.info("=" * 80)
        logger.info(f"Total stocks processed: {processed}")
        logger.info(f"Total indicators created: {total_indicators}")
        logger.info(f"Skipped (already exists): {skipped}")
        logger.info(f"Errors: {errors}")
        logger.info("=" * 80)


if __name__ == "__main__":
    logger.info(f"Starting batch indicator calculation at {datetime.now()}")
    asyncio.run(batch_calculate_all())
    logger.info(f"Completed at {datetime.now()}")
