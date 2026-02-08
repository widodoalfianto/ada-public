"""
Tests for scheduler-service job functions.
"""
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime
import pytz


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
        
        assert is_trading_day() == True
    
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
        
        assert is_trading_day() == False


class TestRunMarketScan:
    """Tests for run_market_scan function."""
    
    @patch('src.jobs.requests')
    @patch('src.jobs.is_trading_day')
    def test_skips_on_non_trading_day(self, mock_is_trading_day, mock_requests):
        """Test that scan is skipped on non-trading days."""
        from src.jobs import run_market_scan
        
        mock_is_trading_day.return_value = False
        
        run_market_scan("end_of_day")
        
        # Should not make any HTTP calls
        mock_requests.post.assert_not_called()
    
    @patch('src.jobs.requests')
    @patch('src.jobs.is_trading_day')
    def test_triggers_scan_on_trading_day(self, mock_is_trading_day, mock_requests):
        """Test that scan is triggered on trading days."""
        from src.jobs import run_market_scan
        
        mock_is_trading_day.return_value = True
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_requests.post.return_value = mock_response
        
        run_market_scan("end_of_day")
        
        # Should call the scanner service
        mock_requests.post.assert_called_once()
        call_url = mock_requests.post.call_args[0][0]
        assert "/run-scan" in call_url
    
    @patch('src.jobs.requests')
    @patch('src.jobs.is_trading_day')
    def test_handles_connection_error(self, mock_is_trading_day, mock_requests):
        """Test that connection errors are handled gracefully."""
        from src.jobs import run_market_scan
        
        mock_is_trading_day.return_value = True
        mock_requests.post.side_effect = Exception("Connection refused")
        
        # Should not raise exception
        run_market_scan("end_of_day")
