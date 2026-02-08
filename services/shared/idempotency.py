"""
Idempotency utilities for safe data operations.

Provides consistent patterns for duplicate detection and safe re-runs.
"""
from typing import TypeVar, Optional, Callable, Any
from datetime import date, datetime
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import logging


logger = logging.getLogger(__name__)

T = TypeVar('T')


class IdempotencyChecker:
    """
    Utility for checking if records already exist before insert.
    
    This enables safe re-runs of data pipelines without creating duplicates.
    """
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def record_exists(
        self,
        model: type,
        **filters
    ) -> bool:
        """
        Check if a record matching the filters already exists.
        
        Args:
            model: SQLAlchemy model class
            **filters: Key-value pairs for filtering (e.g., stock_id=1, date=date.today())
        
        Returns:
            True if record exists, False otherwise
        """
        query = select(model)
        for key, value in filters.items():
            query = query.where(getattr(model, key) == value)
        query = query.limit(1)
        
        result = await self.session.execute(query)
        return result.scalars().first() is not None
    
    async def get_or_create(
        self,
        model: type,
        defaults: dict,
        **lookup_filters
    ) -> tuple[Any, bool]:
        """
        Get existing record or create new one.
        
        Args:
            model: SQLAlchemy model class
            defaults: Default values for new record
            **lookup_filters: Filters to find existing record
        
        Returns:
            Tuple of (instance, created) where created is True if new record was made
        """
        query = select(model)
        for key, value in lookup_filters.items():
            query = query.where(getattr(model, key) == value)
        query = query.limit(1)
        
        result = await self.session.execute(query)
        existing = result.scalars().first()
        
        if existing:
            return existing, False
        
        # Merge filters and defaults for new record
        new_data = {**lookup_filters, **defaults}
        new_instance = model(**new_data)
        self.session.add(new_instance)
        
        return new_instance, True
    
    async def upsert(
        self,
        model: type,
        update_fields: list[str],
        **data
    ) -> tuple[Any, str]:
        """
        Insert or update a record.
        
        Args:
            model: SQLAlchemy model class
            update_fields: Fields to update if record exists
            **data: All data including lookup keys
        
        Returns:
            Tuple of (instance, action) where action is 'created' or 'updated'
        """
        # Determine primary key fields (assumes 'stock_id' and 'date' for typical models)
        lookup_keys = ['stock_id', 'date']
        lookup = {k: data[k] for k in lookup_keys if k in data}
        
        query = select(model)
        for key, value in lookup.items():
            query = query.where(getattr(model, key) == value)
        query = query.limit(1)
        
        result = await self.session.execute(query)
        existing = result.scalars().first()
        
        if existing:
            # Update existing record
            for field in update_fields:
                if field in data:
                    setattr(existing, field, data[field])
            return existing, 'updated'
        else:
            # Create new record
            new_instance = model(**data)
            self.session.add(new_instance)
            return new_instance, 'created'


# =============================================================================
# Convenience functions
# =============================================================================

async def check_duplicate(
    session: AsyncSession,
    model: type,
    stock_id: int,
    target_date: date
) -> bool:
    """
    Quick check for stock+date duplicate (most common pattern).
    
    Returns:
        True if record already exists for this stock on this date
    """
    checker = IdempotencyChecker(session)
    return await checker.record_exists(model, stock_id=stock_id, date=target_date)


def log_idempotency_skip(symbol: str, operation: str, reason: str = "already exists"):
    """Log when an operation is skipped due to idempotency."""
    logger.info(f"[IDEMPOTENT] {symbol}: Skipping {operation} - {reason}")


def log_idempotency_proceed(symbol: str, operation: str):
    """Log when an operation proceeds (no duplicate found)."""
    logger.debug(f"[PROCEED] {symbol}: Executing {operation}")
