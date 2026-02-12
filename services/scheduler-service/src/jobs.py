"""
Daily data pipeline jobs for scheduler service
"""
import asyncio
import logging
from datetime import datetime

import pytz
try:
    import pandas_market_calendars as mcal
except ImportError:  # pragma: no cover - handled at runtime/deployment
    mcal = None

logger = logging.getLogger(__name__)

RETRY_DELAYS_SECONDS = [300, 600, 1200, 2400, 3600]  # 5m, 10m, 20m, 40m, 60m


def _is_success_status(result: dict) -> bool:
    status = str(result.get("status", "")).lower()
    return status in {"completed", "success", "triggered", "queued"}


def _format_delay(seconds: int) -> str:
    if seconds % 3600 == 0:
        return f"{seconds // 3600}h"
    if seconds % 60 == 0:
        return f"{seconds // 60}m"
    return f"{seconds}s"


async def _send_system_alert(job_name: str, message: str, severity: str = "critical") -> None:
    import httpx
    from src.config import settings

    payload = {
        "title": f"{job_name} failed",
        "message": message,
        "severity": severity,
        "source": "scheduler-service",
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(f"{settings.ALERT_SERVICE_URL}/system-alert", json=payload)
            if response.status_code != 200:
                logger.error(
                    "Failed to send system alert for %s: HTTP %s - %s",
                    job_name,
                    response.status_code,
                    response.text,
                )
                return

            body = response.json() if response.content else {}
            if str(body.get("status", "")).lower() not in {"queued", "success", "triggered"}:
                logger.error(
                    "System alert endpoint returned non-success for %s: %s",
                    job_name,
                    body,
                )
    except Exception as e:
        logger.error(f"System alert delivery failed for {job_name}: {e}", exc_info=True)


async def _post_json_with_retry(
    url: str,
    *,
    job_name: str,
    timeout_seconds: float,
    payload: dict | None = None,
    validate_result=_is_success_status,
) -> dict | None:
    """
    POST with retry/backoff for unstable upstream service calls.

    Tries once + 5 retries with exponential backoff capped at 1 hour.
    """
    import httpx

    max_attempts = len(RETRY_DELAYS_SECONDS) + 1
    last_error: Exception | None = None

    for attempt in range(1, max_attempts + 1):
        try:
            async with httpx.AsyncClient(timeout=timeout_seconds) as client:
                response = await client.post(url, json=payload)

            if response.status_code != 200:
                raise RuntimeError(f"HTTP {response.status_code}: {response.text[:500]}")

            result = response.json() if response.content else {}
            if validate_result and not validate_result(result):
                raise RuntimeError(f"Unexpected response payload: {result}")

            if attempt > 1:
                logger.info(f"{job_name}: succeeded on attempt {attempt}/{max_attempts}.")
            return result
        except Exception as e:
            last_error = e
            if attempt < max_attempts:
                delay = RETRY_DELAYS_SECONDS[attempt - 1]
                logger.warning(
                    "%s: attempt %s/%s failed (%s). Retrying in %s.",
                    job_name,
                    attempt,
                    max_attempts,
                    e,
                    _format_delay(delay),
                )
                await asyncio.sleep(delay)
                continue

            error_text = f"{job_name} failed after {max_attempts} attempts. Last error: {e}"
            logger.error(error_text, exc_info=True)
            await _send_system_alert(job_name, error_text, severity="critical")
            return None

    # Defensive fallback; loop always returns above.
    if last_error:
        await _send_system_alert(
            job_name,
            f"{job_name} failed after retries. Last error: {last_error}",
            severity="critical",
        )
    return None


def is_trading_day() -> bool:
    """
    Check if today is a valid trading day using pandas_market_calendars.
    """
    if mcal is None:
        raise RuntimeError("pandas_market_calendars is required for trading-day checks")

    nyse = mcal.get_calendar("NYSE")
    now = datetime.now(pytz.timezone("US/Eastern"))
    today_str = now.strftime("%Y-%m-%d")
    schedule = nyse.schedule(start_date=today_str, end_date=today_str)
    return not schedule.empty


async def daily_price_fetch():
    if not is_trading_day():
        logger.info("Daily price fetch: Not a trading day. Skipping.")
        return

    """
    Fetch daily price data for all active stocks.
    Runs Monday-Friday at 5:00 PM EST (after market close).
    """
    logger.info("=" * 80)
    logger.info(f"[{datetime.now()}] Starting daily price fetch...")
    logger.info("=" * 80)

    from src.config import settings

    result = await _post_json_with_retry(
        f"{settings.DATA_SERVICE_URL}/api/daily-update",
        job_name="daily_price_fetch",
        timeout_seconds=600.0,
    )
    if result is None:
        return

    logger.info("Price fetch complete.")
    logger.info(f"   Stocks processed: {result.get('total_stocks', 0)}")
    logger.info(f"   Success: {result.get('success_count', 0)}")
    logger.info(f"   Failures: {result.get('failure_count', 0)}")
    logger.info(f"   Duration: {result.get('duration_seconds', 0)}s")

    # Alert if high failure rate
    if result.get('failure_count', 0) > result.get('total_stocks', 0) * 0.1:
        logger.error("WARNING: High failure rate detected!")


async def daily_indicator_calculation():
    if not is_trading_day():
        logger.info("Daily indicator calculation: Not a trading day. Skipping.")
        return

    """
    Calculate daily indicators for all active stocks.
    Runs Monday-Friday at 5:15 PM EST (after price fetch).
    """
    logger.info("=" * 80)
    logger.info(f"[{datetime.now()}] Starting daily indicator calculation...")
    logger.info("=" * 80)

    from src.config import settings

    result = await _post_json_with_retry(
        f"{settings.INDICATOR_SERVICE_URL}/api/daily-calculate",
        job_name="daily_indicator_calculation",
        timeout_seconds=300.0,
    )
    if result is None:
        return

    logger.info("Indicator calculation complete.")
    logger.info(
        f"   Stocks processed: {result.get('success_count', 0)}/{result.get('total_stocks', 0)}"
    )
    logger.info(f"   Indicators created: {result.get('indicators_created', 0)}")
    logger.info(f"   Skipped: {result.get('skipped_count', 0)}")
    logger.info(f"   Duration: {result.get('duration_seconds', 0)}s")

    # Alert if high failure rate
    if result.get('failure_count', 0) > result.get('total_stocks', 0) * 0.05:
        logger.error("WARNING: High failure rate detected!")


async def weekly_data_cleanup():
    """
    Trigger weekly data cleanup (pruning old records).
    Runs Sundays at 2:00 AM EST.
    """
    logger.info("=" * 80)
    logger.info(f"[{datetime.now()}] Starting weekly data cleanup...")
    logger.info("=" * 80)

    from src.config import settings

    result = await _post_json_with_retry(
        f"{settings.DATA_SERVICE_URL}/api/cleanup",
        job_name="weekly_data_cleanup",
        timeout_seconds=300.0,
    )
    if result is None:
        return

    logger.info("Data cleanup complete.")
    logger.info(f"   Indicators Deleted: {result.get('indicators_deleted', 0)}")
    logger.info(f"   Alerts Deleted: {result.get('alerts_deleted', 0)}")
    logger.info(f"   Duration: {result.get('duration_seconds', 0)}s")


async def evening_esm_scan():
    if not is_trading_day():
        logger.info("Evening ESM scan: Not a trading day. Skipping.")
        return

    """
    Run EMA/SMA crossover scan (ESM).
    Runs Monday-Friday at 5:30 PM EST (after indicators calculated).
    """
    logger.info("=" * 80)
    logger.info(f"[{datetime.now()}] Starting Evening ESM Scan...")
    logger.info("=" * 80)

    from src.config import settings

    result = await _post_json_with_retry(
        f"{settings.SCANNER_SERVICE_URL}/run-esm-scan",
        job_name="evening_esm_scan",
        timeout_seconds=600.0,
        validate_result=lambda _: True,
    )
    if result is None:
        return

    logger.info("ESM scan triggered successfully.")


async def evening_pf_scan():
    if not is_trading_day():
        logger.info("Evening PF scan: Not a trading day. Skipping.")
        return

    """
    Run PF strategy scan.
    Runs Monday-Friday after ESM scan.
    """
    logger.info("=" * 80)
    logger.info(f"[{datetime.now()}] Starting Evening PF Scan...")
    logger.info("=" * 80)

    from src.config import settings

    result = await _post_json_with_retry(
        f"{settings.SCANNER_SERVICE_URL}/run-pf-scan",
        job_name="evening_pf_scan",
        timeout_seconds=600.0,
        validate_result=lambda _: True,
    )
    if result is None:
        return

    logger.info("PF scan triggered successfully.")


async def morning_summary_report():
    if not is_trading_day():
        logger.info("Morning summary: Not a trading day. Skipping.")
        return

    """
    Trigger Morning Summary Report.
    Runs Monday-Friday at 8:30 AM EST (Pre-market).
    """
    logger.info("=" * 80)
    logger.info(f"[{datetime.now()}] Triggering Morning Summary...")
    logger.info("=" * 80)

    from src.config import settings

    result = await _post_json_with_retry(
        f"{settings.ALERT_SERVICE_URL}/send-morning-summary",
        job_name="morning_summary_report",
        timeout_seconds=60.0,
        validate_result=lambda _: True,
    )
    if result is None:
        return

    logger.info("Morning summary triggered successfully.")
