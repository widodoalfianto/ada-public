
import discord
from discord import app_commands
from discord import ui
import asyncio
import logging
import httpx
import datetime
from src.config import settings
from src.chart_generator import ChartGenerator
from src.database import AsyncSessionLocal
from src.rate_limiter import backtest_limiter, strategy_limiter

logger = logging.getLogger(__name__)


# --- Helpers ---
async def fetch_alert_history(target_date: str) -> list:
    """Helper to fetch alert history from Data Service."""
    url = f"{settings.DATA_SERVICE_URL}/api/alert-history"
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{url}?target_date={target_date}", timeout=10.0)
            if resp.status_code == 200:
                data = resp.json()
                return data.get("alerts", [])
            else:
                logger.error(f"Failed to fetch history: {resp.text}")
                return []
    except Exception as e:
        logger.error(f"Error fetching alerts: {e}")
        return []

# --- Strategies & Presets ---
STRATEGIES = {
    "ma_crossover": {"name": "9x20 MA Crossover", "params": {"fast": 9, "slow": 20}},
    "rsi_bounce": {"name": "RSI Bounce (30)", "params": {"rsi_buy": 30, "rsi_sell": 70}},
    "macd_cross": {"name": "MACD Crossover", "params": {}},
}

PERIODS = {
    "1M": 30,
    "3M": 90,
    "6M": 180,
    "1Y": 365,
    "2Y": 730,
}

DEFAULT_CAPITAL = 100000.0

# --- Morning Summary Chart Selector ---
class SummaryChartSelect(ui.Select):
    def __init__(self, symbols: list[str]):
        options = [discord.SelectOption(label=symbol, value=symbol) for symbol in symbols]
        super().__init__(
            placeholder="View chart for a symbol...",
            min_values=1,
            max_values=1,
            options=options
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
                    show_volume=False
                )
            file = discord.File(fp=image_buffer, filename=f"{symbol}.png")
            embed = discord.Embed(title=f"Chart: {symbol}", color=0x3498db)
            embed.set_image(url=f"attachment://{symbol}.png")
            await interaction.followup.send(embed=embed, file=file, ephemeral=True)
        except Exception as e:
            logger.error(f"Summary chart error for {symbol}: {e}", exc_info=True)
            await interaction.followup.send("❌ Failed to generate chart.", ephemeral=True)

class SummaryChartView(ui.View):
    def __init__(self, symbols: list[str]):
        super().__init__(timeout=900)
        if symbols:
            self.add_item(SummaryChartSelect(symbols))

# --- Modal: Backtest Form ---
class BacktestModal(ui.Modal, title="📊 Run Backtest"):
    symbol = ui.TextInput(
        label="Stock Symbol",
        placeholder="AAPL",
        required=True,
        max_length=10
    )
    capital = ui.TextInput(
        label="Initial Capital ($)",
        placeholder="100000",
        default="100000",
        required=True
    )
    
    def __init__(self, strategy: str = "ma_crossover", period: str = "1Y"):
        super().__init__()
        self.strategy = strategy
        self.period = period
    
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer()
        
        symbol = self.symbol.value.upper()
        try:
            capital = float(self.capital.value.replace(",", "").replace("$", ""))
        except ValueError:
            await interaction.followup.send("❌ Invalid capital amount.", ephemeral=True)
            return
        
        days = PERIODS.get(self.period, 365)
        await run_backtest_and_reply(interaction, symbol, self.strategy, days, capital)

# --- View: Strategy + Period Selectors ---
class BacktestSetupView(ui.View):
    def __init__(self):
        super().__init__(timeout=120)
        self.strategy = "ma_crossover"
        self.period = "1Y"
    
    @ui.select(
        placeholder="📈 Select Strategy",
        options=[
            discord.SelectOption(label="9x20 MA Crossover", value="ma_crossover", default=True),
            discord.SelectOption(label="RSI Bounce (30)", value="rsi_bounce"),
            discord.SelectOption(label="MACD Crossover", value="macd_cross"),
        ]
    )
    async def strategy_select(self, interaction: discord.Interaction, select: ui.Select):
        self.strategy = select.values[0]
        await interaction.response.defer()
    
    @ui.select(
        placeholder="📅 Select Period",
        options=[
            discord.SelectOption(label="1 Month", value="1M"),
            discord.SelectOption(label="3 Months", value="3M"),
            discord.SelectOption(label="6 Months", value="6M"),
            discord.SelectOption(label="1 Year", value="1Y", default=True),
            discord.SelectOption(label="2 Years", value="2Y"),
        ]
    )
    async def period_select(self, interaction: discord.Interaction, select: ui.Select):
        self.period = select.values[0]
        await interaction.response.defer()
    
    @ui.button(label="Continue", style=discord.ButtonStyle.primary, emoji="➡️")
    async def continue_button(self, interaction: discord.Interaction, button: ui.Button):
        modal = BacktestModal(strategy=self.strategy, period=self.period)
        await interaction.response.send_modal(modal)

# --- Shared Backtest Logic ---
async def run_backtest_and_reply(interaction: discord.Interaction, symbol: str, strategy: str, days: int, capital: float):
    end_date = datetime.date.today()
    start_date = end_date - datetime.timedelta(days=days)
    
    strat_config = STRATEGIES.get(strategy, STRATEGIES["ma_crossover"])
    
    payload = {
        "strategy": {
            "name": strat_config["name"],
            "type": strategy,
            "params": strat_config["params"]
        },
        "symbols": [symbol],
        "start_date": str(start_date),
        "end_date": str(end_date),
        "initial_capital": capital,
        "commission_per_share": 0.0,
        "slippage_percent": 0.0
    }
    
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(f"{settings.BACKTEST_SERVICE_URL}/api/backtest/run", json=payload, timeout=60.0)
        
        if resp.status_code != 200:
            await interaction.followup.send(f"❌ Backtest failed: {resp.text}")
            return

        result = resp.json()
        
        if isinstance(result, list):
            data = result[0]
        else:
            data = result
        
        metrics = data if "total_return_pct" in data else data.get("metrics", {})
        
        # Build Embed
        color = 0x26a69a if metrics.get('total_return_pct', 0) >= 0 else 0xef5350
        embed = discord.Embed(title=f"📊 Backtest: {symbol}", color=color)
        embed.add_field(name="Strategy", value=strat_config["name"], inline=True)
        embed.add_field(name="Period", value=f"{days} days", inline=True)
        embed.add_field(name="Capital", value=f"${capital:,.0f}", inline=True)
        embed.add_field(name="─" * 20, value="", inline=False)
        embed.add_field(name="📈 Total Return", value=f"**{metrics.get('total_return_pct', 0):.2f}%**", inline=True)
        embed.add_field(name="🎯 Win Rate", value=f"{metrics.get('win_rate', 0):.1f}%", inline=True)
        embed.add_field(name="💰 Final Equity", value=f"${metrics.get('final_capital', capital):,.2f}", inline=True)
        embed.add_field(name="📉 Trades", value=str(metrics.get('total_trades', 0)), inline=True)
        embed.add_field(name="🏆 Winners", value=str(metrics.get('winning_trades', 0)), inline=True)
        embed.add_field(name="❌ Losers", value=str(metrics.get('losing_trades', 0)), inline=True)
        
        # Add "Run Again" button for quick iteration
        view = QuickActionView(symbol)
        await interaction.followup.send(embed=embed, view=view)
        
    except httpx.RequestError as e:
        await interaction.followup.send(f"❌ Connection error: {e}")
    except Exception as e:
        logger.error(f"Backtest error: {e}", exc_info=True)
        await interaction.followup.send(f"❌ An error occurred: {e}")

# --- View: Quick Actions after Results ---
class QuickActionView(ui.View):
    def __init__(self, symbol: str):
        super().__init__(timeout=300)
        self.symbol = symbol
    
    @ui.button(label="Run Again (1Y)", style=discord.ButtonStyle.secondary, emoji="🔄")
    async def run_again(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.defer()
        await run_backtest_and_reply(interaction, self.symbol, "ma_crossover", 365, DEFAULT_CAPITAL)
    
    @ui.button(label="Try 2Y", style=discord.ButtonStyle.secondary, emoji="📅")
    async def try_2y(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.defer()
        await run_backtest_and_reply(interaction, self.symbol, "ma_crossover", 730, DEFAULT_CAPITAL)

# --- Bot Class ---
class NotificationBot(discord.Client):
    def __init__(self):
        intents = discord.Intents.default()
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)
        self.channel_id = settings.DISCORD_CHANNEL_FALLBACK
        self.ready_event = asyncio.Event()
        self.queue = asyncio.Queue()
        self.worker_task = None

    async def setup_hook(self):
        # For commercial/multi-server use, always use global sync
        # Global sync takes up to 1 hour to propagate but works across all servers
        await self.tree.sync()
        logger.info("Slash commands synced globally")

    async def on_ready(self):
        logger.info(f'Logged in as {self.user} (ID: {self.user.id})')
        self.ready_event.set()
        if not self.worker_task:
            self.worker_task = asyncio.create_task(self.worker_loop())
            logger.info("Rate-Limit Worker Queue started.")

    async def start_mock(self):
        """Start the bot in MOCK/OFFLINE mode."""
        logger.warning("⚠️  Starting Bot in MOCK MODE (No Discord Connection) ⚠️")
        self.ready_event.set()
        if not self.worker_task:
            self.worker_task = asyncio.create_task(self.worker_loop())
            logger.info("Mock Worker Queue started.")

    async def worker_loop(self):
        await self.ready_event.wait()
        while True:
            item = await self.queue.get()
            title, message, color, channel_id, image_buffer = item
            target_id = channel_id if channel_id else self.channel_id
            channel = self.get_channel(target_id)
            
            if channel:
                embed = discord.Embed(title=title, description=message, color=color)
                file = None
                if image_buffer:
                    image_buffer.seek(0)
                    file = discord.File(fp=image_buffer, filename="chart.png")
                    embed.set_image(url="attachment://chart.png")
                
                try:
                    logger.info(f"Sending to Channel ID: {target_id}")
                    if file:
                        await channel.send(embed=embed, file=file)
                    else:
                        await channel.send(embed=embed)
                    logger.info(f"✅ Sent successfully to {target_id}")
                    await asyncio.sleep(1.2)
                except discord.HTTPException as e:
                    if e.status == 429:
                        retry_after = e.response.headers.get('Retry-After', 2.0)
                        await asyncio.sleep(float(retry_after))
                    else:
                        logger.error(f"Discord API Error: {e}")
            else:
                logger.error(f"Channel {target_id} not found")
            self.queue.task_done()


    async def send_alert(self, title: str, message: str, color: int = 0x00ff00, channel_id: int = None, image_buffer = None):
        await self.queue.put((title, message, color, channel_id, image_buffer))

    async def send_morning_summary(self, target_date: datetime.date = None):
        """
        Fetch alert history for the given date (default: yesterday) 
        and send a summary report to the main channel.
        This is triggered by the Scheduler Service (via API call -> Bot method).
        """
        if target_date is None:
            # Default to yesterday (morning summary covers previous trading day)
            target_date = datetime.date.today() - datetime.timedelta(days=1)
            # If today is Monday, summary might cover Friday? 
            # Ideally scheduler passes the date. 
            # If scheduler calls at 8:30 AM Tuesday, it wants Monday's close signals.
        
        target_str = target_date.isoformat()
        logger.info(f"Generating Morning Summary for {target_str}")
        
        alerts = await fetch_alert_history(target_str)
            
        if not alerts:
            logger.info("No alerts found for summary.")
            return

        # Group by type
        golden = []
        death = []
        symbols = set()
        
        for a in alerts:
            # Format: SYMBOL ($Price) +Strength%
            strength = a['indicator_values'].get('strength', 0)
            line = f"**{a['symbol']}** (${a['price']:.2f}) `{strength:+.2f}%`"
            symbols.add(a['symbol'])
            
            if "golden" in a.get('crossover_type', '').lower():
                golden.append(line)
            elif "death" in a.get('crossover_type', '').lower():
                death.append(line)

        # Build Embed
        embed = discord.Embed(
            title=f"📋 Morning Watchlist - {datetime.date.today().strftime('%b %d, %Y')}",
            description=f"Recap of crossovers from **{target_date.strftime('%b %d')}**",
            color=0xffffff
        )
        
        if golden:
            embed.add_field(name="🟢 Golden Cross (Possible Entry)", value="\n".join(golden), inline=False)
        
        if death:
            embed.add_field(name="🔴 Death Cross (Check Exits)", value="\n".join(death), inline=False)
            
        embed.set_footer(text="Market opens in 1 hour • Use /chart <symbol> for details")

        # Add chart selector (Discord supports up to 25 options per select)
        sorted_symbols = sorted(symbols)
        chart_symbols = sorted_symbols[:25]
        view = SummaryChartView(chart_symbols) if chart_symbols else None
        if len(sorted_symbols) > 25:
            embed.add_field(
                name="📈 Charts",
                value="Select a symbol from the menu below (first 25 shown).",
                inline=False
            )
        elif chart_symbols:
            embed.add_field(
                name="📈 Charts",
                value="Select a symbol from the menu below.",
                inline=False
            )
        
        # Send to main channel (or configured channel)
        # Using Fallback or MA channel
        target_channel_id = settings.DISCORD_CHANNEL_MA or settings.DISCORD_CHANNEL_FALLBACK
        if not target_channel_id:
             logger.warning("No target channel configured for morning summary")
             return

        channel = self.get_channel(target_channel_id)
        if channel:
            if view:
                await channel.send(embed=embed, view=view)
            else:
                await channel.send(embed=embed)
            logger.info(f"Morning summary sent to {target_channel_id}")
        else:
            logger.error(f"Could not find channel {target_channel_id}")

    # --- New Slash Commands ---
    
    async def fetch_todays_alerts(self, interaction: discord.Interaction):
        """Helper to fetch and display today's alerts."""
        today = datetime.date.today()
        # If it's before 9 AM, maybe show yesterday's? 
        # User asked for "today's alerts", sticking to today.
        
        target_str = today.isoformat()
        
        alerts = await fetch_alert_history(target_str)

        if not alerts:
            await interaction.followup.send("📭 No alerts generated yet today.")
            return

        embed = discord.Embed(title=f"🔔 Alerts for Today ({today.strftime('%b %d')})", color=0x3498db)
        
        lines = []
        for a in alerts:
            icon = "🟢" if "golden" in a.get('crossover_type', '') else "🔴"
            time_str = datetime.datetime.fromisoformat(a['triggered_at']).strftime('%H:%M')
            lines.append(f"`{time_str}` {icon} **{a['symbol']}** {a['condition_met']}")
            
        embed.description = "\n".join(lines)
        await interaction.followup.send(embed=embed)

bot = NotificationBot()

@bot.tree.command(name="alerts", description="View recent alerts")
@app_commands.choices(period=[
    app_commands.Choice(name="Today", value="today"),
    app_commands.Choice(name="Yesterday", value="yesterday")
])
async def alerts_command(interaction: discord.Interaction, period: app_commands.Choice[str]):
    """View alerts for today or yesterday."""
    await interaction.response.defer()
    
    if period.value == "today":
        await bot.fetch_todays_alerts(interaction)
    else:
        # Re-use logic for yesterday requires param change if extracted
        # For simplicity, implementing inline or refactoring if needed.
        # Let's simple-implement yesterday here by copying logic or making helper flexible
        pass
        # (Implementing yesterday fetch in helper would be better, but for brevity...)
        target_date = datetime.date.today() - datetime.timedelta(days=1)
        target_str = target_date.isoformat()
        alerts = await fetch_alert_history(target_str)

        if not alerts:
             await interaction.followup.send(f"📭 No alerts found for {target_date}.")
             return

        embed = discord.Embed(title=f"🔔 Alerts for {target_date.strftime('%b %d')}", color=0x95a5a6)
        lines = []
        for a in alerts:
            icon = "🟢" if "golden" in a.get('crossover_type', '') else "🔴"
            lines.append(f"{icon} **{a['symbol']}** ({a['condition_met']})")
        embed.description = "\n".join(lines)
        await interaction.followup.send(embed=embed)


# --- Slash Commands ---

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
                show_volume=False
            )
        file = discord.File(fp=image_buffer, filename=f"{symbol}.png")
        embed = discord.Embed(title=f"Chart: {symbol}", color=0x3498db)
        embed.set_image(url=f"attachment://{symbol}.png")
        await interaction.followup.send(embed=embed, file=file, ephemeral=True)
    except Exception as e:
        logger.error(f"Chart command error for {symbol}: {e}", exc_info=True)
        await interaction.followup.send("❌ Failed to generate chart.", ephemeral=True)

@bot.tree.command(name="backtest", description="Run a backtest simulation with an interactive form")
async def backtest_command(interaction: discord.Interaction):
    """Opens a modal form for backtest configuration."""
    # Rate limiting check
    is_allowed, remaining = await backtest_limiter.check(interaction.user.id)
    if not is_allowed:
        await interaction.response.send_message(
            backtest_limiter.get_cooldown_message(remaining),
            ephemeral=True
        )
        return
    
    # Channel restriction
    if settings.DISCORD_CHANNEL_BACKTEST and interaction.channel_id != settings.DISCORD_CHANNEL_BACKTEST:
        await interaction.response.send_message(
            f"❌ This command can only be used in <#{settings.DISCORD_CHANNEL_BACKTEST}>",
            ephemeral=True
        )
        return
    
    embed = discord.Embed(
        title="📊 Backtest Configuration",
        description="Select your **strategy** and **time period**, then click **Continue** to enter the stock symbol.",
        color=0x00b0f4
    )
    view = BacktestSetupView()
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

@bot.tree.command(name="quick", description="Run a quick backtest with default settings")
@app_commands.describe(symbol="Stock symbol (e.g. AAPL)")
async def quick_command(interaction: discord.Interaction, symbol: str):
    """Quick backtest: 9x20 MA, 1Y, $100k."""
    # Rate limiting check
    is_allowed, remaining = await backtest_limiter.check(interaction.user.id)
    if not is_allowed:
        await interaction.response.send_message(
            backtest_limiter.get_cooldown_message(remaining),
            ephemeral=True
        )
        return
    
    # Channel restriction
    if settings.DISCORD_CHANNEL_BACKTEST and interaction.channel_id != settings.DISCORD_CHANNEL_BACKTEST:
        await interaction.response.send_message(
            f"❌ This command can only be used in <#{settings.DISCORD_CHANNEL_BACKTEST}>",
            ephemeral=True
        )
        return
    
    await interaction.response.defer()
    await run_backtest_and_reply(interaction, symbol.upper(), "ma_crossover", 365, DEFAULT_CAPITAL)

# =============================================================================
# STRATEGY BUILDER
# =============================================================================

# Condition types for dropdowns
CONDITION_OPTIONS = [
    discord.SelectOption(label="RSI Below Threshold", value="rsi_below", emoji="📉"),
    discord.SelectOption(label="RSI Above Threshold", value="rsi_above", emoji="📈"),
    discord.SelectOption(label="MA Cross Up (EMA > SMA)", value="ma_cross_up", emoji="🔼"),
    discord.SelectOption(label="MA Cross Down (EMA < SMA)", value="ma_cross_down", emoji="🔽"),
    discord.SelectOption(label="Price Above SMA", value="price_above_sma", emoji="⬆️"),
    discord.SelectOption(label="Price Below SMA", value="price_below_sma", emoji="⬇️"),
    discord.SelectOption(label="Volume Spike", value="volume_spike", emoji="📊"),
]

# Modal for RSI condition
class RSIConditionModal(ui.Modal, title="RSI Condition"):
    period = ui.TextInput(label="RSI Period", default="14", max_length=3)
    threshold = ui.TextInput(label="Threshold", default="30", max_length=3)
    
    def __init__(self, comparison: str, builder_view: "StrategyBuilderView", is_entry: bool):
        super().__init__()
        self.comparison = comparison
        self.builder_view = builder_view
        self.is_entry = is_entry
    
    async def on_submit(self, interaction: discord.Interaction):
        cond = {
            "indicator": "rsi",
            "comparison": self.comparison,
            "params": {"period": int(self.period.value), "threshold": int(self.threshold.value)}
        }
        if self.is_entry:
            self.builder_view.entry_conditions.append(cond)
        else:
            self.builder_view.exit_conditions.append(cond)
        await self.builder_view.update_embed(interaction)

# Modal for MA Cross condition
class MACrossModal(ui.Modal, title="MA Cross Condition"):
    fast_period = ui.TextInput(label="Fast MA Period (EMA)", default="9", max_length=3)
    slow_period = ui.TextInput(label="Slow MA Period (SMA)", default="20", max_length=3)
    
    def __init__(self, comparison: str, builder_view: "StrategyBuilderView", is_entry: bool):
        super().__init__()
        self.comparison = comparison
        self.builder_view = builder_view
        self.is_entry = is_entry
    
    async def on_submit(self, interaction: discord.Interaction):
        cond = {
            "indicator": "ma_cross",
            "comparison": self.comparison,
            "params": {"fast_period": int(self.fast_period.value), "slow_period": int(self.slow_period.value)}
        }
        if self.is_entry:
            self.builder_view.entry_conditions.append(cond)
        else:
            self.builder_view.exit_conditions.append(cond)
        await self.builder_view.update_embed(interaction)

# Modal for Price vs SMA condition
class PriceSMAModal(ui.Modal, title="Price vs SMA"):
    sma_period = ui.TextInput(label="SMA Period", default="50", max_length=3)
    
    def __init__(self, comparison: str, builder_view: "StrategyBuilderView", is_entry: bool):
        super().__init__()
        self.comparison = comparison
        self.builder_view = builder_view
        self.is_entry = is_entry
    
    async def on_submit(self, interaction: discord.Interaction):
        cond = {
            "indicator": "price_vs_sma",
            "comparison": self.comparison,
            "params": {"sma_period": int(self.sma_period.value)}
        }
        if self.is_entry:
            self.builder_view.entry_conditions.append(cond)
        else:
            self.builder_view.exit_conditions.append(cond)
        await self.builder_view.update_embed(interaction)

# Modal for Volume condition
class VolumeModal(ui.Modal, title="Volume Spike"):
    multiplier = ui.TextInput(label="Volume Multiplier (e.g. 1.5 = 150% of avg)", default="1.5", max_length=4)
    
    def __init__(self, builder_view: "StrategyBuilderView", is_entry: bool):
        super().__init__()
        self.builder_view = builder_view
        self.is_entry = is_entry
    
    async def on_submit(self, interaction: discord.Interaction):
        cond = {
            "indicator": "volume",
            "comparison": ">",
            "params": {"multiplier": float(self.multiplier.value)}
        }
        if self.is_entry:
            self.builder_view.entry_conditions.append(cond)
        else:
            self.builder_view.exit_conditions.append(cond)
        await self.builder_view.update_embed(interaction)

# Modal for Symbol and Capital before running
class StrategyRunModal(ui.Modal, title="Run Custom Strategy"):
    symbol = ui.TextInput(label="Stock Symbol", placeholder="AAPL", max_length=10)
    capital = ui.TextInput(label="Initial Capital ($)", default="100000")
    days = ui.TextInput(label="Backtest Days", default="365", max_length=4)
    
    def __init__(self, strategy_dict: dict):
        super().__init__()
        self.strategy_dict = strategy_dict
    
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer()
        
        symbol = self.symbol.value.upper()
        try:
            capital = float(self.capital.value.replace(",", "").replace("$", ""))
            days = int(self.days.value)
        except ValueError:
            await interaction.followup.send("❌ Invalid input.", ephemeral=True)
            return
        
        await run_custom_backtest(interaction, symbol, self.strategy_dict, days, capital)

# Main Strategy Builder View
class StrategyBuilderView(ui.View):
    def __init__(self):
        super().__init__(timeout=300)
        self.entry_conditions = []
        self.exit_conditions = []
        self.adding_entry = True  # Track which type we're adding
        self.message = None
    
    def describe_condition(self, c: dict) -> str:
        ind = c["indicator"]
        comp = c["comparison"]
        params = c.get("params", {})
        
        if ind == "rsi":
            return f"RSI({params.get('period', 14)}) {comp} {params.get('threshold', 30)}"
        elif ind == "ma_cross":
            arrow = "↑" if comp == "cross_up" else "↓"
            return f"EMA({params.get('fast_period', 9)}) {arrow} SMA({params.get('slow_period', 20)})"
        elif ind == "price_vs_sma":
            op = ">" if comp == ">" else "<"
            return f"Price {op} SMA({params.get('sma_period', 50)})"
        elif ind == "volume":
            return f"Volume > {params.get('multiplier', 1.5)}x Avg"
        return str(c)
    
    def build_embed(self) -> discord.Embed:
        embed = discord.Embed(title="🛠️ Strategy Builder", color=0x9b59b6)
        
        entry_text = "\n".join(f"  ✅ {self.describe_condition(c)}" for c in self.entry_conditions) or "  (none)"
        exit_text = "\n".join(f"  🚪 {self.describe_condition(c)}" for c in self.exit_conditions) or "  (none)"
        
        embed.add_field(name="📥 Entry Conditions (AND)", value=entry_text, inline=False)
        embed.add_field(name="📤 Exit Conditions (OR)", value=exit_text, inline=False)
        embed.set_footer(text="Add conditions, then click 'Run Backtest' to test your strategy.")
        return embed
    
    async def update_embed(self, interaction: discord.Interaction):
        await interaction.response.edit_message(embed=self.build_embed(), view=self)
    
    @ui.button(label="+ Entry", style=discord.ButtonStyle.success, emoji="📥", row=0)
    async def add_entry(self, interaction: discord.Interaction, button: ui.Button):
        self.adding_entry = True
        select_view = ConditionSelectView(self, is_entry=True)
        await interaction.response.edit_message(
            embed=discord.Embed(title="Select Entry Condition Type", color=0x2ecc71),
            view=select_view
        )
    
    @ui.button(label="+ Exit", style=discord.ButtonStyle.danger, emoji="📤", row=0)
    async def add_exit(self, interaction: discord.Interaction, button: ui.Button):
        self.adding_entry = False
        select_view = ConditionSelectView(self, is_entry=False)
        await interaction.response.edit_message(
            embed=discord.Embed(title="Select Exit Condition Type", color=0xe74c3c),
            view=select_view
        )
    
    @ui.button(label="Clear All", style=discord.ButtonStyle.secondary, emoji="🗑️", row=0)
    async def clear_all(self, interaction: discord.Interaction, button: ui.Button):
        self.entry_conditions.clear()
        self.exit_conditions.clear()
        await self.update_embed(interaction)
    
    @ui.button(label="Run Backtest", style=discord.ButtonStyle.primary, emoji="▶️", row=1)
    async def run_backtest(self, interaction: discord.Interaction, button: ui.Button):
        if not self.entry_conditions:
            await interaction.response.send_message("❌ Add at least one entry condition.", ephemeral=True)
            return
        
        strategy_dict = {
            "name": "Custom Strategy",
            "type": "custom",
            "entry_conditions": self.entry_conditions,
            "exit_conditions": self.exit_conditions
        }
        modal = StrategyRunModal(strategy_dict)
        await interaction.response.send_modal(modal)

# Select view for choosing condition type
class ConditionSelectView(ui.View):
    def __init__(self, builder_view: StrategyBuilderView, is_entry: bool):
        super().__init__(timeout=60)
        self.builder_view = builder_view
        self.is_entry = is_entry
    
    @ui.select(placeholder="Choose condition type...", options=CONDITION_OPTIONS)
    async def condition_select(self, interaction: discord.Interaction, select: ui.Select):
        value = select.values[0]
        
        if value == "rsi_below":
            await interaction.response.send_modal(RSIConditionModal("<", self.builder_view, self.is_entry))
        elif value == "rsi_above":
            await interaction.response.send_modal(RSIConditionModal(">", self.builder_view, self.is_entry))
        elif value == "ma_cross_up":
            await interaction.response.send_modal(MACrossModal("cross_up", self.builder_view, self.is_entry))
        elif value == "ma_cross_down":
            await interaction.response.send_modal(MACrossModal("cross_down", self.builder_view, self.is_entry))
        elif value == "price_above_sma":
            await interaction.response.send_modal(PriceSMAModal(">", self.builder_view, self.is_entry))
        elif value == "price_below_sma":
            await interaction.response.send_modal(PriceSMAModal("<", self.builder_view, self.is_entry))
        elif value == "volume_spike":
            await interaction.response.send_modal(VolumeModal(self.builder_view, self.is_entry))
    
    @ui.button(label="Back", style=discord.ButtonStyle.secondary, emoji="⬅️")
    async def back_button(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.edit_message(embed=self.builder_view.build_embed(), view=self.builder_view)

# Custom backtest runner
async def run_custom_backtest(interaction: discord.Interaction, symbol: str, strategy_dict: dict, days: int, capital: float):
    end_date = datetime.date.today()
    start_date = end_date - datetime.timedelta(days=days)
    
    payload = {
        "strategy": strategy_dict,
        "symbols": [symbol],
        "start_date": str(start_date),
        "end_date": str(end_date),
        "initial_capital": capital,
        "commission_per_share": 0.0,
        "slippage_percent": 0.0
    }
    
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(f"{settings.BACKTEST_SERVICE_URL}/api/backtest/run", json=payload, timeout=60.0)
        
        if resp.status_code != 200:
            await interaction.followup.send(f"❌ Backtest failed: {resp.text}")
            return

        result = resp.json()
        data = result[0] if isinstance(result, list) else result
        metrics = data if "total_return_pct" in data else data.get("metrics", {})
        
        color = 0x26a69a if metrics.get('total_return_pct', 0) >= 0 else 0xef5350
        embed = discord.Embed(title=f"📊 Custom Strategy: {symbol}", color=color)
        embed.add_field(name="Period", value=f"{days} days", inline=True)
        embed.add_field(name="Capital", value=f"${capital:,.0f}", inline=True)
        embed.add_field(name="─" * 20, value="", inline=False)
        embed.add_field(name="📈 Total Return", value=f"**{metrics.get('total_return_pct', 0):.2f}%**", inline=True)
        embed.add_field(name="🎯 Win Rate", value=f"{metrics.get('win_rate', 0):.1f}%", inline=True)
        embed.add_field(name="💰 Final Equity", value=f"${metrics.get('final_capital', capital):,.2f}", inline=True)
        embed.add_field(name="📉 Trades", value=str(metrics.get('total_trades', 0)), inline=True)
        embed.add_field(name="🏆 Winners", value=str(metrics.get('winning_trades', 0)), inline=True)
        embed.add_field(name="❌ Losers", value=str(metrics.get('losing_trades', 0)), inline=True)
        
        await interaction.followup.send(embed=embed)
        
    except httpx.RequestError as e:
        await interaction.followup.send(f"❌ Connection error: {e}")
    except Exception as e:
        logger.error(f"Custom backtest error: {e}", exc_info=True)
        await interaction.followup.send(f"❌ An error occurred: {e}")

# /strategy command
@bot.tree.command(name="strategy", description="Build a custom multi-indicator trading strategy")
async def strategy_command(interaction: discord.Interaction):
    """Opens the Strategy Builder interface."""
    # Rate limiting check
    is_allowed, remaining = await strategy_limiter.check(interaction.user.id)
    if not is_allowed:
        await interaction.response.send_message(
            strategy_limiter.get_cooldown_message(remaining),
            ephemeral=True
        )
        return
    
    if settings.DISCORD_CHANNEL_BACKTEST and interaction.channel_id != settings.DISCORD_CHANNEL_BACKTEST:
        await interaction.response.send_message(
            f"❌ This command can only be used in <#{settings.DISCORD_CHANNEL_BACKTEST}>",
            ephemeral=True
        )
        return
    
    view = StrategyBuilderView()
    embed = view.build_embed()
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

