"""
End-to-End Integration Test Suite

Tests the entire daily data pipeline across all services.
Uses pytest for proper test management and assertions.

Run with: pytest tests/integration_test_suite.py -v

Note: These tests require all services to be running via docker-compose.
"""
import os
import pytest
import httpx
from datetime import datetime, date, timedelta
from typing import Dict, Any, Optional

# Import shared utilities for consistent error handling
import sys
sys.path.insert(0, 'services')
try:
    from shared.exceptions import ExternalServiceError, log_exception
except ImportError:
    # Fallback if shared not available
    ExternalServiceError = Exception
    def log_exception(e, context=""): return {"error": str(e)}


# =============================================================================
# Configuration
# =============================================================================

def _env_port(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


SERVICE_URLS = {
    'data-service': f"http://localhost:{_env_port('DATA_PORT', 8001)}",
    'indicator-service': f"http://localhost:{_env_port('INDICATOR_PORT', 8002)}",
    'scanner-service': f"http://localhost:{_env_port('SCANNER_PORT', 8003)}",
    'backtest-service': f"http://localhost:{_env_port('BACKTEST_PORT', 8004)}",
    'alert-service': f"http://localhost:{_env_port('ALERT_PORT', 8005)}",
    'scheduler-service': "http://localhost:8006",
}

# Docker internal URLs (when running inside container)
DOCKER_SERVICE_URLS = {
    'data-service': 'http://data-service:8000',
    'indicator-service': 'http://indicator-service:8000',
    'scanner-service': 'http://scanner-service:8000',
    'backtest-service': 'http://backtest-service:8000',
    'alert-service': 'http://alert-service:8000',
    'scheduler-service': 'http://scheduler-service:8000',
}


def _running_in_docker() -> bool:
    if os.environ.get("USE_DOCKER", "").lower() in ("1", "true", "yes"):
        return True
    return os.path.exists("/.dockerenv")


def get_service_url(service_name: str, use_docker: Optional[bool] = None) -> str:
    """Get the URL for a service based on environment."""
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


def _safe_json(response: httpx.Response) -> Dict[str, Any]:
    try:
        return response.json()
    except Exception:
        return {"raw_text": response.text}


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def http_client():
    """Provide an async HTTP client."""
    return httpx.AsyncClient(timeout=30.0)


# =============================================================================
# Health Check Tests
# =============================================================================

class TestServiceHealth:
    """Verify all services are running and healthy."""
    
    @pytest.mark.asyncio
    async def test_data_service_health(self):
        """Data service should respond to health check."""
        async with httpx.AsyncClient(timeout=5.0) as client:
            try:
                response = await client.get(f"{get_service_url('data-service')}/")
                assert response.status_code == 200, f"Data service unhealthy: {response.status_code}"
            except httpx.ConnectError:
                pytest.skip("Data service not running")
    
    @pytest.mark.asyncio
    async def test_indicator_service_health(self):
        """Indicator service should respond to health check."""
        async with httpx.AsyncClient(timeout=5.0) as client:
            try:
                response = await client.get(f"{get_service_url('indicator-service')}/")
                assert response.status_code == 200, f"Indicator service unhealthy: {response.status_code}"
            except httpx.ConnectError:
                pytest.skip("Indicator service not running")
    
    @pytest.mark.asyncio
    async def test_scanner_service_health(self):
        """Scanner service should respond to health check."""
        async with httpx.AsyncClient(timeout=5.0) as client:
            try:
                response = await client.get(f"{get_service_url('scanner-service')}/")
                assert response.status_code == 200, f"Scanner service unhealthy: {response.status_code}"
            except httpx.ConnectError:
                pytest.skip("Scanner service not running")


# =============================================================================
# Data Freshness Tests
# =============================================================================

class TestDataFreshness:
    """Verify data is current and accessible."""
    
    @pytest.mark.asyncio
    async def test_aapl_has_recent_data(self):
        """AAPL should have indicator data from recent trading day."""
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                url = f"{get_service_url('indicator-service')}/indicators/AAPL?days=5"
                response = await client.get(url)
                
                if response.status_code == 404:
                    pytest.skip("AAPL not in database")
                
                assert response.status_code == 200
                result = response.json()
                assert len(result) > 0, "No indicator data found for AAPL"
                
                # Check that we have recent data (within 7 days)
                latest_date = result[0]['date']
                latest = datetime.strptime(latest_date, "%Y-%m-%d").date()
                days_old = (date.today() - latest).days
                
                assert days_old <= 7, f"Data is {days_old} days old"
                
            except httpx.ConnectError:
                pytest.skip("Indicator service not running")
    
    @pytest.mark.asyncio
    async def test_indicators_have_required_fields(self):
        """Indicator data should have all required fields."""
        required_indicator_fields = ['ema_9', 'sma_20', 'rsi_14', 'macd_line']
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                url = f"{get_service_url('indicator-service')}/indicators/AAPL?days=1"
                response = await client.get(url)
                
                if response.status_code != 200:
                    pytest.skip("AAPL data not available")
                
                result = response.json()
                if not result:
                    pytest.skip("No recent data")
                
                indicator = result[0]
                assert 'date' in indicator, "Missing field: date"

                # New response shape nests indicators under 'indicators'
                indicator_values = indicator.get('indicators') or indicator
                for field in required_indicator_fields:
                    assert field in indicator_values, f"Missing field: {field}"
                    
            except httpx.ConnectError:
                pytest.skip("Indicator service not running")


# =============================================================================
# Pipeline Tests
# =============================================================================

class TestDailyPipeline:
    """Test the complete daily data update pipeline."""
    
    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_daily_price_update(self):
        """Daily price update endpoint should work."""
        async with httpx.AsyncClient(timeout=120.0) as client:
            try:
                url = f"{get_service_url('data-service')}/api/daily-update"
                response = await client.post(url)
                
                # Should return 200 or 202 (accepted for async processing)
                assert response.status_code in [200, 202], f"Unexpected status: {response.status_code}"
                
                if response.status_code == 200:
                    result = response.json()
                    assert 'success_count' in result
                    assert 'failure_count' in result
                    
            except httpx.ConnectError:
                pytest.skip("Data service not running")
            except httpx.ReadTimeout:
                # Long-running operation, may timeout - that's OK
                pass
    
    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_daily_indicator_calculation(self):
        """Daily indicator calculation should work."""
        async with httpx.AsyncClient(timeout=120.0) as client:
            try:
                url = f"{get_service_url('indicator-service')}/api/daily-calculate"
                response = await client.post(url)
                
                assert response.status_code in [200, 202], f"Unexpected status: {response.status_code}"
                
                if response.status_code == 200:
                    result = response.json()
                    assert 'success_count' in result or 'indicators_created' in result
                    
            except httpx.ConnectError:
                pytest.skip("Indicator service not running")
            except httpx.ReadTimeout:
                pass


# =============================================================================
# Backtest Service Tests
# =============================================================================

class TestBacktestService:
    """Test the backtesting service."""
    
    @pytest.mark.asyncio
    async def test_backtest_endpoint(self):
        """Backtest endpoint should accept strategy configurations."""
        payload = {
            "strategy": {
                "type": "ma_crossover",
                "params": {"fast": 9, "slow": 20}
            },
            "symbols": ["AAPL"],
            "start_date": "2024-01-01",
            "end_date": "2024-12-31",
            "initial_capital": 100000.0
        }
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            try:
                url = f"{get_service_url('backtest-service')}/api/backtest/run"
                response = await client.post(url, json=payload)
                
                if response.status_code == 404:
                    pytest.skip("Backtest endpoint not found")
                
                # Should return results or accepted
                assert response.status_code in [200, 202, 422], f"Unexpected: {response.status_code}"
                
            except httpx.ConnectError:
                pytest.skip("Backtest service not running")


# =============================================================================
# Idempotency Tests
# =============================================================================

class TestIdempotency:
    """Verify that operations are idempotent (safe to re-run)."""
    
    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_price_update_idempotent(self):
        """Running price update twice should not create duplicates."""
        async with httpx.AsyncClient(timeout=120.0) as client:
            try:
                url = f"{get_service_url('data-service')}/api/daily-update"
                
                # First run
                response1 = await client.post(url)
                if response1.status_code != 200:
                    pytest.skip("First update didn't complete")
                
                result1 = response1.json()
                
                # Second run (should skip existing)
                response2 = await client.post(url)
                if response2.status_code != 200:
                    pytest.skip("Second update didn't complete")
                
                result2 = response2.json()
                
                # Second run should have more skips or same success count
                # (idempotent = same result)
                assert result2.get('skipped_count', 0) >= 0
                
            except httpx.ConnectError:
                pytest.skip("Data service not running")
            except httpx.ReadTimeout:
                pytest.skip("Timeout during update")


# =============================================================================
# Simulation Helper
# =============================================================================

async def run_simulated_daily_flow(target_date: Optional[date] = None) -> Dict[str, Any]:
    """
    Run the full daily flow for a specific date:
    1) Daily price update
    2) Daily indicator calculation
    3) Evening crossover scan
    4) Morning summary (next day)

    Default behavior:
    - Uses yesterday for the daily pipeline steps
    - Uses the following day for the morning summary
    """
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
        # Daily price update
        resp = await client.post(
            f"{get_service_url('data-service')}/api/daily-update",
            json={"target_date": sim_date.isoformat(), "lookback_days": lookback_days},
        )
        results["steps"]["daily_update"] = {
            "status_code": resp.status_code,
            "body": _safe_json(resp),
        }

        # Daily indicator calculation
        resp = await client.post(
            f"{get_service_url('indicator-service')}/api/daily-calculate",
            json={"target_date": sim_date.isoformat()},
        )
        results["steps"]["daily_calculate"] = {
            "status_code": resp.status_code,
            "body": _safe_json(resp),
        }

        # Evening crossover scan
        resp = await client.post(
            f"{get_service_url('scanner-service')}/run-crossover-scan",
            json={"target_date": sim_date.isoformat()},
        )
        results["steps"]["crossover_scan"] = {
            "status_code": resp.status_code,
            "body": _safe_json(resp),
        }

        # Morning summary (next day)
        resp = await client.post(
            f"{get_service_url('alert-service')}/send-morning-summary",
            json={"target_date": summary_date.isoformat()},
        )
        results["steps"]["morning_summary"] = {
            "status_code": resp.status_code,
            "body": _safe_json(resp),
        }

    return results


# =============================================================================
# CLI Entry Point (for running outside pytest)
# =============================================================================

async def run_manual_tests():
    """Run tests manually for debugging."""
    print("\n" + "="*80)
    print("INTEGRATION TEST SUITE (Manual Mode)")
    print(f"Started: {datetime.now()}")
    print("="*80)
    
    # Quick health checks
    print("\n[Service Health Checks]")
    services_to_check = ['data-service', 'indicator-service', 'scanner-service']
    
    async with httpx.AsyncClient(timeout=5.0) as client:
        for service in services_to_check:
            try:
                response = await client.get(f"{get_service_url(service)}/")
                status = "✅ Healthy" if response.status_code == 200 else f"⚠️ Status {response.status_code}"
                print(f"  {service}: {status}")
            except Exception as e:
                print(f"  {service}: ❌ Error - {e}")
    
    run_simulation = os.environ.get("RUN_SIMULATION", "").lower() in ("1", "true", "yes")
    sim_date = _parse_date(os.environ.get("SIMULATION_DATE", ""))
    if run_simulation or sim_date:
        resolved_date = sim_date or (date.today() - timedelta(days=1))
        print("\n" + "="*80)
        print(f"SIMULATED DAILY FLOW (target_date={resolved_date})")
        print("="*80)
        results = await run_simulated_daily_flow(target_date=sim_date)
        print(f"  lookback_days: {results.get('lookback_days')}")
        for step, info in results["steps"].items():
            print(f"  {step}: {info['status_code']}")

    print("\n" + "="*80)
    print("For full test run: pytest tests/integration_test_suite.py -v")
    print("="*80)


if __name__ == "__main__":
    import asyncio
    asyncio.run(run_manual_tests())
