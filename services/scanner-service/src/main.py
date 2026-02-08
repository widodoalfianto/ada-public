from fastapi import FastAPI, BackgroundTasks
from src.worker import ScannerWorker
import asyncio
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

app = FastAPI()
worker = ScannerWorker()

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(worker.start())

@app.get("/")
async def root():
    return {"message": "Scanner Service is running"}

@app.post("/run-scan")
async def run_scan(background_tasks: BackgroundTasks):
    background_tasks.add_task(worker.scan_market)
    return {"message": "Scan triggered in background"}

from src.crossover_worker import CrossoverWorker

from pydantic import BaseModel
from typing import Optional
from datetime import date

class DatePayload(BaseModel):
    target_date: Optional[date] = None

@app.post("/run-crossover-scan")
async def run_crossover_scan(background_tasks: BackgroundTasks, payload: DatePayload = None):
    """
    Trigger the Golden Cross / Death Cross scan.
    Filters top 100 stocks by volume and checks for EMA 9/SMA 20 crossovers.
    """
    target = payload.target_date if payload else None
    crossover_worker = CrossoverWorker()
    background_tasks.add_task(crossover_worker.run_scan, target_date=target)
    
    return {"message": f"Crossover scan triggered in background for {target if target else 'today'}"}
