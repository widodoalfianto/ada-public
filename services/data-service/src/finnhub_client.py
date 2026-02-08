import httpx
import redis.asyncio as redis
import time
import asyncio
from src.config import settings
from tenacity import retry, stop_after_attempt, wait_exponential

class RateLimiter:
    def __init__(self, redis_url: str, limit: int = 60, window: int = 60):
        self.redis = redis.from_url(redis_url)
        self.limit = limit
        self.window = window

    async def acquire(self):
        key = f"rate_limit:{int(time.time() // 60)}"
        current = await self.redis.incr(key)
        if current == 1:
            await self.redis.expire(key, self.window + 10)
        
        if current > self.limit:
            wait_time = 60 - (time.time() % 60)
            print(f"Rate limit hit, waiting {wait_time:.2f}s")
            await asyncio.sleep(wait_time + 1)
            # Recursive retry after wait
            await self.acquire()

class FinnhubClient:
    def __init__(self):
        self.base_url = "https://finnhub.io/api/v1"
        self.api_key = settings.FINNHUB_API_KEY
        self.rate_limiter = RateLimiter(settings.REDIS_URL)

    @retry(stop=stop_after_attempt(5), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def get_quote(self, symbol: str):
        await self.rate_limiter.acquire()
        # Prevent burst limit (30 req/sec) by adding a small delay
        await asyncio.sleep(0.05) 
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/quote",
                params={"symbol": symbol, "token": self.api_key}
            )
            response.raise_for_status()
            return response.json()

    @retry(stop=stop_after_attempt(5), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def get_candles(self, symbol: str, resolution: str, from_ts: int, to_ts: int):
        await self.rate_limiter.acquire()
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/stock/candle",
                params={
                    "symbol": symbol,
                    "resolution": resolution,
                    "from": from_ts,
                    "to": to_ts,
                    "token": self.api_key
                }
            )
            response.raise_for_status()
            return response.json()
