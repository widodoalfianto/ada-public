"""
Tests for shared transaction utilities.
"""
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
import asyncio


class TestTransactionScope:
    """Tests for transaction_scope context manager."""
    
    @pytest.mark.asyncio
    async def test_commits_on_success(self):
        """Test that transaction commits when no exception occurs."""
        from shared.transactions import transaction_scope
        
        # Mock session
        session = AsyncMock()
        session.commit = AsyncMock()
        session.rollback = AsyncMock()
        
        async with transaction_scope(session, "test_op"):
            pass  # No exception
        
        session.commit.assert_called_once()
        session.rollback.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_rollback_on_exception(self):
        """Test that transaction rolls back when exception occurs."""
        from shared.transactions import transaction_scope, TransactionError
        
        session = AsyncMock()
        session.commit = AsyncMock()
        session.rollback = AsyncMock()
        
        with pytest.raises(TransactionError):
            async with transaction_scope(session, "test_op"):
                raise ValueError("Test error")
        
        session.rollback.assert_called_once()
        session.commit.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_transaction_error_wraps_original(self):
        """Test that TransactionError wraps the original exception."""
        from shared.transactions import transaction_scope, TransactionError
        
        session = AsyncMock()
        
        try:
            async with transaction_scope(session, "test_op"):
                raise ValueError("Original error")
        except TransactionError as e:
            assert "test_op" in str(e)
            assert isinstance(e.original_error, ValueError)


class TestBatchTransaction:
    """Tests for batch_transaction context manager."""
    
    @pytest.mark.asyncio
    async def test_commits_at_batch_size(self):
        """Test that commits happen at batch size intervals."""
        from shared.transactions import batch_transaction
        
        session = AsyncMock()
        session.commit = AsyncMock()
        
        async with batch_transaction(session, batch_size=3, operation_name="test") as batch:
            await batch.increment()  # 1
            await batch.increment()  # 2
            await batch.increment()  # 3 - should commit
            await batch.increment()  # 4
        
        # Should have 2 commits: one at batch size, one final
        assert session.commit.call_count == 2
        assert batch.total_count == 4
    
    @pytest.mark.asyncio
    async def test_final_commit_for_remainder(self):
        """Test that final items are committed on exit."""
        from shared.transactions import batch_transaction
        
        session = AsyncMock()
        session.commit = AsyncMock()
        
        async with batch_transaction(session, batch_size=10) as batch:
            await batch.increment()  # Only 1 item
        
        # Should still commit the one item
        session.commit.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_batch_context_tracks_counts(self):
        """Test that batch context correctly tracks all counts."""
        from shared.transactions import batch_transaction
        
        session = AsyncMock()
        session.commit = AsyncMock()
        
        async with batch_transaction(session, batch_size=5) as batch:
            for _ in range(12):
                await batch.increment()
        
        assert batch.total_count == 12
        # 2 batch commits (at 5 and 10) + 1 final commit
        assert batch.commit_count == 2


class TestTransactionalDecorator:
    """Tests for @transactional decorator."""
    
    @pytest.mark.asyncio
    async def test_decorator_wraps_function(self):
        """Test that decorator properly wraps function."""
        from shared.transactions import transactional
        
        session = AsyncMock()
        session.commit = AsyncMock()
        session.rollback = AsyncMock()
        
        @transactional("test_operation")
        async def my_function(sess, value):
            return value * 2
        
        result = await my_function(session, 5)
        
        assert result == 10
        session.commit.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_decorator_rolls_back_on_error(self):
        """Test that decorator rolls back on error."""
        from shared.transactions import transactional, TransactionError
        
        session = AsyncMock()
        session.commit = AsyncMock()
        session.rollback = AsyncMock()
        
        @transactional("failing_operation")
        async def failing_function(sess):
            raise RuntimeError("Something broke")
        
        with pytest.raises(TransactionError):
            await failing_function(session)
        
        session.rollback.assert_called_once()


class TestTransactionContext:
    """Tests for TransactionContext helper class."""
    
    @pytest.mark.asyncio
    async def test_savepoint_creation(self):
        """Test that savepoints can be created."""
        from shared.transactions import transaction_scope
        
        session = AsyncMock()
        session.begin_nested = AsyncMock()
        
        async with transaction_scope(session, "test_op") as txn:
            savepoint_name = await txn.savepoint()
            
            assert "test_op" in savepoint_name
            assert txn._savepoint_count == 1
            session.begin_nested.assert_called_once()


class TestTransactionError:
    """Tests for TransactionError exception."""
    
    def test_transaction_error_creation(self):
        """Test TransactionError creation."""
        from shared.transactions import TransactionError
        
        original = ValueError("Original")
        error = TransactionError("Transaction failed", original_error=original)
        
        assert "Transaction failed" in str(error)
        assert error.original_error == original
