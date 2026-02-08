import asyncio
import sys
from sqlalchemy import select, delete, func


from src.database import AsyncSessionLocal
from src.models import Stock, Indicator, PriceData
from src.service import process_stock_indicators

async def verify_aapl():
    print("\n2. Checking existing data count...")
    async with AsyncSessionLocal() as session:
        # Get AAPL ID
        stock_res = await session.execute(select(Stock).where(Stock.symbol == "AAPL"))
        stock = stock_res.scalars().first()
        
        if stock:
            # Check count
            count_res = await session.execute(
                select(func.count()).select_from(PriceData).where(PriceData.stock_id == stock.id)
            )
            count = count_res.scalar()
            print(f"  Existing count: {count}")
            
            if count < 200:
                print("  Insufficient data (< 200 days). Deleting to force backfill...")
                await session.execute(delete(PriceData).where(PriceData.stock_id == stock.id))
                await session.commit()
                print("  Deleted.")
    
    print("\n3. Skipping automatic backfill triggered by script (run manually in data-service if needed)...")
    # In Docker, we can't easily call the neighbor service script from here without complex networking/volumes.
    # We assume the user/orchestrator has run backfill_history.py for AAPL in data-service already.

    print("\n4. Calculation Indicators for AAPL...")
    async with AsyncSessionLocal() as session:
        
        # Run calculation
        count = await process_stock_indicators(stock.id, session)
        print(f"  Calculated {count} indicator records.")
        
        if count > 0:
            print("\n3. Verifying stored data (Latest 5 records)...")
            # Fetch latest indicators
            # indicators table has composite PK (stock_id, date, indicator_name)
            # Let's fetch the latest DATE present
            
            # Find latest date
            # We can't easily do max(date) on composite PK without being specific or using distinct.
            # Let's just grab last 20 rows order by date desc
            
            ind_res = await session.execute(
                select(Indicator)
                .where(Indicator.stock_id == stock.id)
                .order_by(Indicator.date.desc())
                .limit(20)
            )
            indicators = ind_res.scalars().all()
            
            # Group by date for display
            by_date = {}
            for ind in indicators:
                if ind.date not in by_date:
                    by_date[ind.date] = {}
                by_date[ind.date][ind.indicator_name] = ind.value
                
            sorted_dates = sorted(by_date.keys(), reverse=True)
            for d in sorted_dates[:3]:
                print(f"  Date: {d}")
                for name, val in by_date[d].items():
                    print(f"    {name}: {val:.4f}")

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    # Set env vars if needed (assuming they are set in the shell or .env is loaded by config)
    # The config.py loads .env, so we just need to make sure we run this from where .env is visible or accessible?
    # Our config.py usually looks for .env in current CWD. 
    # If we run from root, it should be fine.
    
    asyncio.run(verify_aapl())
