import asyncio
from datetime import datetime
from sqlalchemy import select, desc
from src.database import AsyncSessionLocal
from src.models import Stock
from src.stock_filter import get_top_stocks_by_volume
from shared.models import PriceData, Indicator
from src.config import settings
from src.evaluator import ConditionEvaluator

class ScannerWorker:
    def __init__(self):
        self.running = False

    async def scan_market(self):
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{now}] Starting market scan...")
        async with AsyncSessionLocal() as session:
            # 1. Get top 100 stocks by avg dollar volume
            stocks = await get_top_stocks_by_volume(session, limit=100, min_price=10.0)
            
            for stock in stocks:
                try:
                    # 2. Get recent PriceData (Last 2 days for crossover checks)
                    # We need the last 2 records to compare "Today" vs "Yesterday"
                    stmt_prices = select(PriceData).where(
                        PriceData.stock_id == stock.id
                    ).order_by(desc(PriceData.date)).limit(2)
                    
                    price_result = await session.execute(stmt_prices)
                    prices = price_result.scalars().all()
                    
                    if len(prices) < 2:
                        continue
                        
                    # 3. Get Indicators for these dates
                    target_dates = [p.date for p in prices]
                    stmt_inds = select(Indicator).where(
                        Indicator.stock_id == stock.id,
                        Indicator.date.in_(target_dates)
                    )
                    ind_result = await session.execute(stmt_inds)
                    indicators = ind_result.scalars().all()
                    
                    # 4. Construct History for Evaluator
                    # Format: [{'date': ..., 'volume': ..., 'indicators': {...}}, ...]
                    # Sort desc by date (latest first) matches prices order
                    history = []
                    for p in prices:
                        day_inds = {
                            i.indicator_name: i.value 
                            for i in indicators 
                            if i.date == p.date
                        }
                        
                        # Only include if we have indicators (or lenient?)
                        # Evaluator handles missing keys gracefully-ish, but if empty, signals won't fire
                        history.append({
                            'date': p.date,
                            'volume': p.volume,
                            'indicators': day_inds
                        })
                    
                    # 5. Evaluate
                    signals = ConditionEvaluator.evaluate(history)
                    
                    # 6. Emit Signals (To Alert Service)
                    if signals:
                        import httpx # Import locally or keep at top. Keeping locally to minimize top-level deps if we want
                        async with httpx.AsyncClient() as client:
                            for sig in signals:
                                signal_code = sig.get('signal_code')
                                if signal_code not in ("GOLDEN_CROSS", "DEATH_CROSS"):
                                    continue

                                print(f"Signal for {stock.symbol}: {signal_code}")

                                latest_price = prices[0].close if prices else None
                                indicator_values = {
                                    "ema_9": sig.get("data", {}).get("ema_9"),
                                    "sma_20": sig.get("data", {}).get("sma_20"),
                                }
                                try:
                                    ema_9 = float(indicator_values["ema_9"])
                                    sma_20 = float(indicator_values["sma_20"])
                                    strength = ((ema_9 - sma_20) / sma_20) * 100 if sma_20 else 0.0
                                except Exception:
                                    strength = 0.0
                                indicator_values["strength"] = round(strength, 2)

                                # Record to alert history first (idempotent)
                                record_payload = {
                                    "stock_symbol": stock.symbol,
                                    "triggered_at": datetime.utcnow().isoformat(),
                                    "date": prices[0].date.isoformat() if prices else datetime.utcnow().date().isoformat(),
                                    "condition_met": "Golden Cross" if signal_code == "GOLDEN_CROSS" else "Death Cross",
                                    "crossover_type": "golden_cross" if signal_code == "GOLDEN_CROSS" else "death_cross",
                                    "direction": "bullish" if signal_code == "GOLDEN_CROSS" else "bearish",
                                    "price": float(latest_price) if latest_price is not None else 0.0,
                                    "indicator_values": indicator_values,
                                }

                                try:
                                    record_resp = await client.post(
                                        f"{settings.DATA_SERVICE_URL}/api/record-alert",
                                        json=record_payload,
                                        timeout=5.0
                                    )
                                    record_data = record_resp.json() if record_resp.status_code == 200 else {}
                                    if record_data.get("status") != "success":
                                        print(f"Skipping notify for {stock.symbol}: {record_data.get('message', 'record failed')}")
                                        continue
                                except Exception as e:
                                    print(f"Failed to record alert for {stock.symbol}: {e}")
                                    continue

                                notify_payload = {
                                    "signal_code": signal_code,
                                    "symbol": stock.symbol,
                                    "timestamp": sig['timestamp'],
                                    "data": sig['data']
                                }

                                try:
                                    await client.post(
                                        f"{settings.ALERT_SERVICE_URL}/signal",
                                        json=notify_payload,
                                        timeout=5.0
                                    )
                                except Exception as e:
                                    print(f"Failed to send alert for {stock.symbol}: {e}")
                            
                except Exception as e:
                    print(f"Error scanning {stock.symbol}: {e}")

    async def start(self, interval: int = 86400): # 24 hours
        self.running = True
        while self.running:
            await self.scan_market()
            # Wait for next scan
            await asyncio.sleep(interval)
