import argparse
import asyncio
from datetime import datetime

from src.signal_worker import SignalWorker


async def run_scan(strategy: str | None, target_date: str | None, send_notifications: bool = True) -> None:
    worker = SignalWorker()
    parsed_date = datetime.strptime(target_date, "%Y-%m-%d").date() if target_date else None

    if strategy:
        await worker.run_strategy(
            strategy.upper(),
            target_date=parsed_date,
            send_notifications=send_notifications,
        )
    else:
        await worker.run_all(target_date=parsed_date, send_notifications=send_notifications)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run scanner strategies manually")
    parser.add_argument(
        "--strategy",
        choices=["ESM", "PF"],
        default=None,
        help="Run one strategy only (default: run all enabled strategies)",
    )
    parser.add_argument(
        "--date",
        dest="target_date",
        default=None,
        help="Target date in YYYY-MM-DD",
    )
    parser.add_argument(
        "--no-notify",
        action="store_true",
        help="Record signals without sending Discord/email alerts",
    )
    args = parser.parse_args()

    asyncio.run(run_scan(args.strategy, args.target_date, send_notifications=not args.no_notify))


if __name__ == "__main__":
    main()
