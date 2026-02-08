"""
Transaction management utilities for safe database operations.

Provides consistent patterns for commit/rollback handling with proper cleanup.
"""
from typing import TypeVar, Callable, Any, Optional
from contextlib import asynccontextmanager
from sqlalchemy.ext.asyncio import AsyncSession
import logging
import functools


logger = logging.getLogger(__name__)

T = TypeVar('T')


class TransactionError(Exception):
    """Raised when a transaction fails and is rolled back."""
    
    def __init__(self, message: str, original_error: Optional[Exception] = None):
        super().__init__(message)
        self.original_error = original_error


@asynccontextmanager
async def transaction_scope(session: AsyncSession, operation_name: str = "operation"):
    """
    Context manager for safe transaction handling.
    
    Automatically commits on success and rolls back on failure.
    
    Usage:
        async with transaction_scope(session, "create_user") as txn:
            session.add(new_user)
            # Auto-commit on exit, auto-rollback on exception
    
    Args:
        session: SQLAlchemy async session
        operation_name: Name for logging purposes
    
    Yields:
        Transaction context with commit/rollback helpers
    """
    try:
        yield TransactionContext(session, operation_name)
        await session.commit()
        logger.debug(f"[TXN] {operation_name}: Committed successfully")
    except Exception as e:
        await session.rollback()
        logger.error(f"[TXN] {operation_name}: Rolled back due to error: {e}")
        raise TransactionError(f"Transaction '{operation_name}' failed", original_error=e) from e


class TransactionContext:
    """Helper class providing transaction state and utilities."""
    
    def __init__(self, session: AsyncSession, operation_name: str):
        self.session = session
        self.operation_name = operation_name
        self._savepoint_count = 0
    
    async def savepoint(self):
        """Create a savepoint for partial rollback capability."""
        self._savepoint_count += 1
        savepoint_name = f"{self.operation_name}_sp_{self._savepoint_count}"
        await self.session.begin_nested()
        logger.debug(f"[TXN] Created savepoint: {savepoint_name}")
        return savepoint_name


@asynccontextmanager  
async def batch_transaction(session: AsyncSession, batch_size: int = 50, operation_name: str = "batch"):
    """
    Context manager for batch operations with periodic commits.
    
    Commits every `batch_size` operations to prevent memory buildup.
    
    Usage:
        async with batch_transaction(session, batch_size=100) as batch:
            for item in items:
                session.add(item)
                await batch.increment()  # Auto-commits every 100
    
    Args:
        session: SQLAlchemy async session
        batch_size: Number of operations before commit
        operation_name: Name for logging
    """
    batch_ctx = BatchContext(session, batch_size, operation_name)
    try:
        yield batch_ctx
        # Final commit for remaining items
        if batch_ctx.pending_count > 0:
            await session.commit()
            logger.debug(f"[BATCH] {operation_name}: Final commit of {batch_ctx.pending_count} items")
    except Exception as e:
        await session.rollback()
        logger.error(f"[BATCH] {operation_name}: Rolled back at item {batch_ctx.total_count}")
        raise TransactionError(f"Batch '{operation_name}' failed at item {batch_ctx.total_count}", original_error=e) from e


class BatchContext:
    """Helper class for batch transaction tracking."""
    
    def __init__(self, session: AsyncSession, batch_size: int, operation_name: str):
        self.session = session
        self.batch_size = batch_size
        self.operation_name = operation_name
        self.total_count = 0
        self.pending_count = 0
        self.commit_count = 0
    
    async def increment(self):
        """Increment counter and commit if batch size reached."""
        self.total_count += 1
        self.pending_count += 1
        
        if self.pending_count >= self.batch_size:
            await self.session.commit()
            self.commit_count += 1
            logger.debug(f"[BATCH] {self.operation_name}: Committed batch {self.commit_count} ({self.total_count} total)")
            self.pending_count = 0


# =============================================================================
# Decorator for function-level transaction handling
# =============================================================================

def transactional(operation_name: Optional[str] = None):
    """
    Decorator to wrap async functions in transaction scope.
    
    The decorated function must accept 'session' as first argument.
    
    Usage:
        @transactional("create_order")
        async def create_order(session: AsyncSession, order_data: dict):
            ...
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(session: AsyncSession, *args, **kwargs):
            name = operation_name or func.__name__
            async with transaction_scope(session, name):
                return await func(session, *args, **kwargs)
        return wrapper
    return decorator


# =============================================================================
# Integrity validation helpers
# =============================================================================

async def validate_foreign_key(
    session: AsyncSession,
    model: type,
    pk_value: Any,
    field_name: str = "id"
) -> bool:
    """
    Validate that a foreign key reference exists.
    
    Args:
        session: Database session
        model: Model class to check
        pk_value: Primary key value to look up
        field_name: Name of the primary key field
    
    Returns:
        True if reference exists, False otherwise
    """
    from sqlalchemy import select
    
    query = select(model).where(getattr(model, field_name) == pk_value).limit(1)
    result = await session.execute(query)
    return result.scalars().first() is not None


async def validate_unique(
    session: AsyncSession,
    model: type,
    exclude_id: Optional[int] = None,
    **unique_fields
) -> bool:
    """
    Validate that a combination of fields is unique.
    
    Args:
        session: Database session
        model: Model class to check
        exclude_id: Exclude this ID (for updates)
        **unique_fields: Field values that must be unique together
    
    Returns:
        True if unique (no conflict), False if duplicate exists
    """
    from sqlalchemy import select
    
    query = select(model)
    for field, value in unique_fields.items():
        query = query.where(getattr(model, field) == value)
    
    if exclude_id is not None:
        query = query.where(model.id != exclude_id)
    
    query = query.limit(1)
    result = await session.execute(query)
    return result.scalars().first() is None
