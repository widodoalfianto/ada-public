import asyncio
import datetime
import logging
from typing import Optional

import discord
import httpx
from discord import app_commands
from discord import ui

from src.chart_generator import ChartGenerator
from src.config import settings
from src.database import AsyncSessionLocal

logger = logging.getLogger(__name__)


async def fetch_alert_history(target_date: str) -> list[dict]:
    """Fetch alert history for a date from data-service."""
    url = f"{settings.DATA_SERVICE_URL}/api/alert-history"
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{url}?target_date={target_date}", timeout=10.0)
            if resp.status_code == 200:
                data = resp.json()
                return data.get("alerts", [])
            logger.error(f"Failed to fetch history: {resp.text}")
            return []
    except Exception as e:
        logger.error(f"Error fetching alerts: {e}")
        return []


def _is_entry_alert(alert: dict) -> bool:
    crossover_type = str(alert.get("crossover_type", "")).lower()
    condition_met = str(alert.get("condition_met", "")).lower()
    direction = str(alert.get("direction", "")).lower()
    return "entry" in crossover_type or "entry" in condition_met or direction == "bullish"


def _is_exit_alert(alert: dict) -> bool:
    crossover_type = str(alert.get("crossover_type", "")).lower()
    condition_met = str(alert.get("condition_met", "")).lower()
    direction = str(alert.get("direction", "")).lower()
    return "exit" in crossover_type or "exit" in condition_met or direction == "bearish"


def _alert_icon(alert: dict) -> str:
    return "\U0001F7E2" if _is_entry_alert(alert) else "\U0001F534"


class SummaryChartSelect(ui.Select):
    def __init__(self, symbols: list[str]):
        options = [discord.SelectOption(label=symbol, value=symbol) for symbol in symbols]
        super().__init__(
            placeholder="View chart for a symbol...",
            min_values=1,
            max_values=1,
            options=options,
        )

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        symbol = self.values[0].upper()
        try:
            async with AsyncSessionLocal() as session:
                image_buffer = await ChartGenerator.generate_chart(
                    symbol,
                    session,
                    indicators=["ema_9", "sma_20"],
                    show_volume=False,
                )
            file = discord.File(fp=image_buffer, filename=f"{symbol}.png")
            embed = discord.Embed(title=f"Chart: {symbol}", color=0x3498DB)
            embed.set_image(url=f"attachment://{symbol}.png")
            await interaction.followup.send(embed=embed, file=file, ephemeral=True)
        except Exception as e:
            logger.error(f"Summary chart error for {symbol}: {e}", exc_info=True)
            await interaction.followup.send("Failed to generate chart.", ephemeral=True)


class SummaryChartView(ui.View):
    def __init__(self, symbols: list[str]):
        super().__init__(timeout=900)
        if symbols:
            self.add_item(SummaryChartSelect(symbols))


class NotificationBot(discord.Client):
    def __init__(self):
        intents = discord.Intents.default()
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)
        self.channel_id = settings.DISCORD_CHANNEL_FALLBACK
        self.ready_event = asyncio.Event()
        self.queue = asyncio.Queue()
        self.worker_task: Optional[asyncio.Task] = None

    async def setup_hook(self):
        await self.tree.sync()
        logger.info("Slash commands synced globally")

    async def on_ready(self):
        logger.info(f"Logged in as {self.user} (ID: {self.user.id})")
        self.ready_event.set()
        if not self.worker_task:
            self.worker_task = asyncio.create_task(self.worker_loop())
            logger.info("Notification worker queue started")

    async def start_mock(self):
        """Start in offline mode without Discord connection."""
        logger.warning("Starting bot in MOCK MODE (no Discord connection).")
        self.ready_event.set()
        if not self.worker_task:
            self.worker_task = asyncio.create_task(self.worker_loop())
            logger.info("Mock worker queue started")

    async def worker_loop(self):
        await self.ready_event.wait()
        while True:
            title, message, color, channel_id, image_buffer = await self.queue.get()
            target_id = channel_id if channel_id else self.channel_id
            channel = self.get_channel(target_id)
            try:
                if channel:
                    embed = discord.Embed(title=title, description=message, color=color)
                    file = None
                    if image_buffer:
                        image_buffer.seek(0)
                        file = discord.File(fp=image_buffer, filename="chart.png")
                        embed.set_image(url="attachment://chart.png")

                    if file:
                        await channel.send(embed=embed, file=file)
                    else:
                        await channel.send(embed=embed)
                    await asyncio.sleep(1.2)
                else:
                    logger.error(f"Channel {target_id} not found")
            except discord.HTTPException as e:
                if e.status == 429:
                    retry_after = e.response.headers.get("Retry-After", 2.0)
                    await asyncio.sleep(float(retry_after))
                else:
                    logger.error(f"Discord API error: {e}")
            finally:
                self.queue.task_done()

    async def send_alert(
        self,
        title: str,
        message: str,
        color: int = 0x00FF00,
        channel_id: int = None,
        image_buffer=None,
    ):
        await self.queue.put((title, message, color, channel_id, image_buffer))

    async def send_morning_summary(self, target_date: datetime.date = None):
        """
        Summarize prior-day signals from data-service and post in Discord.
        """
        if target_date is None:
            target_date = datetime.date.today() - datetime.timedelta(days=1)

        target_str = target_date.isoformat()
        logger.info(f"Generating morning summary for {target_str}")
        alerts = await fetch_alert_history(target_str)
        if not alerts:
            logger.info("No alerts found for summary")
            return

        entries: list[str] = []
        exits: list[str] = []
        symbols: set[str] = set()
        for alert in alerts:
            strength = alert.get("indicator_values", {}).get("strength", 0)
            line = f"**{alert['symbol']}** (${alert['price']:.2f}) `{strength:+.2f}%`"
            symbols.add(alert["symbol"])
            if _is_entry_alert(alert):
                entries.append(line)
            elif _is_exit_alert(alert):
                exits.append(line)

        embed = discord.Embed(
            title=f"Morning Watchlist - {datetime.date.today().strftime('%b %d, %Y')}",
            description=f"Recap of entry/exit signals from {target_date.strftime('%b %d')}",
            color=0xFFFFFF,
        )
        if entries:
            embed.add_field(name="Entry Signals", value="\n".join(entries), inline=False)
        if exits:
            embed.add_field(name="Exit Signals", value="\n".join(exits), inline=False)
        embed.set_footer(text="Use /chart <symbol> for details")

        sorted_symbols = sorted(symbols)
        chart_symbols = sorted_symbols[:25]
        view = SummaryChartView(chart_symbols) if chart_symbols else None

        target_channel_id = settings.DISCORD_CHANNEL_ESM or settings.DISCORD_CHANNEL_FALLBACK
        if not target_channel_id:
            logger.warning("No target channel configured for morning summary")
            return

        channel = self.get_channel(target_channel_id)
        if not channel:
            logger.error(f"Could not find channel {target_channel_id}")
            return

        if view:
            await channel.send(embed=embed, view=view)
        else:
            await channel.send(embed=embed)
        logger.info(f"Morning summary sent to {target_channel_id}")

    async def fetch_todays_alerts(self, interaction: discord.Interaction):
        today = datetime.date.today()
        alerts = await fetch_alert_history(today.isoformat())
        if not alerts:
            await interaction.followup.send("No alerts generated yet today.")
            return

        embed = discord.Embed(title=f"Alerts for Today ({today.strftime('%b %d')})", color=0x3498DB)
        lines = []
        for alert in alerts:
            icon = _alert_icon(alert)
            time_str = datetime.datetime.fromisoformat(alert["triggered_at"]).strftime("%H:%M")
            lines.append(f"`{time_str}` {icon} **{alert['symbol']}** {alert['condition_met']}")
        embed.description = "\n".join(lines)
        await interaction.followup.send(embed=embed)


bot = NotificationBot()


@bot.tree.command(name="alerts", description="View recent alerts")
@app_commands.choices(
    period=[
        app_commands.Choice(name="Today", value="today"),
        app_commands.Choice(name="Yesterday", value="yesterday"),
    ]
)
async def alerts_command(interaction: discord.Interaction, period: app_commands.Choice[str]):
    await interaction.response.defer()
    if period.value == "today":
        await bot.fetch_todays_alerts(interaction)
        return

    target_date = datetime.date.today() - datetime.timedelta(days=1)
    alerts = await fetch_alert_history(target_date.isoformat())
    if not alerts:
        await interaction.followup.send(f"No alerts found for {target_date}.")
        return

    embed = discord.Embed(title=f"Alerts for {target_date.strftime('%b %d')}", color=0x95A5A6)
    lines = [f"{_alert_icon(a)} **{a['symbol']}** ({a['condition_met']})" for a in alerts]
    embed.description = "\n".join(lines)
    await interaction.followup.send(embed=embed)


@bot.tree.command(name="chart", description="Show EMA9/SMA20 chart for a symbol")
@app_commands.describe(symbol="Stock symbol (e.g. AAPL)")
async def chart_command(interaction: discord.Interaction, symbol: str):
    await interaction.response.defer(ephemeral=True)
    symbol = symbol.upper()
    try:
        async with AsyncSessionLocal() as session:
            image_buffer = await ChartGenerator.generate_chart(
                symbol,
                session,
                indicators=["ema_9", "sma_20"],
                show_volume=False,
            )
        file = discord.File(fp=image_buffer, filename=f"{symbol}.png")
        embed = discord.Embed(title=f"Chart: {symbol}", color=0x3498DB)
        embed.set_image(url=f"attachment://{symbol}.png")
        await interaction.followup.send(embed=embed, file=file, ephemeral=True)
    except Exception as e:
        logger.error(f"Chart command error for {symbol}: {e}", exc_info=True)
        await interaction.followup.send("Failed to generate chart.", ephemeral=True)
