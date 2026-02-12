from fastapi import FastAPI
from src.database import init_db
from contextlib import asynccontextmanager
import asyncio
import logging
from datetime import datetime, date
from pydantic import BaseModel
from typing import List, Optional, Dict, Any

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield

app = FastAPI(lifespan=lifespan)

@app.on_event("startup")
async def startup_event():
    # Initialize DB (Create Tables)
    pass # DB Init handled by lifespan or externally. Lifespan handles it.
    # asyncio.create_task(scheduler.start()) # Legacy scheduler disabled


@app.get("/")
async def root():
    return {"message": "Data Service is running"}

from src.database import AsyncSessionLocal
from shared.models import Stock
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from src.daily_update import fetch_daily_prices

class DatePayload(BaseModel):
    target_date: Optional[date] = None
    lookback_days: int = 0

@app.post("/api/daily-update")
async def daily_update(payload: DatePayload = None):
    """
    Fetch and store latest price data for all active stocks.
    Designed to be called daily after market close.
    """
    try:
        target = payload.target_date if payload else None
        lookback = payload.lookback_days if payload else 0
        summary = await fetch_daily_prices(target_date=target, lookback_days=lookback)
        return summary
    except Exception as e:
        logger.error(f"Daily update failed: {e}", exc_info=True)
        return {
            "status": "failed",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }

from src.cleanup import prune_old_data

@app.post("/api/cleanup")
async def run_cleanup():
    """
    Trigger data pruning for old records (Indicators, Alerts).
    Should be scheduled weekly.
    """
    try:
        summary = await prune_old_data()
        return summary
    except Exception as e:
        logger.error(f"Cleanup endpoint failed: {e}", exc_info=True)
        return {
            "status": "failed",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }


# Alert History Endpoints
from src.models import AlertHistory

class AlertCreate(BaseModel):
    stock_symbol: str
    alert_config_id: Optional[int] = None
    triggered_at: datetime
    date: date
    condition_met: str
    crossover_type: Optional[str] = None
    direction: str
    price: float
    indicator_values: Dict[str, Any]

@app.post("/api/record-alert")
async def record_alert(alert: AlertCreate):
    """
    Record an alert in the history.
    """
    try:
        async with AsyncSessionLocal() as session:
            # Find stock id
            stmt = select(Stock.id).where(Stock.symbol == alert.stock_symbol)
            result = await session.execute(stmt)
            stock_id = result.scalar()
            
            if not stock_id:
                return {"status": "error", "message": "Stock not found"}

            history = AlertHistory(
                stock_id=stock_id,
                alert_config_id=alert.alert_config_id,
                triggered_at=alert.triggered_at,
                date=alert.date,
                condition_met=alert.condition_met,
                crossover_type=alert.crossover_type or "unknown",
                direction=alert.direction,
                price=alert.price,
                indicator_values=alert.indicator_values,
                notified=False,
            )
            session.add(history)

            try:
                await session.commit()
            except IntegrityError:
                await session.rollback()
                return {"status": "skipped", "message": "Duplicate alert"}

            await session.refresh(history)
            return {"status": "success", "id": history.id}
    except Exception as e:
        logger.error(f"Failed to record alert: {e}", exc_info=True)
        return {"status": "error", "message": str(e)}

@app.get("/api/alert-history")
async def get_alert_history(target_date: date):
    """
    Get alert history for a specific date.
    Useful for morning summary.
    """
    try:
        async with AsyncSessionLocal() as session:
            # Join with Stock to get symbol
            stmt = select(AlertHistory, Stock.symbol).join(Stock).where(
                AlertHistory.date == target_date
            )
            result = await session.execute(stmt)
            rows = result.all()
            
            alerts = []
            for history, symbol in rows:
                alerts.append({
                    "symbol": symbol,
                    "crossover_type": history.crossover_type,
                    "direction": history.direction,
                    "price": history.price,
                    "condition_met": history.condition_met,
                    "indicator_values": history.indicator_values,
                    "triggered_at": history.triggered_at.isoformat()
                })
            
            return {"status": "success", "alerts": alerts}
            
    except Exception as e:
        logger.error(f"Failed to fetch alert history: {e}", exc_info=True)
        return {"status": "error", "message": str(e)}

