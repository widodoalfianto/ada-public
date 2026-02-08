"""
Script to populate the Signal Registry with initial definitions.
"""
import asyncio
import sys
import os

# Add parent dir to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.database import AsyncSessionLocal
from src.models import SignalRegistry
from sqlalchemy import select

INITIAL_SIGNALS = [
    {
        "signal_code": "SIG_GOLDEN_CROSS",
        "display_name": "Golden Cross",
        "emoji": "🐂",
        "severity": "high",
        "template_text": "EMA 9 ({data[ema_9]}) crossed above SMA 20 ({data[sma_20]}). Short-term momentum is bullish.",
        "action_text": "Potential Entry (Long)"
    },
    {
        "signal_code": "GOLDEN_CROSS",
        "display_name": "Golden Cross",
        "emoji": "🐂",
        "severity": "high",
        "template_text": "EMA 9 ({data[ema_9]}) crossed above SMA 20 ({data[sma_20]}). Short-term momentum is bullish.",
        "action_text": "Potential Entry (Long)"
    },
    {
        "signal_code": "SIG_DEATH_CROSS",
        "display_name": "Death Cross",
        "emoji": "🐻",
        "severity": "high",
        "template_text": "EMA 9 ({data[ema_9]}) crossed below SMA 20 ({data[sma_20]}). Short-term momentum is bearish.",
        "action_text": "Consider Exit/Short"
    },
    {
        "signal_code": "DEATH_CROSS",
        "display_name": "Death Cross",
        "emoji": "🐻",
        "severity": "high",
        "template_text": "EMA 9 ({data[ema_9]}) crossed below SMA 20 ({data[sma_20]}). Short-term momentum is bearish.",
        "action_text": "Consider Exit/Short"
    },
    {
        "signal_code": "SIG_MACD_BULLISH",
        "display_name": "MACD Bullish Cross",
        "emoji": "🟢",
        "severity": "medium",
        "template_text": "MACD Line ({data[macd_line]}) crossed above Signal ({data[macd_signal]}).",
        "action_text": "Bullish Confirmation"
    },
    {
        "signal_code": "SIG_MACD_BEARISH",
        "display_name": "MACD Bearish Cross",
        "emoji": "🔴",
        "severity": "medium",
        "template_text": "MACD Line ({data[macd_line]}) crossed below Signal ({data[macd_signal]}).",
        "action_text": "Bearish Caution"
    },
    {
        "signal_code": "SIG_RSI_OVERBOUGHT",
        "display_name": "RSI Overbought",
        "emoji": "📉",
        "severity": "medium",
        "template_text": "RSI is {data[rsi_14]:.2f} (Above 70). Asset may be overextended.",
        "action_text": "Watch for Reversal"
    },
    {
        "signal_code": "SIG_RSI_OVERSOLD",
        "display_name": "RSI Oversold",
        "emoji": "📈",
        "severity": "medium",
        "template_text": "RSI is {data[rsi_14]:.2f} (Below 30). Asset may be undervalues.",
        "action_text": "Watch for Bounce"
    },
    {
        "signal_code": "SIG_VOLUME_SPIKE",
        "display_name": "Volume Spike",
        "emoji": "👀",
        "severity": "medium",
        "template_text": "Volume {data[volume]:,} is > 2.5x Average ({data[sma_vol_20]:,.0f}).",
        "action_text": "Check for Breakout"
    }
]

async def populate():
    print("Populating Signal Registry...")
    async with AsyncSessionLocal() as session:
        for sig in INITIAL_SIGNALS:
            # Check exist
            stmt = select(SignalRegistry).where(SignalRegistry.signal_code == sig["signal_code"])
            result = await session.execute(stmt)
            existing = result.scalars().first()
            
            if not existing:
                print(f"Creating: {sig['signal_code']}")
                new_sig = SignalRegistry(**sig)
                session.add(new_sig)
            else:
                print(f"Updating: {sig['signal_code']}")
                for k, v in sig.items():
                    setattr(existing, k, v)
        
        await session.commit()
    print("Done!")

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(populate())
