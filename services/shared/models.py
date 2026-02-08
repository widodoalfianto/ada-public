from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Boolean, BigInteger, Date
from sqlalchemy.orm import relationship
from shared.database import Base
from datetime import datetime

class Stock(Base):
    __tablename__ = "stocks"

    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String(10), unique=True, index=True, nullable=False)
    name = Column(String(255))
    exchange = Column(String(20))
    sector = Column(String(100), index=True)
    industry = Column(String(100))
    market_cap = Column(BigInteger)
    avg_volume_20d = Column(BigInteger)
    avg_volume_30d = Column(BigInteger, index=True)  # For top 100 filtering
    last_close_price = Column(Float)  # For min price filtering
    is_active = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    prices = relationship("PriceData", back_populates="stock")
    indicators = relationship("Indicator", back_populates="stock")
    # Service-specific relationships (AlertHistory, FetchFailure) are injected via backref in their respective services

class PriceData(Base):
    __tablename__ = "price_data"

    # TimescaleDB requires the partitioning column (date) to be part of the primary key
    stock_id = Column(Integer, ForeignKey("stocks.id"), primary_key=True)
    date = Column(Date, nullable=False, primary_key=True)
    open = Column(Float)
    high = Column(Float)
    low = Column(Float)
    close = Column(Float)
    volume = Column(BigInteger)
    adjusted_close = Column(Float)
    created_at = Column(DateTime, default=datetime.utcnow)

    stock = relationship("Stock", back_populates="prices")

class Indicator(Base):
    __tablename__ = "indicators"

    stock_id = Column(Integer, ForeignKey("stocks.id"), primary_key=True)
    date = Column(Date, nullable=False, primary_key=True)
    indicator_name = Column(String(50), primary_key=True)
    value = Column(Float)
    created_at = Column(DateTime, default=datetime.utcnow)

    stock = relationship("Stock", back_populates="indicators")
