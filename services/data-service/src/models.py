from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Boolean, BigInteger, Date, Text
from sqlalchemy.dialects.postgresql import JSONB, ARRAY
from sqlalchemy.orm import relationship
from src.database import Base
from datetime import datetime


# AlertConfig, AlertHistory, ScanLog, FetchFailure are still specific to Data Service (or can be moved later if needed)
# But for now they stay here, inheriting from shared Base


class AlertConfig(Base):
    __tablename__ = "alert_configs"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    condition_json = Column(JSONB, nullable=False)
    stocks = Column(ARRAY(String))  # Array of symbols, None/Null means all
    priority = Column(String(20), default='medium')
    enabled = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    history = relationship("AlertHistory", back_populates="config")

class AlertHistory(Base):
    __tablename__ = "alert_history"

    id = Column(BigInteger, primary_key=True, index=True)
    alert_config_id = Column(Integer, ForeignKey("alert_configs.id"), index=True)
    stock_id = Column(Integer, ForeignKey("stocks.id"), index=True)
    triggered_at = Column(DateTime, nullable=False, index=True)
    date = Column(Date, nullable=False, index=True)
    condition_met = Column(String(255))
    crossover_type = Column(String(20), index=True)  # 'golden_cross' or 'death_cross'
    direction = Column(String(50))  # bullish or bearish
    price = Column(Float)
    indicator_values = Column(JSONB)
    notified = Column(Boolean, default=False)
    notification_sent_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)

    config = relationship("AlertConfig", back_populates="history")
    stock = relationship("Stock", backref="alert_history")

class ScanLog(Base):
    __tablename__ = "scan_logs"

    id = Column(Integer, primary_key=True, index=True)
    scan_type = Column(String(50), index=True) # pre_market, end_of_day
    scan_time = Column(DateTime, nullable=False, index=True)
    stocks_attempted = Column(Integer)
    stocks_successful = Column(Integer)
    stocks_failed = Column(Integer)
    alerts_detected = Column(Integer)
    alerts_sent = Column(Integer)
    api_calls_used = Column(Integer)
    duration_seconds = Column(Integer)
    status = Column(String(20)) # completed, partial, failed
    error_message = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

    failures = relationship("FetchFailure", back_populates="scan_log")

class FetchFailure(Base):
    __tablename__ = "fetch_failures"

    id = Column(Integer, primary_key=True, index=True)
    stock_id = Column(Integer, ForeignKey("stocks.id"))
    scan_log_id = Column(Integer, ForeignKey("scan_logs.id"))
    error_code = Column(String(50))
    error_message = Column(Text)
    attempted_at = Column(DateTime, nullable=False)
    retry_count = Column(Integer, default=0)
    resolved = Column(Boolean, default=False)

    stock = relationship("Stock", backref="fetch_failures")
    scan_log = relationship("ScanLog", back_populates="failures")
