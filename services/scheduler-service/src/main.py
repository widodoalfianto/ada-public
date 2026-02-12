from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
import asyncio
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


def _run_async(job_coro):
    """
    Bridge async job coroutines into BlockingScheduler's sync execution model.
    """

    def _runner():
        asyncio.run(job_coro())

    return _runner


def main():
    logger.info("Starting Scheduler Service...")
    
    scheduler = BlockingScheduler(timezone="US/Eastern")

    # ----------------------------------------------------
    # DAILY DATA PIPELINE
    # ----------------------------------------------------
    from src.jobs import (
        daily_price_fetch, 
        daily_indicator_calculation, 
        weekly_data_cleanup,
        evening_esm_scan,
        evening_pf_scan,
        morning_summary_report
    )

    # 4:05 PM - Daily Price Fetch (after market close)
    scheduler.add_job(
        _run_async(daily_price_fetch),
        CronTrigger(day_of_week='mon-fri', hour=16, minute=5)
    )

    # 4:15 PM - Daily Indicator Calculation
    scheduler.add_job(
        _run_async(daily_indicator_calculation),
        CronTrigger(day_of_week='mon-fri', hour=16, minute=15)
    )

    # 4:30 PM - Evening ESM Scan
    scheduler.add_job(
        _run_async(evening_esm_scan),
        CronTrigger(day_of_week='mon-fri', hour=16, minute=30)
    )

    # 4:35 PM - Evening PF Scan
    scheduler.add_job(
        _run_async(evening_pf_scan),
        CronTrigger(day_of_week='mon-fri', hour=16, minute=35)
    )

    # 9:35 AM - Morning Summary Report (market start)
    scheduler.add_job(
        _run_async(morning_summary_report),
        CronTrigger(day_of_week='mon-fri', hour=9, minute=35)
    )

    # ----------------------------------------------------
    # WEEKLY MAINTENANCE
    # ----------------------------------------------------
    # Sunday 2:00 AM - Data Cleanup
    scheduler.add_job(
        _run_async(weekly_data_cleanup),
        CronTrigger(day_of_week='sun', hour=2, minute=0)
    )

    logger.info("Scheduler initialized. Jobs scheduled for daily pipeline and weekly maintenance.")

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Scheduler stopping...")

if __name__ == "__main__":
    main()
