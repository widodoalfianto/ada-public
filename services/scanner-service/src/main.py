from datetime import date
import logging
from typing import Optional

from fastapi import FastAPI, BackgroundTasks
from pydantic import BaseModel

from src.signal_worker import SignalWorker

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

app = FastAPI()
worker = SignalWorker()


class DatePayload(BaseModel):
    target_date: Optional[date] = None
    send_notifications: bool = True


@app.on_event("startup")
async def startup_event():
    # Scanner is trigger-based from scheduler/API; no autonomous background loop.
    return


@app.get("/")
async def root():
    return {"message": "Scanner Service is running"}


@app.post("/run-scan")
async def run_scan(background_tasks: BackgroundTasks, payload: DatePayload = None):
    """
    Trigger all enabled strategy scans.
    """
    target = payload.target_date if payload else None
    send_notifications = payload.send_notifications if payload else True
    background_tasks.add_task(
        worker.run_all,
        target_date=target,
        send_notifications=send_notifications,
    )
    return {
        "message": f"All enabled strategy scans triggered for {target if target else 'today'}",
        "send_notifications": send_notifications,
    }


@app.post("/run-strategy-scan/{strategy_code}")
async def run_strategy_scan(
    strategy_code: str,
    background_tasks: BackgroundTasks,
    payload: DatePayload = None,
):
    """
    Trigger a specific strategy scan by code (e.g. ESM, PF).
    """
    target = payload.target_date if payload else None
    send_notifications = payload.send_notifications if payload else True
    code = strategy_code.upper()
    background_tasks.add_task(
        worker.run_strategy,
        code,
        target_date=target,
        send_notifications=send_notifications,
    )
    return {
        "message": f"{code} scan triggered in background for {target if target else 'today'}",
        "send_notifications": send_notifications,
    }


@app.post("/run-esm-scan")
async def run_esm_scan(background_tasks: BackgroundTasks, payload: DatePayload = None):
    """
    Trigger ESM strategy scan.
    """
    return await run_strategy_scan("ESM", background_tasks, payload)


@app.post("/run-pf-scan")
async def run_pf_scan(background_tasks: BackgroundTasks, payload: DatePayload = None):
    """
    Trigger PF strategy scan.
    """
    return await run_strategy_scan("PF", background_tasks, payload)
