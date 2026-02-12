"""
Tests for scheduler-service job functions.
"""
from unittest.mock import patch, MagicMock, AsyncMock

import pytest
from types import ModuleType


class TestIsTradingDay:
    """Tests for is_trading_day function."""
    
    @patch('src.jobs.mcal')
    def test_trading_day_returns_true(self, mock_mcal):
        """Test that a trading day returns True."""
        from src.jobs import is_trading_day
        
        # Mock NYSE calendar returning non-empty schedule
        mock_calendar = MagicMock()
        mock_schedule = MagicMock()
        mock_schedule.empty = False
        mock_calendar.schedule.return_value = mock_schedule
        mock_mcal.get_calendar.return_value = mock_calendar
        
        assert is_trading_day() is True
    
    @patch('src.jobs.mcal')
    def test_holiday_returns_false(self, mock_mcal):
        """Test that a holiday returns False."""
        from src.jobs import is_trading_day
        
        # Mock NYSE calendar returning empty schedule (holiday)
        mock_calendar = MagicMock()
        mock_schedule = MagicMock()
        mock_schedule.empty = True
        mock_calendar.schedule.return_value = mock_schedule
        mock_mcal.get_calendar.return_value = mock_calendar
        
        assert is_trading_day() is False


class TestRetryHelpers:
    @pytest.mark.asyncio
    async def test_post_json_with_retry_succeeds(self):
        from src.jobs import _post_json_with_retry

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b'{"status":"completed"}'
        mock_response.json.return_value = {"status": "completed"}

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response

        mock_ctx = AsyncMock()
        mock_ctx.__aenter__.return_value = mock_client
        mock_ctx.__aexit__.return_value = None
        mock_httpx = ModuleType("httpx")
        mock_httpx.AsyncClient = MagicMock(return_value=mock_ctx)

        with patch.dict("sys.modules", {"httpx": mock_httpx}):
            result = await _post_json_with_retry(
                "http://example/api",
                job_name="test_job",
                timeout_seconds=1.0,
            )

        assert result == {"status": "completed"}

    @pytest.mark.asyncio
    async def test_post_json_with_retry_sends_system_alert_after_exhaustion(self):
        from src import jobs

        mock_client = AsyncMock()
        mock_client.post.side_effect = RuntimeError("upstream down")

        mock_ctx = AsyncMock()
        mock_ctx.__aenter__.return_value = mock_client
        mock_ctx.__aexit__.return_value = None
        mock_httpx = ModuleType("httpx")
        mock_httpx.AsyncClient = MagicMock(return_value=mock_ctx)

        with patch.dict("sys.modules", {"httpx": mock_httpx}), patch(
            "src.jobs.RETRY_DELAYS_SECONDS",
            [1, 2],
        ), patch("asyncio.sleep", new=AsyncMock()) as mock_sleep, patch(
            "src.jobs._send_system_alert",
            new=AsyncMock(),
        ) as mock_system_alert:
            result = await jobs._post_json_with_retry(
                "http://example/api",
                job_name="test_job",
                timeout_seconds=1.0,
            )

        assert result is None
        assert mock_sleep.await_count == 2
        mock_system_alert.assert_awaited_once()
