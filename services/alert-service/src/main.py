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


def _is_entry_signal(signal_code: str) -> bool:
    code = signal_code.upper()
    return code.endswith("_ENTRY")


def _is_exit_signal(signal_code: str) -> bool:
    code = signal_code.upper()
    return code.endswith("_EXIT")


def _is_esm_signal(signal_code: str) -> bool:
    code = signal_code.upper()
    return code.startswith("ESM_")


def _is_pf_signal(signal_code: str) -> bool:
    code = signal_code.upper()
    return code.startswith("PF_")


def _esm_copy_for_signal(signal_code: str, _data: Dict[str, Any]) -> tuple[Optional[str], Optional[str]]:
    """
    Canonical ESM copy aligned to signal registry messaging.
    """
    code = signal_code.upper()

    if code == "ESM_ENTRY":
        return (
            "ESM Entry: Short-term momentum is bullish.",
            "Potential Entry (Long)",
        )

    if code == "ESM_EXIT":
        return ("ESM Exit: Short-term momentum is bearish.", "Potential Exit.")

    return (None, None)

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
        if not (_is_esm_signal(signal.signal_code) or _is_pf_signal(signal.signal_code)):
            return {"status": "ignored", "reason": "unsupported_signal_family"}
            
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

        # Enforce canonical copy for ESM entry/exit signals.
        action_text = definition.action_text
        if _is_esm_signal(signal.signal_code):
            esm_message, esm_action = _esm_copy_for_signal(signal.signal_code, signal.data)
            if esm_message:
                message_body = esm_message
            if esm_action:
                action_text = esm_action

        # Construct Embed Details
        emoji = definition.emoji if definition.emoji else ""
        title = f"{emoji} {definition.display_name}: {signal.symbol}"
        if settings.TEST_MODE:
            title = f"[TEST] {title}"
            
        # Color Logic
        color = 0x00ff00  # Default Green
        sev = definition.severity.lower()
        if _is_exit_signal(signal.signal_code):
            color = 0xff0000
        elif _is_entry_signal(signal.signal_code):
            color = 0x00ff00
        elif sev == "warning":
            color = 0xffff00
            
        # Body Construction
        body = f"\U0001F552 <t:{signal.timestamp}:f>\n\n"
        body += f"Signal: {message_body}\n"
        
        if action_text:
            body += f"Action: {action_text}\n"
        # Determine Category for Routing based on signal code
        category = "general"
        if _is_pf_signal(signal.signal_code): 
            category = "pf"
        elif _is_esm_signal(signal.signal_code):
            category = "esm"
        
        target_channel = _get_channel_for_category(category, sev)
        
        # Determine which indicators to show on chart
        indicators_to_show = None # Default: Show all
        show_volume_panel = True # Default: Show volume
        
        # User Logic: Filter noise based on signal type
        if _is_esm_signal(signal.signal_code):
            # User specifically requested ONLY EMA9 and SMA20, and NO Volume, NO SMA50/200
            indicators_to_show = ['ema_9', 'sma_20']
            show_volume_panel = False
        elif _is_pf_signal(signal.signal_code):
            # PF alerts should include a chart with key trend overlays.
            indicators_to_show = ['ema_9', 'sma_20', 'sma_50']
            show_volume_panel = True
        
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


class SystemAlertPayload(BaseModel):
    title: str
    message: str
    severity: str = "error"
    source: Optional[str] = None


def _severity_color(level: str) -> int:
    sev = level.lower()
    if sev == "critical":
        return 0x8B0000
    if sev == "error":
        return 0xFF0000
    if sev == "warning":
        return 0xFFA500
    return 0x3498DB


@app.post("/system-alert")
async def send_system_alert(payload: SystemAlertPayload):
    """
    Send operational alerts directly to developer-only system channel.
    """
    if not settings.DISCORD_CHANNEL_SYSTEM:
        logger.error("System alert rejected: DISCORD_CHANNEL_SYSTEM is not configured")
        return {"status": "failed", "reason": "system_channel_not_configured"}

    ts = int(datetime.now().timestamp())
    source = f"\nSource: {payload.source}" if payload.source else ""
    body = f"\U0001F552 <t:{ts}:f>\n\n{payload.message}{source}"
    title = f"\u26A0\uFE0F {payload.title}"
    if settings.TEST_MODE:
        title = f"[TEST] {title}"

    asyncio.create_task(
        bot.send_alert(
            title=title,
            message=body,
            color=_severity_color(payload.severity),
            channel_id=settings.DISCORD_CHANNEL_SYSTEM,
            image_buffer=None,
        )
    )
    return {"status": "queued", "channel": "system"}

def _get_channel_for_category(category: str, level: str):
    target_channel = settings.DISCORD_CHANNEL_FALLBACK
    cat = category.lower()
    
    # 1. Error / System Routing
    if (level == "error" or level == "critical") and settings.DISCORD_CHANNEL_SYSTEM:
        target_channel = settings.DISCORD_CHANNEL_SYSTEM
    # 2. Category Routing
    elif cat == "esm" and settings.DISCORD_CHANNEL_ESM:
        target_channel = settings.DISCORD_CHANNEL_ESM
    elif cat == "pf" and settings.DISCORD_CHANNEL_PF:
        target_channel = settings.DISCORD_CHANNEL_PF

    return target_channel

