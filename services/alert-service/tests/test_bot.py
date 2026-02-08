"""
Tests for alert-service bot components.
"""
import pytest
from unittest.mock import MagicMock, patch, AsyncMock
import sys

# Define robust mocks that handle class-level kwargs
class MockModal:
    def __init_subclass__(cls, **kwargs):
        pass
    def __init__(self, *args, **kwargs):
        pass

class MockView:
    def __init_subclass__(cls, **kwargs):
        pass
    def __init__(self, *args, **kwargs):
        pass

# Mock discord module
mock_discord = MagicMock()
mock_discord.ui.Modal = MockModal
mock_discord.ui.View = MockView
mock_discord.ui.TextInput = MagicMock
mock_discord.ui.Select = MagicMock
mock_discord.ui.Button = MagicMock
mock_discord.ButtonStyle = MagicMock()
mock_discord.SelectOption = MagicMock
mock_discord.Embed = MagicMock

with patch.dict(sys.modules, {'discord': mock_discord, 'discord.ui': mock_discord.ui}):
    from src import bot

class TestStrategies:
    """Tests for strategy configuration."""
    
    def test_strategies_defined(self):
        """Test that default strategies are properly defined."""
        assert "ma_crossover" in bot.STRATEGIES
        assert "rsi_bounce" in bot.STRATEGIES
        assert "macd_cross" in bot.STRATEGIES
        
        # Check structure
        ma_strategy = bot.STRATEGIES["ma_crossover"]
        assert "name" in ma_strategy
        assert "params" in ma_strategy
    
    def test_periods_defined(self):
        """Test that period mappings are correct."""
        assert bot.PERIODS["1M"] == 30
        assert bot.PERIODS["3M"] == 90
        assert bot.PERIODS["6M"] == 180
        assert bot.PERIODS["1Y"] == 365
        assert bot.PERIODS["2Y"] == 730


class TestBacktestModal:
    """Tests for BacktestModal class."""
    
    def test_modal_initialization(self):
        """Test modal initializes with correct defaults."""
        modal = bot.BacktestModal(strategy="ma_crossover", period="1Y")
        
        assert modal.strategy == "ma_crossover"
        assert modal.period == "1Y"


class TestStrategyBuilder:
    """Tests for StrategyBuilderView."""
    
    def test_builder_initialization(self):
        """Test strategy builder initializes empty."""
        builder = bot.StrategyBuilderView()
        
        assert builder.entry_conditions == []
        assert builder.exit_conditions == []
        assert builder.adding_entry == True
    
    def test_describe_rsi_condition(self):
        """Test RSI condition description."""
        builder = bot.StrategyBuilderView()
        
        condition = {
            "indicator": "rsi",
            "comparison": "<",
            "params": {"period": 14, "threshold": 30}
        }
        
        description = builder.describe_condition(condition)
        
        assert "RSI" in description
        assert "14" in description
        assert "30" in description
    
    def test_describe_ma_cross_condition(self):
        """Test MA cross condition description."""
        builder = bot.StrategyBuilderView()
        
        condition = {
            "indicator": "ma_cross",
            "comparison": "cross_up",
            "params": {"fast_period": 9, "slow_period": 20}
        }
        
        description = builder.describe_condition(condition)
        
        assert "EMA" in description
        assert "SMA" in description
        assert "9" in description
        assert "20" in description
    
    def test_build_embed_with_empty_conditions(self):
        """Test embed building with no conditions."""
        builder = bot.StrategyBuilderView()
        embed = builder.build_embed()
        
        assert embed is not None


class TestConditionOptions:
    """Tests for condition options."""
    
    def test_condition_options_defined(self):
        """Test that condition options are properly defined."""
        assert len(bot.CONDITION_OPTIONS) >= 5
