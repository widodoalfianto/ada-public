"""
Daily Price Data Update Endpoint

Handles automated daily price fetching for all active stocks.
Uses shared utilities for transaction management and idempotency.
Switched to yfinance for data retrieval.
"""
import logging
from datetime import datetime, date, timedelta
from typing import Dict, Any
from sqlalchemy import select, text
from src.database import AsyncSessionLocal
from shared.models import Stock, PriceData
import yfinance as yf
import pandas as pd

# Import shared utilities
from shared.transactions import batch_transaction
from shared.idempotency import check_duplicate, log_idempotency_skip
from shared.exceptions import ExternalServiceError, log_exception

logger = logging.getLogger(__name__)


async def fetch_daily_prices(target_date: date = None, lookback_days: int = 0) -> Dict[str, Any]:
    """
    Fetch and store latest price data for all active stocks using yfinance.
    Supports backfilling via lookback_days.
    
    Args:
        target_date: Optional date to fetch data for. Defaults to today.
        lookback_days: Number of days to look back from target_date for backfilling.
    
    Returns:
        Summary dict with success/failure counts and duration
    """
    start_time = datetime.now()
    
    success_count = 0
    failure_count = 0
    skipped_count = 0
    failures = []
    
    today = target_date if target_date else date.today()
    start_date = today - timedelta(days=lookback_days)
    
    logger.info(f"Starting price fetch. Range: {start_date} to {today} (lookback={lookback_days}) using yfinance")
    
    async with AsyncSessionLocal() as session:
        # Auto-backfill guard: ensure enough history for indicators on fresh DBs
        if lookback_days == 0:
            try:
                stats = await session.execute(text("""
                    SELECT COUNT(*) AS rows,
                           COUNT(DISTINCT date) AS days,
                           MIN(date) AS min_date,
                           MAX(date) AS max_date
                    FROM price_data
                """))
                row_count, day_count, min_date, max_date = stats.fetchone()
                if row_count == 0 or (day_count is not None and day_count < 50):
                    lookback_days = 120
                    start_date = today - timedelta(days=lookback_days)
                    logger.warning(
                        "Price data history insufficient (rows=%s, days=%s, min=%s, max=%s). "
                        "Auto-backfill enabled with lookback_days=%s.",
                        row_count, day_count, min_date, max_date, lookback_days
                    )
            except Exception as e:
                logger.error(f"Auto-backfill guard failed: {e}")

        # Get all active stocks
        result = await session.execute(select(Stock).where(Stock.is_active == True))
        stocks = result.scalars().all()
        
        total_stocks = len(stocks)
        logger.info(f"Found {total_stocks} active stocks to process")
        
        # 1. Filter checks
        # optimization: if lookback > 0, we might skip detailed idempotency check per date here 
        # and rely on DB constraints or check inside loop.
        # For bulk backfill, checking 500 stocks * 60 days = 30000 checks is slow.
        # We will optimistically fetch and check inside or rely on upsert?
        # Let's fetch all active stocks logic if backfilling.
        
        stocks_to_process = []
        if lookback_days > 5:
            # Assume we want to process all if backfilling large history
            stocks_to_process = stocks
        else:
             # For daily update, check idempotency for 'today'
            for stock in stocks:
                if await check_duplicate(session, PriceData, stock_id=stock.id, target_date=today):
                     # Only skip if we are ONLY doing today.
                     if lookback_days == 0:
                        skipped_count += 1
                        success_count += 1
                        continue
                     else:
                        stocks_to_process.append(stock)
                else:
                    stocks_to_process.append(stock)
                
        if not stocks_to_process:
            logger.info("All stocks already have data for today. Skipping fetch.")
        else:
            logger.info(f"Fetching data for {len(stocks_to_process)} stocks...")
            
            # 2. Bulk Fetch with yfinance
            symbols = [s.symbol.upper() for s in stocks_to_process]
            stock_map = {s.symbol.upper(): s for s in stocks_to_process}
            
            # yfinance expects end date as exclusive, so add 1 day to cover 'today'
            end_date = today + timedelta(days=1)
            
            try:
                # Use threads=True for faster download
                # group_by='ticker' ensures consistency
                df = yf.download(
                    symbols,
                    start=start_date,
                    end=end_date,
                    group_by='ticker',
                    threads=True,
                    progress=False,
                    auto_adjust=False,
                )

                # If we are doing a daily update and nothing comes back (weekend/holiday),
                # retry with a short lookback window to capture the last trading day.
                if df.empty and lookback_days == 0 and target_date is None:
                    fallback_start = today - timedelta(days=7)
                    logger.warning(
                        "No data returned for %s to %s. Retrying with lookback to %s.",
                        start_date,
                        end_date,
                        fallback_start,
                    )
                    df = yf.download(
                        symbols,
                        start=fallback_start,
                        end=end_date,
                        group_by='ticker',
                        threads=True,
                        progress=False,
                        auto_adjust=False,
                    )

                if df.empty:
                    logger.error("yfinance returned empty data for all symbols in range %s to %s.", start_date, end_date)
                    for symbol in symbols:
                        failure_count += 1
                        failures.append({"symbol": symbol, "error": "No data returned from yfinance (empty download)"})
                    # Skip processing if we have no data at all
                    df = None
                
                # 3. Process Results
                # Batch transaction for inserts
                async with batch_transaction(session, batch_size=500, operation_name="daily_price_fetch") as batch:
                    if df is None:
                        return {
                            "status": "completed",
                            "total_stocks": total_stocks,
                            "success_count": success_count,
                            "skipped_count": skipped_count,
                            "failure_count": failure_count,
                            "success_rate": 0,
                            "duration_seconds": round((datetime.now() - start_time).total_seconds(), 2),
                            "failures": failures[:10] if failures else [],
                            "timestamp": datetime.now().isoformat(),
                        }

                    for symbol in symbols:
                        try:
                            # Handle DataFrame structure (Single level for 1 symbol, Multi-level for many)
                            if len(symbols) == 1:
                                ticker_data = df
                            else:
                                try:
                                    ticker_data = df[symbol]
                                except KeyError:
                                    logger.warning(f"No data returned for {symbol}")
                                    failure_count += 1
                                    failures.append({"symbol": symbol, "error": "No data returned from yfinance"})
                                    continue
                            
                            if ticker_data.empty:
                                logger.warning(f"Empty data for {symbol}")
                                failure_count += 1
                                continue
                            
                            # Normalize index to date
                            ticker_data.index = ticker_data.index.date
                            stock = stock_map.get(symbol)
                            if stock is None:
                                logger.warning(f"Unknown symbol in stock map: {symbol}")
                                failure_count += 1
                                failures.append({"symbol": symbol, "error": "Symbol not in stock map"})
                                continue
                            wrote_any = False

                            # Iterate over ALL rows in the range
                            for row_date, row in ticker_data.iterrows():
                                # row_date is the index (date object)
                                
                                # Check for NaN values
                                if pd.isna(row['Close']):
                                    continue
                                wrote_any = True
                                
                                # Check idempotency per row/date (Skip if exists)
                                # Optimization: Bulk check or cache? 
                                # For now, simple check. If backfilling 30k rows, this is slow.
                                # But we are using batch_transaction...
                                # Let's assume on backfill we might want to upsert or just ignore errors?
                                # Ideally check_duplicate.
                                if await check_duplicate(session, PriceData, stock_id=stock.id, target_date=row_date):
                                    continue

                                # Create PriceData record
                                price_data = PriceData(
                                    stock_id=stock.id,
                                    date=row_date,
                                    open=float(row['Open']),
                                    high=float(row['High']),
                                    low=float(row['Low']),
                                    close=float(row['Close']),
                                    adjusted_close=float(row['Adj Close']),
                                    volume=int(row['Volume'])
                                )
                                
                                session.add(price_data)
                                await batch.increment()
                            
                            # Update transient stock stats (use last row)
                            if wrote_any:
                                last_row = ticker_data.iloc[-1]
                                stock.last_close_price = float(last_row['Close'])
                                success_count += 1
                            else:
                                logger.warning(f"No valid rows for {symbol}")
                                failure_count += 1
                            
                        except Exception as e:
                            logger.error(f"Error processing {symbol}: {e}")
                            failure_count += 1
                            failures.append({"symbol": symbol, "error": str(e)})

            except Exception as e:
                logger.error(f"Critical yfinance error: {e}")
                return {
                    "status": "failed",
                    "error": str(e),
                    "timestamp": datetime.now().isoformat()
                }

        # 4. Update stats (Avg Volume) efficiently
        if success_count > 0:
            logger.info("Updating 30-day average volume stats...")
            
            update_stats_stm = text("""
                UPDATE stocks s
                SET 
                    avg_volume_30d = (
                        SELECT AVG(volume)::bigint 
                        FROM price_data p 
                        WHERE p.stock_id = s.id 
                        AND p.date >= CURRENT_DATE - INTERVAL '30 days'
                    ),
                    last_close_price = (
                        SELECT close 
                        FROM price_data p 
                        WHERE p.stock_id = s.id 
                        ORDER BY date DESC 
                        LIMIT 1
                    ),
                    updated_at = NOW()
                WHERE s.is_active = true
            """)
            
            try:
                await session.execute(update_stats_stm)
                await session.commit()
                logger.info("Stock volume and price stats updated successfully")
            except Exception as e:
                logger.error(f"Failed to update stock stats: {e}")

    duration = (datetime.now() - start_time).total_seconds()
    
    summary = {
        "status": "completed",
        "total_stocks": total_stocks,
        "success_count": success_count,
        "skipped_count": skipped_count,
        "failure_count": failure_count,
        "success_rate": round((success_count / total_stocks * 100), 2) if total_stocks > 0 else 0,
        "duration_seconds": round(duration, 2),
        "failures": failures[:10] if failures else [],
        "timestamp": datetime.now().isoformat()
    }
    
    logger.info(f"Price fetch complete: {success_count}/{total_stocks} succeeded ({skipped_count} skipped) in {duration:.2f}s")
    
    return summary
