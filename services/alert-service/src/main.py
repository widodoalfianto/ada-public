from fastapi import FastAPI
from pydantic import BaseModel
import asyncio
from typing import Dict, Any, Optional
from src.bot import bot
from src.config import settings
from src.database import init_db, AsyncSessionLocal
from src.models import SignalRegistry
from src.chart_generator import ChartGenerator
from sqlalchemy import select

import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

app = FastAPI()

# --- Models ---

class RawSignal(BaseModel):
    """New Raw Signal Model (Registry based)"""
    signal_code: str
    symbol: str
    timestamp: int
    data: Dict[str, Any]

# --- Startup ---

@app.on_event("startup")
async def startup_event():
    # Initialize DB (Create Tables)
    await init_db()
    # Start Discord Bot in background
    # Start Discord Bot in background
    token = settings.DISCORD_BOT_TOKEN
    if not token or "your_" in token or token == "placeholder":
        asyncio.create_task(bot.start_mock())
    else:
        asyncio.create_task(bot.start(token))



@app.post("/signal")
async def receive_signal(signal: RawSignal):
    """New endpoint: Accepts raw signals and formats them via Registry."""
    logger.info(f"Received Signal: {signal.signal_code} for {signal.symbol}")
    
    async with AsyncSessionLocal() as session:
        # Looking up definition
        stmt = select(SignalRegistry).where(SignalRegistry.signal_code == signal.signal_code)
        result = await session.execute(stmt)
        definition = result.scalars().first()
        
        if not definition:
            logger.warning(f"Unknown signal code: {signal.signal_code}")
            return {"status": "ignored", "reason": "unknown_code"}
            
        if not definition.enabled:
            return {"status": "ignored", "reason": "disabled"}
            
        # Format Data
        try:
            # Add symbol to data context for formatting
            # Template expects {data[key]}, so we must nest the signal data under a 'data' key
            ctx = {'data': signal.data, 'symbol': signal.symbol}
            
            # Format using safe substitution
            class SafeDict(dict):
                def __missing__(self, key):
                    return "N/A"
            
            # Wrap nested 'data' if it exists and is a dict
            if isinstance(ctx.get('data'), dict):
                ctx['data'] = SafeDict(ctx['data'])
            
            safe_ctx = SafeDict(ctx)
            message_body = definition.template_text.format_map(safe_ctx)
        except Exception as e:
            logger.error(f"Formatting error: {e}")
            message_body = f"Error formatting message. Raw Data: {signal.data}"

        # Construct Embed Details
        emoji = definition.emoji if definition.emoji else ""
        title = f"{emoji} {definition.display_name}: {signal.symbol}"
        if settings.TEST_MODE:
            title = f"[TEST] {title}"
            
        # Color Logic
        color = 0x00ff00 # Default Green
        sev = definition.severity.lower()
        if sev == "high" or sev == "critical":
            # If 'bearish' in display name or code, make it Red? 
            # Ideally the registry should have a 'color' or 'sentiment' column too.
            # For now, simplistic heuristic or default.
            if "BEARISH" in signal.signal_code or "DEATH" in signal.signal_code or "OVERBOUGHT" in signal.signal_code:
                 color = 0xff0000 
            else:
                 color = 0x00ff00
        elif sev == "warning":
            color = 0xffff00
            
        # Body Construction
        body = f"🕒 <t:{signal.timestamp}:f>\n\n"
        body += f"**Signal**: {message_body}\n"
        
        if definition.action_text:
            body += f"**Action**: {definition.action_text}\n"
            
        if sev == "critical":
             body += "\n🚨 **CRITICAL ALERT** 🚨"
        elif sev == "high":
             body += "\n⚠️ **HIGH PRIORITY**"

        # Determine Category for Routing based on signal code
        category = "general"
        if "MACD" in signal.signal_code: category = "macd"
        elif "RSI" in signal.signal_code: category = "rsi"
        elif "VOL" in signal.signal_code: category = "volume"
        elif "CROSS" in signal.signal_code: category = "ma"
        
        target_channel = _get_channel_for_category(category, sev)
        
        # Determine which indicators to show on chart
        indicators_to_show = None # Default: Show all
        show_volume_panel = True # Default: Show volume
        
        # User Logic: Filter noise based on signal type
        if "GOLDEN_CROSS" in signal.signal_code or "DEATH_CROSS" in signal.signal_code:
            # User specifically requested ONLY EMA9 and SMA20, and NO Volume, NO SMA50/200
            indicators_to_show = ['ema_9', 'sma_20']
            show_volume_panel = False
        elif "RSI" in signal.signal_code:
            indicators_to_show = ['rsi_14']
        elif "MACD" in signal.signal_code:
            indicators_to_show = ['macd', 'macd_signal']
        elif "SMA" in signal.signal_code or "EMA" in signal.signal_code:
             indicators_to_show = ['sma_20', 'sma_50', 'sma_200', 'ema_9']
        
        # Generate Chart
        image_buffer = None
        try:
            image_buffer = await ChartGenerator.generate_chart(
                signal.symbol, 
                session, 
                indicators=indicators_to_show, 
                show_volume=show_volume_panel
            )
        except Exception as e:
            logger.error(f"Failed to generate chart for {signal.symbol}: {e}")
        
        asyncio.create_task(bot.send_alert(title, body, color, channel_id=target_channel, image_buffer=image_buffer))
        return {"status": "processed", "definition": definition.display_name}

from datetime import date

class DatePayload(BaseModel):
    target_date: Optional[date] = None

@app.post("/send-morning-summary")
async def trigger_morning_summary(payload: DatePayload = None):
    """Trigger the morning summary report (called by scheduler)."""
    # Trigger bot method in background
    target = payload.target_date if payload else None
    asyncio.create_task(bot.send_morning_summary(target_date=target))
    return {"status": "triggered", "target_date": target}

def _get_channel_for_category(category: str, level: str):
    target_channel = settings.DISCORD_CHANNEL_FALLBACK
    cat = category.lower()
    
    # 1. Error / System Routing
    if (level == "error" or level == "critical") and settings.DISCORD_CHANNEL_SYSTEM:
        target_channel = settings.DISCORD_CHANNEL_SYSTEM
    # 2. Category Routing
    elif cat == "ma" and settings.DISCORD_CHANNEL_MA:
        target_channel = settings.DISCORD_CHANNEL_MA
    elif cat == "rsi" and settings.DISCORD_CHANNEL_RSI:
        target_channel = settings.DISCORD_CHANNEL_RSI
    elif cat == "macd" and settings.DISCORD_CHANNEL_MACD:
        target_channel = settings.DISCORD_CHANNEL_MACD
    elif (cat == "volume" or cat == "vol") and settings.DISCORD_CHANNEL_VOL:
        target_channel = settings.DISCORD_CHANNEL_VOL
        
    return target_channel
