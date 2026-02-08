"""
Tests for rate limiter utility.
"""
import pytest
from unittest.mock import patch
import asyncio
import time


class TestRateLimiter:
    """Tests for RateLimiter class."""
    
    @pytest.mark.asyncio
    async def test_allows_under_limit(self):
        """Test that requests under limit are allowed."""
        from src.rate_limiter import RateLimiter, RateLimitConfig
        
        limiter = RateLimiter(RateLimitConfig(max_requests=5, window_seconds=60))
        
        is_allowed, remaining = await limiter.check(user_id=123)
        
        assert is_allowed == True
        assert remaining is None
    
    @pytest.mark.asyncio
    async def test_blocks_over_limit(self):
        """Test that requests over limit are blocked."""
        from src.rate_limiter import RateLimiter, RateLimitConfig
        
        limiter = RateLimiter(RateLimitConfig(max_requests=2, window_seconds=60))
        
        # Use up the limit
        await limiter.check(user_id=123)
        await limiter.check(user_id=123)
        
        # Third request should be blocked
        is_allowed, remaining = await limiter.check(user_id=123)
        
        assert is_allowed == False
        assert remaining is not None
        assert remaining > 0
    
    @pytest.mark.asyncio
    async def test_different_users_independent(self):
        """Test that different users have independent limits."""
        from src.rate_limiter import RateLimiter, RateLimitConfig
        
        limiter = RateLimiter(RateLimitConfig(max_requests=1, window_seconds=60))
        
        # User 1 uses their limit
        is_allowed_1, _ = await limiter.check(user_id=1)
        is_blocked_1, _ = await limiter.check(user_id=1)
        
        # User 2 should still be allowed
        is_allowed_2, _ = await limiter.check(user_id=2)
        
        assert is_allowed_1 == True
        assert is_blocked_1 == False
        assert is_allowed_2 == True
    
    def test_cooldown_message(self):
        """Test cooldown message generation."""
        from src.rate_limiter import RateLimiter, RateLimitConfig
        
        limiter = RateLimiter(RateLimitConfig(
            cooldown_message="Wait {remaining}s"
        ))
        
        message = limiter.get_cooldown_message(30)
        
        assert message == "Wait 30s"
    
    def test_get_usage(self):
        """Test usage tracking."""
        from src.rate_limiter import RateLimiter, RateLimitConfig
        
        limiter = RateLimiter(RateLimitConfig(max_requests=5))
        
        # New user should have 0 usage
        current, max_req = limiter.get_usage(user_id=999)
        
        assert current == 0
        assert max_req == 5


class TestPreConfiguredLimiters:
    """Tests for pre-configured limiters."""
    
    def test_backtest_limiter_exists(self):
        """Test that backtest_limiter is configured correctly."""
        from src.rate_limiter import backtest_limiter
        
        assert backtest_limiter.config.max_requests == 5
        assert backtest_limiter.config.window_seconds == 60
    
    def test_strategy_limiter_exists(self):
        """Test that strategy_limiter is configured correctly."""
        from src.rate_limiter import strategy_limiter
        
        assert strategy_limiter.config.max_requests == 10
        assert strategy_limiter.config.window_seconds == 60
