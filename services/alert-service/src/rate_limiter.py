"""
Rate limiting utilities for Discord commands and API endpoints.

Provides per-user rate limiting to prevent abuse of resource-intensive commands.
"""
from typing import Dict, Optional
import time
import asyncio
import logging
from collections import defaultdict
from dataclasses import dataclass, field


logger = logging.getLogger(__name__)


@dataclass
class RateLimitConfig:
    """Configuration for rate limiting."""
    max_requests: int = 5  # Maximum requests in window
    window_seconds: int = 60  # Time window in seconds
    cooldown_message: str = "⏳ You're doing that too fast. Please wait {remaining}s before trying again."


@dataclass
class UserBucket:
    """Tracks request counts for a single user."""
    requests: list = field(default_factory=list)  # Timestamps of requests
    
    def add_request(self, timestamp: float):
        self.requests.append(timestamp)
    
    def cleanup(self, window_seconds: int, current_time: float):
        """Remove requests outside the current window."""
        cutoff = current_time - window_seconds
        self.requests = [ts for ts in self.requests if ts > cutoff]
    
    def count(self) -> int:
        return len(self.requests)


class RateLimiter:
    """
    In-memory rate limiter for Discord commands.
    
    Uses a sliding window algorithm to track requests per user.
    """
    
    def __init__(self, config: Optional[RateLimitConfig] = None):
        self.config = config or RateLimitConfig()
        self.buckets: Dict[int, UserBucket] = defaultdict(UserBucket)
        self._lock = asyncio.Lock()
    
    async def check(self, user_id: int) -> tuple[bool, Optional[int]]:
        """
        Check if a user is rate limited.
        
        Args:
            user_id: Discord user ID
            
        Returns:
            Tuple of (is_allowed, seconds_until_reset)
            - is_allowed: True if request is allowed
            - seconds_until_reset: Seconds until rate limit resets (if limited)
        """
        async with self._lock:
            current_time = time.time()
            bucket = self.buckets[user_id]
            
            # Clean up old requests
            bucket.cleanup(self.config.window_seconds, current_time)
            
            # Check if over limit
            if bucket.count() >= self.config.max_requests:
                # Calculate time until oldest request expires
                oldest_request = min(bucket.requests)
                reset_time = oldest_request + self.config.window_seconds
                remaining = int(reset_time - current_time) + 1
                return False, remaining
            
            # Allow request and record it
            bucket.add_request(current_time)
            return True, None
    
    def get_cooldown_message(self, remaining_seconds: int) -> str:
        """Get the user-friendly cooldown message."""
        return self.config.cooldown_message.format(remaining=remaining_seconds)
    
    def get_usage(self, user_id: int) -> tuple[int, int]:
        """
        Get current usage for a user.
        
        Returns:
            Tuple of (current_requests, max_requests)
        """
        bucket = self.buckets.get(user_id)
        if not bucket:
            return 0, self.config.max_requests
        
        bucket.cleanup(self.config.window_seconds, time.time())
        return bucket.count(), self.config.max_requests


# =============================================================================
# Pre-configured Rate Limiters
# =============================================================================

# Backtest commands: 5 requests per minute (expensive operations)
backtest_limiter = RateLimiter(RateLimitConfig(
    max_requests=5,
    window_seconds=60,
    cooldown_message="⏳ Backtest rate limit reached. Please wait {remaining}s before running another backtest."
))

# Strategy builder: 10 requests per minute (less expensive)
strategy_limiter = RateLimiter(RateLimitConfig(
    max_requests=10,
    window_seconds=60,
    cooldown_message="⏳ Strategy builder rate limit reached. Please wait {remaining}s."
))

# General commands: 20 requests per minute
general_limiter = RateLimiter(RateLimitConfig(
    max_requests=20,
    window_seconds=60,
    cooldown_message="⏳ Too many requests. Please wait {remaining}s."
))


# =============================================================================
# Decorator for easy integration
# =============================================================================

def rate_limited(limiter: RateLimiter):
    """
    Decorator to add rate limiting to Discord slash commands.
    
    Usage:
        @bot.tree.command(name="example")
        @rate_limited(backtest_limiter)
        async def example_command(interaction: discord.Interaction):
            ...
    """
    def decorator(func):
        async def wrapper(interaction, *args, **kwargs):
            user_id = interaction.user.id
            is_allowed, remaining = await limiter.check(user_id)
            
            if not is_allowed:
                await interaction.response.send_message(
                    limiter.get_cooldown_message(remaining),
                    ephemeral=True
                )
                return
            
            return await func(interaction, *args, **kwargs)
        
        # Preserve function metadata for discord.py
        wrapper.__name__ = func.__name__
        wrapper.__doc__ = func.__doc__
        return wrapper
    return decorator
