"""
Crossover Detection Module

Detects Golden Cross and Death Cross signals based on EMA 9 vs SMA 20.
"""
from typing import Dict, Optional, Any, List
from dataclasses import dataclass
from enum import Enum
from datetime import date, timedelta
import logging

from sqlalchemy import select, desc, and_
from shared.models import Indicator, PriceData

logger = logging.getLogger(__name__)


class CrossoverType(Enum):
    """Types of crossovers that can be detected."""
    GOLDEN_CROSS = "golden_cross"  # EMA 9 crosses ABOVE SMA 20 (Buy signal)
    DEATH_CROSS = "death_cross"    # EMA 9 crosses BELOW SMA 20 (Sell signal)


@dataclass
class CrossoverSignal:
    """Represents a detected crossover signal."""
    symbol: str
    stock_id: int
    crossover_type: CrossoverType
    ema_9: float
    sma_20: float
    close_price: float
    signal_strength: float  # Percentage above/below
    
    @property
    def is_bullish(self) -> bool:
        return self.crossover_type == CrossoverType.GOLDEN_CROSS
    
    @property
    def direction(self) -> str:
        return "bullish" if self.is_bullish else "bearish"


def detect_crossover(
    ema_9_today: float,
    ema_9_yesterday: float,
    sma_20_today: float,
    sma_20_yesterday: float
) -> Optional[CrossoverType]:
    """
    Detect if a crossover occurred between yesterday and today.
    
    Golden Cross: EMA was BELOW SMA yesterday, now ABOVE
    Death Cross: EMA was ABOVE SMA yesterday, now BELOW
    
    Args:
        ema_9_today: Today's EMA 9 value
        ema_9_yesterday: Yesterday's EMA 9 value
        sma_20_today: Today's SMA 20 value
        sma_20_yesterday: Yesterday's SMA 20 value
    
    Returns:
        CrossoverType if crossover detected, None otherwise
    """
    if ema_9_today is None or ema_9_yesterday is None:
        return None
    if sma_20_today is None or sma_20_yesterday is None:
        return None
    
    was_below = ema_9_yesterday < sma_20_yesterday
    is_above = ema_9_today > sma_20_today
    
    was_above = ema_9_yesterday > sma_20_yesterday
    is_below = ema_9_today < sma_20_today
    
    if was_below and is_above:
        return CrossoverType.GOLDEN_CROSS
    elif was_above and is_below:
        return CrossoverType.DEATH_CROSS
    
    return None


def calculate_signal_strength(ema_9: float, sma_20: float) -> float:
    """
    Calculate how strong the signal is as a percentage.
    
    Positive = EMA above SMA (bullish)
    Negative = EMA below SMA (bearish)
    """
    if sma_20 == 0:
        return 0.0
    return ((ema_9 - sma_20) / sma_20) * 100


async def scan_for_crossovers(
    session,
    stocks: list,
    target_date: date = None
) -> List[CrossoverSignal]:
    """
    Scan a list of stocks for crossover signals.
    
    Optimized to use bulk queries instead of N+1.
    
    Args:
        session: Database session
        stocks: List of Stock objects to check
        target_date: Optional date to simulate scan for.
    
    Returns:
        List of CrossoverSignal objects for detected crossovers
    """
    if not stocks:
        return []

    signals = []
    stock_ids = [stock.id for stock in stocks]
    stock_map = {stock.id: stock for stock in stocks}
    
    try:
        # 1. Bulk Fetch Indicators (Last 7 days to be safe for weekends)
        today = target_date if target_date else date.today()
        start_date = today - timedelta(days=7)
        
        ind_query = (
            select(Indicator.stock_id, Indicator.date, Indicator.indicator_name, Indicator.value)
            .where(Indicator.stock_id.in_(stock_ids))
            .where(Indicator.indicator_name.in_(['ema_9', 'sma_20']))
            .where(Indicator.date >= start_date)
            .where(Indicator.date <= today) # Ensure we don't pick future data
            .order_by(Indicator.stock_id, desc(Indicator.date))
        )
        
        ind_result = await session.execute(ind_query)
        indicators_data = ind_result.all() # (stock_id, date, name, value)
        
        # Organize indicators by stock_id -> date -> name -> value
        # schema: data[stock_id][date]['ema_9'] = value
        data_map = {}
        
        for stock_id, dt, name, value in indicators_data:
            if stock_id not in data_map:
                data_map[stock_id] = {}
            if dt not in data_map[stock_id]:
                data_map[stock_id][dt] = {}
            data_map[stock_id][dt][name] = value

        # 2. Bulk Fetch Latest Prices
        # Use DISTINCT ON to get the very latest price for each stock
        price_query = (
            select(PriceData.stock_id, PriceData.close)
            .distinct(PriceData.stock_id)
            .where(PriceData.stock_id.in_(stock_ids))
            .order_by(PriceData.stock_id, desc(PriceData.date))
        )
        
        price_result = await session.execute(price_query)
        prices_map = {row.stock_id: row.close for row in price_result.all()}
        
        # 3. Process Each Stock
        for stock_id, stock_measures in data_map.items():
            stock = stock_map.get(stock_id)
            if not stock:
                continue
                
            sorted_dates = sorted(stock_measures.keys(), reverse=True)
            if len(sorted_dates) < 2:
                continue
            
            today_date = sorted_dates[0]
            yesterday_date = sorted_dates[1]
            
            today_vals = stock_measures[today_date]
            yesterday_vals = stock_measures[yesterday_date]
            
            ema_9_today = today_vals.get('ema_9')
            sma_20_today = today_vals.get('sma_20')
            ema_9_yesterday = yesterday_vals.get('ema_9')
            sma_20_yesterday = yesterday_vals.get('sma_20')
            
            # Detect crossover
            crossover = detect_crossover(
                ema_9_today, ema_9_yesterday,
                sma_20_today, sma_20_yesterday
            )
            
            if crossover:
                close_price = prices_map.get(stock_id, 0.0)
                
                signal = CrossoverSignal(
                    symbol=stock.symbol,
                    stock_id=stock.id,
                    crossover_type=crossover,
                    ema_9=ema_9_today,
                    sma_20=sma_20_today,
                    close_price=close_price,
                    signal_strength=calculate_signal_strength(ema_9_today, sma_20_today)
                )
                signals.append(signal)
                
                logger.info(f"🔔 {crossover.value.upper().replace('_', ' ')}: {stock.symbol} "
                           f"(EMA 9: ${ema_9_today:.2f}, SMA 20: ${sma_20_today:.2f})")

    except Exception as e:
        logger.error(f"Error during bulk crossover scan: {e}", exc_info=True)
    
    return signals
