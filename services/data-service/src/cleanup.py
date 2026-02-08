"""
Data Cleanup Service

Handles pruning of old data to maintain database performance and reduce storage costs.
"""
import logging
from datetime import datetime, date, timedelta
from sqlalchemy import text
from src.database import AsyncSessionLocal

logger = logging.getLogger(__name__)

async def prune_old_data():
    """
    Delete data older than retention policies:
    - Indicators: > 2 years
    - Alert History: > 90 days
    """
    start_time = datetime.now()
    summary = {
        "status": "completed",
        "indicators_deleted": 0,
        "alerts_deleted": 0,
        "logs_deleted": 0,
        "duration_seconds": 0
    }
    
    # Retention Periods
    indicator_cutoff = date.today() - timedelta(days=730) # 2 years
    alert_cutoff = date.today() - timedelta(days=90)      # 3 months
    log_cutoff = date.today() - timedelta(days=30)        # 1 month for operational logs
    
    logger.info(f"Starting data pruning. Cutoffs: Indicators < {indicator_cutoff}, Alerts < {alert_cutoff}")

    async with AsyncSessionLocal() as session:
        try:
            # 1. Prune Indicators
            # Using direct SQL for efficiency with large deletes
            ind_query = text("DELETE FROM indicators WHERE date < :cutoff")
            result = await session.execute(ind_query, {"cutoff": indicator_cutoff})
            summary["indicators_deleted"] = result.rowcount
            logger.info(f"Deleted {summary['indicators_deleted']} old indicators")

            # 2. Prune Alert History
            alert_query = text("DELETE FROM alert_history WHERE date < :cutoff")
            result = await session.execute(alert_query, {"cutoff": alert_cutoff})
            summary["alerts_deleted"] = result.rowcount
            logger.info(f"Deleted {summary['alerts_deleted']} old alerts")
            
            # 3. Prune Scan Logs & Failures (Optional cleanup for hygiene)
            log_query = text("DELETE FROM scan_logs WHERE created_at < :cutoff")
            result = await session.execute(log_query, {"cutoff": log_cutoff})
            summary["logs_deleted"] = result.rowcount
            
            # Orphaned fetch_failures usually cascade delete if foreign keys are set up correctly, 
            # otherwise distinct cleanup might be needed. Assuming cascade or ignoring for now.
            
            await session.commit()
            
        except Exception as e:
            await session.rollback()
            logger.error(f"Cleanup failed: {e}")
            summary["status"] = "failed"
            summary["error"] = str(e)
    
    duration = (datetime.now() - start_time).total_seconds()
    summary["duration_seconds"] = round(duration, 2)
    summary["timestamp"] = datetime.now().isoformat()
    
    return summary
