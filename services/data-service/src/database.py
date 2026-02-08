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
