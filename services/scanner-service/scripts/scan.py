import asyncio
import sys
import httpx
from src.config import settings
from src.evaluator import ConditionEvaluator

import argparse
from datetime import datetime

from sqlalchemy import select
from src.database import AsyncSessionLocal
from src.models import Stock

async def manual_scan(symbol: str, start_date_str: str = None):
    symbols_to_scan = []
    
    if symbol.upper() == 'ALL':
        print("Fetching all active stocks...")
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(Stock.symbol).where(Stock.is_active == True))
            symbols_to_scan = result.scalars().all()
        print(f"Found {len(symbols_to_scan)} stocks.")
    else:
        symbols_to_scan = [symbol]

    async with httpx.AsyncClient() as client:
        for sym in symbols_to_scan:
            await scan_single_stock(client, sym, start_date_str)

async def scan_single_stock(client, symbol, start_date_str):
    print(f"Scanning {symbol}...")
    if start_date_str:
        print(f"Replaying from {start_date_str}...")
        try:
            # Fetch plenty of history (e.g. 200 days) to cover the range
            url = f"{settings.INDICATOR_SERVICE_URL}/indicators/{symbol}?days=300"
            # print(f"Fetching from {url}")
            resp = await client.get(url)
            
            if resp.status_code != 200:
                print(f"Error: Status {resp.status_code} - {resp.text}")
                return

            data = resp.json()
            if not data:
                print("No data returned.")
                return

            # print(f"Received {len(data)} records.")
            
            # Data is returned Latest -> Oldest (Index 0 is Today)
            # We want to replay from Past -> Present
            # Sort chronological: Oldest -> Latest
            chronological_data = sorted(data, key=lambda x: x['date'])
            
            start_date_obj = datetime.strptime(start_date_str, "%Y-%m-%d").date() if start_date_str else None
            
            alerts_found = 0
            
            # Iterate
            for i in range(1, len(chronological_data)):
                current = chronological_data[i]
                previous = chronological_data[i-1]
                
                curr_date = datetime.fromisoformat(current['date']).date()
                
                # specific start date check
                if start_date_obj and curr_date < start_date_obj:
                    continue
                
                # Construct history for evaluator (Expecting [Current, Previous])
                history_window = [current, previous]
                
                alerts = ConditionEvaluator.evaluate(history_window)
                
                if alerts:
                    alerts_found += 1
                    print(f"\n[{symbol}] [{curr_date}] SIGNALS:")
                    for a in alerts:
                        print(f" - {a.get('signal_code')} (Timestamp: {a.get('timestamp')})")
                        print(f"   Data: {a.get('data')}")
                        
                        # Trigger actual alert via new /signal endpoint
                        try:
                            payload = {
                                "signal_code": a['signal_code'],
                                "symbol": symbol,
                                "timestamp": a['timestamp'],
                                "data": a['data']
                            }
                            
                            await client.post(
                                f"{settings.ALERT_SERVICE_URL}/signal",
                                json=payload
                            )
                        except Exception as ex:
                            print(f"Failed to send signal: {ex}")

            if alerts_found > 0:
                print(f"{symbol}: {alerts_found} events.")
                
        except Exception as e:
            print(f"Exception scanning {symbol}: {e}")

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        
    parser = argparse.ArgumentParser()
    parser.add_argument("symbol", help="Stock symbol")
    parser.add_argument("--start", help="Start date YYYY-MM-DD", default=None)
    args = parser.parse_args()
    
    asyncio.run(manual_scan(args.symbol, args.start))
