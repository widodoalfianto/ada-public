import asyncio
import sys
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from src.config import settings
from src.models import Stock, PriceData, Indicator

# Database setup
engine = create_async_engine(settings.DATABASE_URL, echo=False)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

async def cleanup_data():
    print("Connecting to database...")
    async with AsyncSessionLocal() as session:
        # 1. Identify inactive stocks
        print("Finding inactive stocks...")
        result = await session.execute(select(Stock.id).where(Stock.is_active == False))
        inactive_ids = result.scalars().all()
        
        if not inactive_ids:
            print("No inactive stocks found.")
            return

        print(f"Found {len(inactive_ids)} inactive stocks. Cleaning up associated data...")
        
        # 2. Delete data in chunks to avoid locking/timeout issues if huge
        # (For simplicity here, we do it in one go or batches if needed, 
        # but 16k stocks * ~2 years data is a lot. Bulk delete is faster via SQL directly)
        
        # Convert IDs to tuple for SQL IN clause
        # If list is too large, we might need to batch this.
        # 16,000 IDs is fine for postgres IN clause usually.
        
        # Delete PriceData
        print("Deleting PriceData for inactive stocks...")
        # Using raw SQL for efficiency with large IN clause, or SQLAlchemy delete
        # SQLAlchemy delete: delete(PriceData).where(PriceData.stock_id.in_(inactive_ids))
        
        # Chunking list of IDs
        chunk_size = 1000
        total_deleted_prices = 0
        total_deleted_indicators = 0
        
        for i in range(0, len(inactive_ids), chunk_size):
            chunk = inactive_ids[i:i + chunk_size]
            
            # Prices
            stmt_prices = delete(PriceData).where(PriceData.stock_id.in_(chunk))
            res_prices = await session.execute(stmt_prices)
            total_deleted_prices += res_prices.rowcount
            
            # Indicators
            stmt_indicators = delete(Indicator).where(Indicator.stock_id.in_(chunk))
            res_indicators = await session.execute(stmt_indicators)
            total_deleted_indicators += res_indicators.rowcount
            
            await session.commit()
            print(f"Processed chunk {i}-{i+len(chunk)}. Prices deleted: {res_prices.rowcount}")

        print("-" * 30)
        print("Cleanup Complete.")
        print(f"Total Inactive Stocks Processed: {len(inactive_ids)}")
        print(f"Total Price Rows Deleted: {total_deleted_prices}")
        print(f"Total Indicator Rows Deleted: {total_deleted_indicators}")

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(cleanup_data())
