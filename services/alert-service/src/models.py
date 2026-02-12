from sqlalchemy import Column, String, Text, Boolean, DateTime
from src.database import Base
from datetime import datetime

class SignalRegistry(Base):
    """
    Registry for Alert definitions.
    Maps a raw 'signal_code' (e.g. ESM_ENTRY) to presentation details.
    """
    __tablename__ = "signal_registry"
    
    signal_code = Column(String(50), primary_key=True)
    display_name = Column(String(100), nullable=False) # e.g. "Golden Cross"
    emoji = Column(String(10))                         # e.g. "🐂"
    severity = Column(String(20), default='info')      # info, warning, high, critical
    template_text = Column(Text, nullable=False)       # e.g. "SMA {fast} crossed {slow}"
    action_text = Column(String(100))                  # e.g. "Potential Entry"
    enabled = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
