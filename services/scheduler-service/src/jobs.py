import requests
import logging
import os
import pandas_market_calendars as mcal
from datetime import datetime
import pytz

logger = logging.getLogger(__name__)

from src.config import settings

logger = logging.getLogger(__name__)

# SCANNER_URL removed in separate edit or handled here by replacing usage

def is_trading_day():
    """
    Check if today is a valid trading day using pandas_market_calendars.
    """
    nyse = mcal.get_calendar('NYSE')
    now = datetime.now(pytz.timezone('US/Eastern'))
    today_str = now.strftime('%Y-%m-%d')
    
    schedule = nyse.schedule(start_date=today_str, end_date=today_str)
    return not schedule.empty

def run_market_scan(scan_type: str):
    """
    Triggers the scan if today is a trading day.
    """
    logger.info(f"Job triggered: {scan_type}")
    
    if not is_trading_day():
        logger.info("Today is NOT a trading day (Holiday/Weekend). Skipping scan.")
        return

    logger.info(f"Trading day confirmed. Triggering {scan_type} scan...")
    
    try:
        resp = requests.post(f"{settings.SCANNER_SERVICE_URL}/run-scan")
        if resp.status_code == 200:
            logger.info("✅ Scan triggered successfully.")
        else:
            logger.error(f"❌ Failed to trigger scan. Status: {resp.status_code}, Body: {resp.text}")
    except Exception as e:
        logger.error(f"❌ Connection error triggering scan: {e}")
