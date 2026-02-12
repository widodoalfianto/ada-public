"""
Integration tests for indicator-service HTTP endpoints.

These tests are skipped automatically when the service is not reachable.
Set INDICATOR_BASE_URL to point to the running service.
"""
from __future__ import annotations

import os

import pytest

httpx = pytest.importorskip("httpx")


BASE_URL = os.getenv("INDICATOR_BASE_URL", "http://localhost:9002")


async def _get(client: httpx.AsyncClient, path: str) -> httpx.Response:
    try:
        return await client.get(f"{BASE_URL}{path}")
    except httpx.ConnectError:
        pytest.skip(f"indicator-service not reachable at {BASE_URL}")


async def _post(client: httpx.AsyncClient, path: str) -> httpx.Response:
    try:
        return await client.post(f"{BASE_URL}{path}")
    except httpx.ConnectError:
        pytest.skip(f"indicator-service not reachable at {BASE_URL}")


@pytest.mark.asyncio
async def test_health_endpoint():
    async with httpx.AsyncClient(timeout=5.0) as client:
        response = await _get(client, "/")
        assert response.status_code == 200
        payload = response.json()
        assert "message" in payload


@pytest.mark.asyncio
async def test_get_indicators_endpoint_smoke():
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await _get(client, "/indicators/AAPL?days=1")
        if response.status_code == 404:
            pytest.skip("AAPL indicator data not available in this environment")

        assert response.status_code == 200
        payload = response.json()
        assert isinstance(payload, list)
        if payload:
            latest = payload[0]
            assert "date" in latest
            assert "indicators" in latest


@pytest.mark.asyncio
@pytest.mark.slow
async def test_daily_calculate_endpoint_smoke():
    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await _post(client, "/api/daily-calculate")
        assert response.status_code == 200
        payload = response.json()
        assert "status" in payload
        assert "timestamp" in payload
