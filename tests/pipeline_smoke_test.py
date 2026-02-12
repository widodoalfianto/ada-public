"""
Pipeline Smoke Test Suite

Lightweight end-to-end validation for the live pipeline:
1) data update
2) indicator calculation
3) ESM + PF scans
4) morning summary trigger

Run with: pytest tests/pipeline_smoke_test.py -v
"""
import os
from datetime import date, datetime, timedelta
from typing import Any, Dict, Optional

import pytest
try:
    import httpx
except ImportError:  # pragma: no cover - dependency present in service containers
    httpx = None


def _env_port(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


SERVICE_URLS = {
    "data-service": f"http://localhost:{_env_port('DATA_PORT', 9001)}",
    "indicator-service": f"http://localhost:{_env_port('INDICATOR_PORT', 9002)}",
    "scanner-service": f"http://localhost:{_env_port('SCANNER_PORT', 9003)}",
    "alert-service": f"http://localhost:{_env_port('ALERT_PORT', 9004)}",
}

DOCKER_SERVICE_URLS = {
    "data-service": "http://data-service:8000",
    "indicator-service": "http://indicator-service:8000",
    "scanner-service": "http://scanner-service:8000",
    "alert-service": "http://alert-service:8000",
}


def _running_in_docker() -> bool:
    if os.environ.get("USE_DOCKER", "").lower() in ("1", "true", "yes"):
        return True
    return os.path.exists("/.dockerenv")


def get_service_url(service_name: str, use_docker: Optional[bool] = None) -> str:
    if use_docker is None:
        use_docker = _running_in_docker()
    urls = DOCKER_SERVICE_URLS if use_docker else SERVICE_URLS
    return urls.get(service_name, "")


def _parse_date(value: str) -> Optional[date]:
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None


def _parse_int(value: str, default: Optional[int] = None) -> Optional[int]:
    if value is None or value == "":
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _require_httpx() -> None:
    if httpx is None:
        pytest.skip("httpx is not installed in this Python environment")


def _safe_json(response) -> Dict[str, Any]:
    try:
        return response.json()
    except Exception:
        return {"raw_text": response.text}


class TestServiceHealth:
    @pytest.mark.asyncio
    async def test_data_service_health(self):
        _require_httpx()
        async with httpx.AsyncClient(timeout=5.0) as client:
            try:
                response = await client.get(f"{get_service_url('data-service')}/")
                assert response.status_code == 200
            except httpx.ConnectError:
                pytest.skip("Data service not running")

    @pytest.mark.asyncio
    async def test_indicator_service_health(self):
        _require_httpx()
        async with httpx.AsyncClient(timeout=5.0) as client:
            try:
                response = await client.get(f"{get_service_url('indicator-service')}/")
                assert response.status_code == 200
            except httpx.ConnectError:
                pytest.skip("Indicator service not running")

    @pytest.mark.asyncio
    async def test_scanner_service_health(self):
        _require_httpx()
        async with httpx.AsyncClient(timeout=5.0) as client:
            try:
                response = await client.get(f"{get_service_url('scanner-service')}/")
                assert response.status_code == 200
            except httpx.ConnectError:
                pytest.skip("Scanner service not running")

    @pytest.mark.asyncio
    async def test_alert_service_health(self):
        _require_httpx()
        async with httpx.AsyncClient(timeout=5.0) as client:
            try:
                response = await client.get(f"{get_service_url('alert-service')}/")
                assert response.status_code in [200, 404]
            except httpx.ConnectError:
                pytest.skip("Alert service not running")


async def run_simulated_daily_flow(target_date: Optional[date] = None) -> Dict[str, Any]:
    """
    Run a smoke daily flow for a specific date:
    1) daily-update
    2) daily-calculate
    3) run-esm-scan + run-pf-scan
    4) send-morning-summary (next day)
    """
    _require_httpx()
    sim_date = target_date or (date.today() - timedelta(days=1))
    summary_date = sim_date + timedelta(days=1)
    default_lookback = 7 if sim_date.weekday() >= 5 else 0
    lookback_days = _parse_int(os.environ.get("SIMULATION_LOOKBACK_DAYS", ""), default_lookback)

    results: Dict[str, Any] = {
        "target_date": sim_date.isoformat(),
        "summary_date": summary_date.isoformat(),
        "lookback_days": lookback_days,
        "steps": {},
    }

    async with httpx.AsyncClient(timeout=600.0) as client:
        resp = await client.post(
            f"{get_service_url('data-service')}/api/daily-update",
            json={"target_date": sim_date.isoformat(), "lookback_days": lookback_days},
        )
        results["steps"]["daily_update"] = {"status_code": resp.status_code, "body": _safe_json(resp)}

        resp = await client.post(
            f"{get_service_url('indicator-service')}/api/daily-calculate",
            json={"target_date": sim_date.isoformat()},
        )
        results["steps"]["daily_calculate"] = {"status_code": resp.status_code, "body": _safe_json(resp)}

        resp = await client.post(
            f"{get_service_url('scanner-service')}/run-esm-scan",
            json={"target_date": sim_date.isoformat()},
        )
        results["steps"]["esm_scan"] = {"status_code": resp.status_code, "body": _safe_json(resp)}

        resp = await client.post(
            f"{get_service_url('scanner-service')}/run-pf-scan",
            json={"target_date": sim_date.isoformat()},
        )
        results["steps"]["pf_scan"] = {"status_code": resp.status_code, "body": _safe_json(resp)}

        resp = await client.post(
            f"{get_service_url('alert-service')}/send-morning-summary",
            json={"target_date": summary_date.isoformat()},
        )
        results["steps"]["morning_summary"] = {"status_code": resp.status_code, "body": _safe_json(resp)}

    return results


class TestPipelineSmoke:
    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_simulated_daily_flow(self):
        _require_httpx()
        sim_date = _parse_date(os.environ.get("SIMULATION_DATE", ""))
        try:
            results = await run_simulated_daily_flow(target_date=sim_date)
        except httpx.ConnectError:
            pytest.skip("One or more services are not running")

        for step_name, info in results["steps"].items():
            assert info["status_code"] in [200, 202], f"{step_name} failed: {info}"


async def run_manual_smoke():
    if httpx is None:
        print("httpx is not installed in this Python environment.")
        return

    print("\n" + "=" * 80)
    print("PIPELINE SMOKE TEST (Manual Mode)")
    print(f"Started: {datetime.now()}")
    print("=" * 80)

    services_to_check = ["data-service", "indicator-service", "scanner-service", "alert-service"]
    async with httpx.AsyncClient(timeout=5.0) as client:
        print("\n[Service Health Checks]")
        for service in services_to_check:
            try:
                response = await client.get(f"{get_service_url(service)}/")
                status = "Healthy" if response.status_code in [200, 404] else f"Status {response.status_code}"
                print(f"  {service}: {status}")
            except Exception as e:
                print(f"  {service}: Error - {e}")

    run_simulation = os.environ.get("RUN_SIMULATION", "").lower() in ("1", "true", "yes")
    sim_date = _parse_date(os.environ.get("SIMULATION_DATE", ""))
    if run_simulation or sim_date:
        resolved_date = sim_date or (date.today() - timedelta(days=1))
        print("\n" + "=" * 80)
        print(f"SIMULATED DAILY FLOW (target_date={resolved_date})")
        print("=" * 80)
        results = await run_simulated_daily_flow(target_date=sim_date)
        print(f"  lookback_days: {results.get('lookback_days')}")
        for step, info in results["steps"].items():
            print(f"  {step}: {info['status_code']}")

    print("\n" + "=" * 80)
    print("For full smoke run: pytest tests/pipeline_smoke_test.py -v")
    print("=" * 80)


if __name__ == "__main__":
    import asyncio

    asyncio.run(run_manual_smoke())
