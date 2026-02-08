from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
import logging
from src.jobs import run_market_scan

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

def main():
    logger.info("Starting Scheduler Service...")
    
    scheduler = BlockingScheduler(timezone="US/Eastern")
    
    # Schedule Jobs
    # 9:35 AM - Market Open Scan (giving 5 mins for data to settle)
    scheduler.add_job(
        run_market_scan, 
        CronTrigger(day_of_week='mon-fri', hour=9, minute=35),
        args=['open']
    )
    
    # 4:05 PM - Market Close Scan
    scheduler.add_job(
        run_market_scan, 
        CronTrigger(day_of_week='mon-fri', hour=16, minute=5),
        args=['close']
    )

    # ----------------------------------------------------
    # DAILY DATA PIPELINE
    # ----------------------------------------------------
    # ----------------------------------------------------
    # DAILY DATA PIPELINE
    # ----------------------------------------------------
    from src.daily_pipeline_jobs import (
        daily_price_fetch, 
        daily_indicator_calculation, 
        weekly_data_cleanup,
        evening_crossover_scan,
        morning_summary_report
    )

    # 4:05 PM - Daily Price Fetch (after market close)
    scheduler.add_job(
        daily_price_fetch,
        CronTrigger(day_of_week='mon-fri', hour=16, minute=5)
    )

    # 4:15 PM - Daily Indicator Calculation
    scheduler.add_job(
        daily_indicator_calculation,
        CronTrigger(day_of_week='mon-fri', hour=16, minute=15)
    )

    # 4:30 PM - Evening Crossover Scan (Golden/Death Cross)
    scheduler.add_job(
        evening_crossover_scan,
        CronTrigger(day_of_week='mon-fri', hour=16, minute=30)
    )

    # 9:35 AM - Morning Summary Report (market start)
    scheduler.add_job(
        morning_summary_report,
        CronTrigger(day_of_week='mon-fri', hour=9, minute=35)
    )

    # ----------------------------------------------------
    # WEEKLY MAINTENANCE
    # ----------------------------------------------------
    # Sunday 2:00 AM - Data Cleanup
    scheduler.add_job(
        weekly_data_cleanup,
        CronTrigger(day_of_week='sun', hour=2, minute=0)
    )
    
    # Verify job immediately on startup if needed (optional)
    # run_market_scan('startup_check')

    logger.info("Scheduler initialized. Jobs scheduled for M-F market open/close and daily pipeline.")

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Scheduler stopping...")

if __name__ == "__main__":
    main()
