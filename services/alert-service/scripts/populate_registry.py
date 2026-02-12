"""
Populate signal registry with currently supported scanner signals.

Current support is intentionally limited to ESM and PF strategy signals.
"""
import asyncio
import os
import sys
from collections import defaultdict

from sqlalchemy import select

# Add parent dir to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.database import AsyncSessionLocal
from src.models import SignalRegistry


INITIAL_SIGNALS = [
    {
        "signal_code": "ESM_ENTRY",
        "display_name": "ESM Entry",
        "emoji": "\U0001F402",
        "severity": "high",
        "template_text": "ESM Entry: Short-term momentum is bullish.",
        "action_text": "Potential Entry (Long)",
    },
    {
        "signal_code": "ESM_EXIT",
        "display_name": "ESM Exit",
        "emoji": "\U0001F43B",
        "severity": "high",
        "template_text": "ESM Exit: Short-term momentum is bearish.",
        "action_text": "Potential Exit.",
    },
    {
        "signal_code": "PF_ENTRY",
        "display_name": "PF Entry",
        "emoji": "\U0001F402",
        "severity": "high",
        "template_text": "PF Entry: Short-term momentum is bullish.",
        "action_text": "Potential Entry (Long)",
    },
    {
        "signal_code": "PF_EXIT",
        "display_name": "PF Exit",
        "emoji": "\U0001F43B",
        "severity": "high",
        "template_text": "PF Exit: Short-term momentum is bearish.",
        "action_text": "Potential Exit.",
    },
]


def validate_entry_exit_pairs(signals: list[dict]) -> None:
    """
    Enforce paired strategy signals for codes that follow <STRATEGY>_ENTRY/EXIT.
    """
    strategy_pairs = defaultdict(set)
    for sig in signals:
        code = sig.get("signal_code", "").upper()
        if code.endswith("_ENTRY"):
            strategy_pairs[code[:-6]].add("ENTRY")
        elif code.endswith("_EXIT"):
            strategy_pairs[code[:-5]].add("EXIT")

    missing = [name for name, pair in strategy_pairs.items() if pair != {"ENTRY", "EXIT"}]
    if missing:
        raise ValueError(f"Missing ENTRY/EXIT pair for strategy codes: {', '.join(sorted(missing))}")


async def populate():
    print("Populating Signal Registry...")
    validate_entry_exit_pairs(INITIAL_SIGNALS)
    active_codes = {sig["signal_code"] for sig in INITIAL_SIGNALS}

    async with AsyncSessionLocal() as session:
        for sig in INITIAL_SIGNALS:
            stmt = select(SignalRegistry).where(SignalRegistry.signal_code == sig["signal_code"])
            result = await session.execute(stmt)
            existing = result.scalars().first()

            if not existing:
                print(f"Creating: {sig['signal_code']}")
                session.add(SignalRegistry(**sig))
            else:
                print(f"Updating: {sig['signal_code']}")
                for k, v in sig.items():
                    setattr(existing, k, v)
                existing.enabled = True

        # Disable legacy/non-supported signal codes currently in the table.
        all_signals = (await session.execute(select(SignalRegistry))).scalars().all()
        for row in all_signals:
            if row.signal_code not in active_codes and row.enabled:
                print(f"Disabling unsupported signal: {row.signal_code}")
                row.enabled = False

        await session.commit()
    print("Done!")


if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(populate())
