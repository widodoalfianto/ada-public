"""
Daily data pipeline jobs for scheduler service
"""
import httpx
import logging
from datetime import datetime
from src.config import settings
from src.jobs import is_trading_day

logger = logging.getLogger(__name__)


async def daily_price_fetch():
    if not is_trading_day():
        logger.info("Daily price fetch: Not a trading day. Skipping.")
        return

    """
    Fetch daily price data for all active stocks.
    Runs Monday-Friday at 5:00 PM EST (after market close).
    """
    logger.info("=" * 80)
    logger.info(f"[{datetime.now()}] Starting daily price fetch...")
    logger.info("=" * 80)
    
    try:
        # Call data-service daily update endpoint
        async with httpx.AsyncClient(timeout=600.0) as client:  # 10 min timeout
            response = await client.post(f"{settings.DATA_SERVICE_URL}/api/daily-update")
            result = response.json()
            
            logger.info(f"✅ Price fetch complete!")
            logger.info(f"   Stocks processed: {result.get('total_stocks', 0)}")
            logger.info(f"   Success: {result.get('success_count', 0)}")
            logger.info(f"   Failures: {result.get('failure_count', 0)}")
            logger.info(f"   Duration: {result.get('duration_seconds', 0)}s")
            
            # Alert if high failure rate
            if result.get('failure_count', 0) > result.get('total_stocks', 0) * 0.1:
                logger.error(f"⚠️ WARNING: High failure rate detected!")
                
    except Exception as e:
        logger.error(f"❌ Price fetch failed: {e}", exc_info=True)


async def daily_indicator_calculation():
    if not is_trading_day():
        logger.info("Daily indicator calculation: Not a trading day. Skipping.")
        return

    """
    Calculate daily indicators for all active stocks.
    Runs Monday-Friday at 5:15 PM EST (after price fetch).
    """
    logger.info("=" * 80)
    logger.info(f"[{datetime.now()}] Starting daily indicator calculation...")
    logger.info("=" * 80)
    
    try:
        # Call indicator-service daily calculate endpoint
        async with httpx.AsyncClient(timeout=300.0) as client:  # 5 min timeout
            response = await client.post(f"{settings.INDICATOR_SERVICE_URL}/api/daily-calculate")
            result = response.json()
            
            logger.info(f"✅ Indicator calculation complete!")
            logger.info(f"   Stocks processed: {result.get('success_count', 0)}/{result.get('total_stocks', 0)}")
            logger.info(f"   Indicators created: {result.get('indicators_created', 0)}")
            logger.info(f"   Skipped: {result.get('skipped_count', 0)}")
            logger.info(f"   Duration: {result.get('duration_seconds', 0)}s")
            
            # Alert if high failure rate
            if result.get('failure_count', 0) > result.get('total_stocks', 0) * 0.05:
                logger.error(f"⚠️ WARNING: High failure rate detected!")
                
    except Exception as e:
        logger.error(f"❌ Indicator calculation failed: {e}", exc_info=True)


async def weekly_data_cleanup():
    """
    Trigger weekly data cleanup (pruning old records).
    Runs Sundays at 2:00 AM EST.
    """
    logger.info("=" * 80)
    logger.info(f"[{datetime.now()}] Starting weekly data cleanup...")
    logger.info("=" * 80)
    
    try:
        # Call data-service cleanup endpoint
        async with httpx.AsyncClient(timeout=300.0) as client:
            response = await client.post(f"{settings.DATA_SERVICE_URL}/api/cleanup")
            result = response.json()
            
            logger.info(f"✅ Data cleanup complete!")
            logger.info(f"   Indicators Deleted: {result.get('indicators_deleted', 0)}")
            logger.info(f"   Alerts Deleted: {result.get('alerts_deleted', 0)}")
            logger.info(f"   Duration: {result.get('duration_seconds', 0)}s")
            
            if result.get('status') == 'failed':
                logger.error(f"❌ Cleanup reported failure: {result.get('error')}")

    except Exception as e:
        logger.error(f"❌ Data cleanup failed: {e}", exc_info=True)


async def evening_crossover_scan():
    if not is_trading_day():
        logger.info("Evening crossover scan: Not a trading day. Skipping.")
        return

    """
    Run Golden Cross / Death Cross scan.
    Runs Monday-Friday at 5:30 PM EST (after indicators calculated).
    """
    logger.info("=" * 80)
    logger.info(f"[{datetime.now()}] Starting Evening Crossover Scan...")
    logger.info("=" * 80)
    
    try:
        # Call scanner-service to run crossover scan
        async with httpx.AsyncClient(timeout=600.0) as client:
            response = await client.post(f"{settings.SCANNER_SERVICE_URL}/run-crossover-scan")
            
            if response.status_code == 200:
                logger.info("✅ Crossover scan triggered successfully")
            else:
                logger.error(f"❌ Failed to trigger scan: {response.text}")
                
    except Exception as e:
        logger.error(f"❌ Crossover scan trigger failed: {e}", exc_info=True)


async def morning_summary_report():
    if not is_trading_day():
        logger.info("Morning summary: Not a trading day. Skipping.")
        return

    """
    Trigger Morning Summary Report.
    Runs Monday-Friday at 8:30 AM EST (Pre-market).
    """
    logger.info("=" * 80)
    logger.info(f"[{datetime.now()}] Triggering Morning Summary...")
    logger.info("=" * 80)
    
    try:
        # Call alert-service to send summary
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(f"{settings.ALERT_SERVICE_URL}/send-morning-summary")
            
            if response.status_code == 200:
                logger.info("✅ Morning summary triggered successfully")
            else:
                logger.error(f"❌ Failed to trigger summary: {response.text}")
                
    except Exception as e:
        logger.error(f"❌ Morning summary trigger failed: {e}", exc_info=True)
