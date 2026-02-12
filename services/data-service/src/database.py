from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text
from src.config import settings

engine = create_async_engine(settings.DATABASE_URL, echo=False)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

from shared.database import Base

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session

async def init_db():
    # Import models to ensure they are registered with Base.metadata
    print(f"DEBUG: Tables to create: {Base.metadata.tables.keys()}")
    
    async with engine.begin() as conn:
        # Create tables
        await conn.run_sync(Base.metadata.create_all)
        
        # Initialize TimescaleDB extension
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;"))
        
        # Convert price_data to hypertable
        # Check if already a hypertable to avoid errors on restart
        try:
            await conn.execute(text("SELECT create_hypertable('price_data', 'date', if_not_exists => TRUE);"))
        except Exception as e:
            print(f"Hypertable creation info: {e}")
            
        # Convert indicators to hypertable could be useful too, sharing partitioning by date
        # indicators has date column too
        try:
             await conn.execute(text("SELECT create_hypertable('indicators', 'date', if_not_exists => TRUE);"))
        except Exception as e:
            print(f"Hypertable creation info (indicators): {e}")

        # Alert history hardening:
        # 1) normalize null types so uniqueness can be enforced
        # 2) dedupe legacy rows by (stock_id, date, crossover_type)
        # 3) enforce unique index for idempotent inserts under concurrency
        try:
            await conn.execute(text("""
                UPDATE alert_history
                SET crossover_type = 'unknown'
                WHERE crossover_type IS NULL;
            """))
            await conn.execute(text("""
                DELETE FROM alert_history a
                USING alert_history b
                WHERE a.id < b.id
                  AND a.stock_id = b.stock_id
                  AND a.date = b.date
                  AND a.crossover_type = b.crossover_type;
            """))
            await conn.execute(text("""
                CREATE UNIQUE INDEX IF NOT EXISTS uq_alert_history_stock_date_type
                ON alert_history (stock_id, date, crossover_type);
            """))
        except Exception as e:
            print(f"Alert history uniqueness setup info: {e}")
