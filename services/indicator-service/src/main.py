from fastapi import FastAPI, HTTPException
from sqlalchemy import select
from src.database import AsyncSessionLocal
from src.models import PriceData, Stock
from src.indicators import calculate_all_indicators
import pandas as pd
from datetime import datetime, date

import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

app = FastAPI()

@app.get("/")
async def root():
    return {"message": "Indicator Service is running"}

@app.get("/indicators/{symbol}")
async def get_indicators(symbol: str, days: int = 1):
    logger.info(f"Received request for {symbol} (days={days})")
    async with AsyncSessionLocal() as session:
        # Get stock_id
        stock_res = await session.execute(select(Stock).where(Stock.symbol == symbol))
        stock = stock_res.scalars().first()
        
        if not stock:
            raise HTTPException(status_code=404, detail="Stock not found")

        # Get price data
        query = select(PriceData).where(PriceData.stock_id == stock.id).order_by(PriceData.date.asc())
        result = await session.execute(query)
        prices = result.scalars().all()
        
        if not prices:
            raise HTTPException(status_code=404, detail="No price data found for symbol")
            
        # Convert to DataFrame
        df = pd.DataFrame([{
            'date': p.date,
            'close': p.close,
            'high': p.high,
            'low': p.low,
            'open': p.open,
            'volume': p.volume
        } for p in prices])
        
        # Calculate Indicators using shared logic
        indicators_map = calculate_all_indicators(df)
        
        # Prepare response list (latest first)
        results = []
        
        # Take the last N rows
        target_rows = df.iloc[-days:]
        # Reverse to have latest first
        target_rows = target_rows.iloc[::-1]

        for idx, row in target_rows.iterrows():
            rec = {
                'date': row['date'].isoformat(),
                'close': float(row['close']),
                'volume': int(row['volume']) if pd.notna(row['volume']) else 0,
                'indicators': {}
            }
            
            for name, series in indicators_map.items():
                if idx in series.index:
                    val = series.loc[idx]
                    if pd.notna(val):
                        rec['indicators'][name] = float(val)
            
            results.append(rec)
        
        return results

from src.daily_calculate import calculate_daily_indicators

from pydantic import BaseModel
from typing import Optional

class DatePayload(BaseModel):
    target_date: Optional[date] = None

@app.post("/api/daily-calculate")
async def daily_calculate(payload: DatePayload = None):
    """
    Calculate indicators for TODAY for all active stocks.
    Incremental mode - only calculates latest date, not historical.
    """
    logger.info("Starting Indicator Service...")
    try:
        target = payload.target_date if payload else None
        summary = await calculate_daily_indicators(target_date=target)
        return summary
    except Exception as e:
        logger.error(f"Daily indicator calculation failed: {e}", exc_info=True)
        return {
            "status": "failed",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }
