"""
Stock Filter Module

Provides filtering functions to select top stocks by volume
for crossover alert monitoring.
"""
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
import logging

logger = logging.getLogger(__name__)


async def get_top_stocks_by_volume(
    session: AsyncSession,
    limit: int = 100,
    min_price: float = 10.0
) -> List:
    """
    Get top N active stocks by 30-day average dollar volume with minimum price filter.
    
    Args:
        session: Database session
        limit: Maximum number of stocks to return (default: 100)
        min_price: Minimum last close price filter (default: $10)
    
    Returns:
        List of Stock objects sorted by avg dollar volume descending
    """
    from shared.models import Stock

    avg_dollar_volume = Stock.avg_volume_30d * Stock.last_close_price
    query = (
        select(Stock)
        .where(Stock.is_active == True)
        .where(Stock.avg_volume_30d.isnot(None))
        .where(Stock.avg_volume_30d > 0)
        .where(Stock.last_close_price.isnot(None))
        .where(Stock.last_close_price >= min_price)
        .order_by(desc(avg_dollar_volume))
        .limit(limit)
    )
    
    result = await session.execute(query)
    stocks = result.scalars().all()
    
    logger.info(f"Selected {len(stocks)} stocks (top {limit} by avg dollar volume, min ${min_price})")
    
    return stocks



