"""
Tests for alert-service bot helpers and wiring.
"""
from types import ModuleType, SimpleNamespace
from unittest.mock import MagicMock, patch
import sys


class MockSelect:
    def __init_subclass__(cls, **kwargs):
        pass

    def __init__(self, *args, **kwargs):
        self.values = []


class MockView:
    def __init_subclass__(cls, **kwargs):
        pass

    def __init__(self, *args, **kwargs):
        self.items = []

    def add_item(self, item):
        self.items.append(item)


class MockClient:
    def __init_subclass__(cls, **kwargs):
        pass

    def __init__(self, *args, **kwargs):
        pass

    def get_channel(self, *_args, **_kwargs):
        return None


class MockCommandTree:
    def __init__(self, *_args, **_kwargs):
        pass

    async def sync(self):
        return None

    def command(self, *args, **kwargs):
        def decorator(func):
            return func

        return decorator


class MockChoice:
    def __init__(self, name, value):
        self.name = name
        self.value = value

    def __class_getitem__(cls, _item):
        return cls


def _identity_decorator(*_args, **_kwargs):
    def decorator(func):
        return func

    return decorator


mock_discord = MagicMock()
mock_discord.Client = MockClient
mock_discord.Intents = SimpleNamespace(default=lambda: object())
mock_discord.Interaction = object
mock_discord.File = MagicMock
mock_discord.SelectOption = MagicMock
mock_discord.Embed = MagicMock
mock_discord.ButtonStyle = MagicMock()
mock_discord.ui = SimpleNamespace(Select=MockSelect, View=MockView)
mock_discord.app_commands = SimpleNamespace(
    Choice=MockChoice,
    choices=_identity_decorator,
    describe=_identity_decorator,
    CommandTree=MockCommandTree,
)

mock_config = ModuleType("src.config")
mock_config.settings = SimpleNamespace(
    DATA_SERVICE_URL="http://data-service:8000",
    DISCORD_CHANNEL_FALLBACK=123,
    DISCORD_CHANNEL_ESM=456,
)

mock_chart = ModuleType("src.chart_generator")
mock_chart.ChartGenerator = SimpleNamespace(generate_chart=MagicMock())

mock_db = ModuleType("src.database")
mock_db.AsyncSessionLocal = MagicMock()

mock_httpx = ModuleType("httpx")
mock_httpx.AsyncClient = MagicMock()

with patch.dict(
    sys.modules,
    {
        "discord": mock_discord,
        "discord.ui": mock_discord.ui,
        "discord.app_commands": mock_discord.app_commands,
        "src.config": mock_config,
        "src.chart_generator": mock_chart,
        "src.database": mock_db,
        "httpx": mock_httpx,
    },
):
    from src import bot


def test_bot_instance_created():
    assert bot.bot is not None
    assert isinstance(bot.bot, bot.NotificationBot)


def test_alert_entry_and_exit_helpers():
    entry = {"crossover_type": "esm_entry", "condition_met": "ESM Entry", "direction": "bullish"}
    exit_signal = {"crossover_type": "pf_exit", "condition_met": "PF Exit", "direction": "bearish"}

    assert bot._is_entry_alert(entry) is True
    assert bot._is_exit_alert(entry) is False
    assert bot._is_exit_alert(exit_signal) is True
    assert bot._is_entry_alert(exit_signal) is False


def test_alert_icon_helper():
    entry = {"direction": "bullish"}
    exit_signal = {"direction": "bearish"}

    assert bot._alert_icon(entry) == "\U0001F7E2"
    assert bot._alert_icon(exit_signal) == "\U0001F534"


def test_summary_chart_view_adds_selector_when_symbols_present():
    view = bot.SummaryChartView(["AAPL", "MSFT"])
    assert len(view.items) == 1
