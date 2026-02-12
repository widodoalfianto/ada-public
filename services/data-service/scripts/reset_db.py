import asyncio
import os
import sys
from sqlalchemy import text
from src.database import AsyncSessionLocal

# Dangerous script!
async def reset_db():
    allow = os.getenv("ALLOW_DB_RESET", "").strip().lower() in {"1", "true", "yes"}
    env = os.getenv("ENV", "").strip().lower()
    if not allow and env not in {"dev", "test", "local"}:
        print("Refusing to reset DB outside local/dev/test.")
        print("Set ALLOW_DB_RESET=true to override.")
        return

    print("WARNING: This will delete ALL data from the database (stocks, prices, indicators).")
    print("Waiting 5 seconds... Press Ctrl+C to cancel.")
    await asyncio.sleep(5)
    
    async with AsyncSessionLocal() as session:
        print("Truncating tables...")
        # Order matters due to foreign keys, or use CASCADE
        tables = [
            "fetch_failures", 
            "scan_logs", 
            "alert_history",
            "alert_configs",
            "indicators", 
            "price_data", 
            "stocks"
        ]
        
        for table in tables:
            try:
                # TRUNCATE is faster and resets auto-increment counters usually (with RESTART IDENTITY)
                # CASCADE is needed because of FKs
                print(f"  Truncating {table}...")
                await session.execute(text(f"TRUNCATE TABLE {table} RESTART IDENTITY CASCADE;"))
            except Exception as e:
                print(f"  Error truncating {table}: {e}")
        
        await session.commit()
        print("Database reset complete.")

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    asyncio.run(reset_db())
