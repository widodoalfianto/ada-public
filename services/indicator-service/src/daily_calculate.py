"""
Daily Indicator Calculation Endpoint

Handles incremental indicator calculation - computes indicators only for latest date.
"""
import logging
from datetime import datetime, date, timedelta
from typing import Dict, Any
from sqlalchemy import select
from src.database import AsyncSessionLocal
from src.models import Stock, PriceData, Indicator
from src.indicators import calculate_all_indicators
import pandas as pd

logger = logging.getLogger(__name__)


async def calculate_daily_indicators(target_date: date = None) -> Dict[str, Any]:
    """
    Calculate indicators for TODAY (or target_date) for all active stocks.
    Only calculates for the latest date, not historical backfill.
    
    Returns:
        Summary dict with success/failure counts and duration
    """
    start_time = datetime.now()
    
    success_count = 0
    failure_count = 0
    indicators_created = 0
    skipped_count = 0
    failures = []
    latest_processed_date = None
    
    today = target_date if target_date else date.today()
    logger.info(f"Starting daily indicator calculation for {today}")
    
    async with AsyncSessionLocal() as session:
        # Get all active stocks
        result = await session.execute(select(Stock).where(Stock.is_active == True))
        stocks = result.scalars().all()
        
        total_stocks = len(stocks)
        logger.info(f"Found {total_stocks} active stocks to process")
        
        for i, stock in enumerate(stocks, 1):
            try:
                # Get last 200 days of price data (need for 200-day SMA)
                cutoff_date = today - timedelta(days=250)  # Extra buffer for weekends
                price_query = select(PriceData).where(
                    PriceData.stock_id == stock.id,
                    PriceData.date >= cutoff_date,
                    PriceData.date <= today  # Ensure we don't peek into future if backfilling
                ).order_by(PriceData.date.asc())
                
                price_result = await session.execute(price_query)
                prices = price_result.scalars().all()
                
                if len(prices) < 50:  # Need minimum data for indicators
                    logger.warning(f"[{i}/{total_stocks}] {stock.symbol}: Insufficient price data ({len(prices)} days)")
                    failure_count += 1
                    failures.append({"symbol": stock.symbol, "error": "Insufficient price data"})
                    continue
                
                # Convert to DataFrame
                df = pd.DataFrame([{
                    'date': p.date,
                    'close': p.close,
                    'high': p.high,
                    'low': p.low,
                    'open': p.open,
                    'volume': p.volume or 0
                } for p in prices])
                
                # Calculate all indicators
                indicators_map = calculate_all_indicators(df)
                
                # Get ONLY the last row (today's indicators)
                last_idx = df.index[-1]
                last_date = df['date'].iloc[-1]
                if latest_processed_date is None or last_date > latest_processed_date:
                    latest_processed_date = last_date

                # Check if indicators already exist for the actual last_date
                existing_result = await session.execute(
                    select(Indicator.indicator_name).where(
                        Indicator.stock_id == stock.id,
                        Indicator.date == last_date
                    )
                )
                existing_names = set(existing_result.scalars().all())
                
                # Create indicator records for TODAY only
                batch_indicators = []
                for indicator_name, series in indicators_map.items():
                    if indicator_name in existing_names:
                        continue
                    if last_idx in series.index:
                        val = series.loc[last_idx]
                        if pd.notna(val):
                            indicator = Indicator(
                                stock_id=stock.id,
                                date=last_date,
                                indicator_name=indicator_name,
                                value=float(val)
                            )
                            batch_indicators.append(indicator)
                
                if not batch_indicators:
                    if existing_names:
                        logger.debug(f"[{i}/{total_stocks}] {stock.symbol}: Indicators already exist for {last_date} (skipping)")
                        skipped_count += 1
                        continue
                    logger.warning(f"[{i}/{total_stocks}] {stock.symbol}: No indicators calculated")
                    failure_count += 1
                    failures.append({"symbol": stock.symbol, "error": "No indicators calculated"})
                    continue
                
                # Batch insert
                session.add_all(batch_indicators)
                indicators_created += len(batch_indicators)
                success_count += 1
                
                if i % 50 == 0:
                    logger.info(f"Progress: {i}/{total_stocks} stocks, {indicators_created} indicators created")
                    await session.commit()  # Commit in batches
                
            except Exception as e:
                await session.rollback()
                logger.error(f"[{i}/{total_stocks}] {stock.symbol}: Error - {e}")
                failure_count += 1
                failures.append({"symbol": stock.symbol, "error": str(e)})
        
        # Final commit
        await session.commit()
    
    duration = (datetime.now() - start_time).total_seconds()
    
    summary_date = latest_processed_date.isoformat() if latest_processed_date else today.isoformat()
    summary = {
        "status": "completed",
        "date": summary_date,
        "total_stocks": total_stocks,
        "success_count": success_count,
        "failure_count": failure_count,
        "skipped_count": skipped_count,
        "indicators_created": indicators_created,
        "success_rate": round((success_count / total_stocks * 100), 2) if total_stocks > 0 else 0,
        "duration_seconds": round(duration, 2),
        "failures": failures[:10] if failures else [],
        "timestamp": datetime.now().isoformat()
    }
    
    logger.info(f"Daily indicator calculation complete: {success_count}/{total_stocks} stocks, {indicators_created} indicators in {duration:.2f}s")
    
    if failure_count > total_stocks * 0.05:  # Alert if > 5% failure rate
        logger.error(f"HIGH FAILURE RATE: {failure_count}/{total_stocks} stocks failed!")
    
    return summary
