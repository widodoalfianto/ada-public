import pandas as pd
import mplfinance as mpf
import io
from sqlalchemy import text

class ChartGenerator:
    
    # --- Custom Colors ---
    COLORS = {
        'background': '#0a0e27',
        'grid': '#1a1f3a',
        'text': '#e0e6ed',
        'candle_up': '#26a69a',
        'candle_down': '#ef5350',
        'volume_up': '#26a69a',
        'volume_down': '#ef5350',
        'rsi': '#bb86fc',
        'rsi_zone': '#cf6679', 
        'macd': '#2196f3',
        'macd_signal': '#ff9800',
        'macd_hist_up': '#4caf50',
        'macd_hist_down': '#ef5350',
        'sma_50': '#ffd700',
        'sma_200': '#00bcd4',
        'ema_9': '#c3fa19', # Fluorescent Neon Green
        'sma_20': '#F81894' # Deep Pink / Bright Pink
    }

    @classmethod
    def _create_style(cls):
        """Creates the custom mplfinance style."""
        marketcolors = mpf.make_marketcolors(
            up=cls.COLORS['candle_up'],
            down=cls.COLORS['candle_down'],
            edge='inherit',
            wick='inherit',
            volume={'up': cls.COLORS['volume_up'], 'down': cls.COLORS['volume_down']},
            alpha=1.0
        )
        
        style = mpf.make_mpf_style(
            marketcolors=marketcolors,
            facecolor=cls.COLORS['background'],
            figcolor=cls.COLORS['background'],
            gridcolor=cls.COLORS['grid'],
            gridstyle='--',
            gridaxis='both',
            y_on_right=True,
            rc={
                'axes.labelsize': 8,
                'axes.titlesize': 10,
                'font.size': 8,
                'text.color': cls.COLORS['text'],
                'axes.labelcolor': cls.COLORS['text'],
                'xtick.color': cls.COLORS['text'],
                'ytick.color': cls.COLORS['text'],
                'axes.edgecolor': cls.COLORS['grid']
            }
        )
        return style

    @staticmethod
    async def generate_chart(symbol: str, db_session, indicators: list[str] = None, show_volume: bool = True) -> io.BytesIO:
        """
        Generates a professional candlestick chart.
        :param indicators: List of indicator names to include (e.g. ['sma_50', 'ema_9']). 
                           If None, defaults to showing all available.
        :param show_volume: Whether to show the volume panel.
        """
        # 1. Fetch Data
        result = await db_session.execute(text("SELECT id FROM stocks WHERE symbol = :symbol"), {"symbol": symbol})
        stock_row = result.fetchone()
        if not stock_row:
            return None
        stock_id = stock_row[0]

        query_prices = text("""
            SELECT date, open, high, low, close, volume 
            FROM price_data 
            WHERE stock_id = :stock_id 
            ORDER BY date DESC 
            LIMIT 120
        """)
        result_prices = await db_session.execute(query_prices, {"stock_id": stock_id})
        rows_prices = result_prices.fetchall()

        if not rows_prices:
            return None

        # DataFrame Setup
        df = pd.DataFrame(rows_prices, columns=['date', 'open', 'high', 'low', 'close', 'volume'])
        df['date'] = pd.to_datetime(df['date'])
        df.set_index('date', inplace=True)
        df.sort_index(inplace=True)

        # 2. Fetch Indicators
        min_date = df.index.min()
        query_indicators = text("""
            SELECT date, indicator_name, value 
            FROM indicators 
            WHERE stock_id = :stock_id AND date >= :min_date
        """)
        result_indicators = await db_session.execute(query_indicators, {"stock_id": stock_id, "min_date": min_date})
        rows_indicators = result_indicators.fetchall()

        if rows_indicators:
            ind_df = pd.DataFrame(rows_indicators, columns=['date', 'indicator_name', 'value'])
            ind_df['date'] = pd.to_datetime(ind_df['date'])
            ind_pivot = ind_df.pivot(index='date', columns='indicator_name', values='value')
            df = df.join(ind_pivot)

        # 2b. Fallback calc for key overlays when indicators are missing/partial
        def _needs_indicator(name: str) -> bool:
            if indicators is None:
                return True
            return name in indicators

        close = df['close']
        if _needs_indicator('ema_9'):
            ema_9 = close.ewm(span=9, adjust=False).mean()
            if 'ema_9' not in df.columns:
                df['ema_9'] = ema_9
            else:
                df['ema_9'] = df['ema_9'].fillna(ema_9)

        if _needs_indicator('sma_20'):
            sma_20 = close.rolling(window=20).mean()
            if 'sma_20' not in df.columns:
                df['sma_20'] = sma_20
            else:
                df['sma_20'] = df['sma_20'].fillna(sma_20)

        # 3. Data Prep (MACD Hist & Vol Colors)
        add_plots = []
        
        # Helper to check if we should show this indicator
        def should_show(name):
            if indicators is None: return True # Show all if no filter
            return name in indicators

        import matplotlib.lines as mlines

        # Overlays - Logic: check if column exists AND if it's requested
        # Note: make_addplot does not accept 'label', so we handle legend manually below
        if 'sma_50' in df.columns and should_show('sma_50'):
            add_plots.append(mpf.make_addplot(df['sma_50'], color=ChartGenerator.COLORS['sma_50'], width=1.0))
        if 'sma_200' in df.columns and should_show('sma_200'):
            add_plots.append(mpf.make_addplot(df['sma_200'], color=ChartGenerator.COLORS['sma_200'], width=1.0))
        if 'ema_9' in df.columns and should_show('ema_9'):
            add_plots.append(mpf.make_addplot(df['ema_9'], color=ChartGenerator.COLORS['ema_9'], width=1.5))
        if 'sma_20' in df.columns and should_show('sma_20'):
             add_plots.append(mpf.make_addplot(df['sma_20'], color=ChartGenerator.COLORS['sma_20'], width=1.5))

        # RSI (Panel 2)
        has_rsi = 'rsi_14' in df.columns and should_show('rsi_14')
        if has_rsi:
            # If volume is hidden, RSI might be panel 1? 
            # mplfinance logic: Panel 0 = Main. Panel 1 = Volume (if True).
            # If volume=False, Panel 1 is the next one.
            rsi_panel = 2 if show_volume else 1
            add_plots.append(mpf.make_addplot(df['rsi_14'], panel=rsi_panel, color=ChartGenerator.COLORS['rsi'], width=1.0, ylabel='RSI'))

        # MACD (Panel 3)
        has_macd = 'macd' in df.columns and 'macd_signal' in df.columns and (should_show('macd') or should_show('macd_signal'))
        if has_macd:
            df['macd_hist'] = df['macd'] - df['macd_signal']
            hist_colors = [ChartGenerator.COLORS['macd_hist_up'] if v >= 0 else ChartGenerator.COLORS['macd_hist_down'] for v in df['macd_hist']]
            
            # Panel index logic
            macd_panel = 3 if show_volume else 2
            if not has_rsi:
                macd_panel -= 1 # Shift up if no RSI
                
            add_plots.append(mpf.make_addplot(df['macd'], panel=macd_panel, color=ChartGenerator.COLORS['macd'], width=1.0, ylabel='MACD'))
            add_plots.append(mpf.make_addplot(df['macd_signal'], panel=macd_panel, color=ChartGenerator.COLORS['macd_signal'], width=1.0))
            add_plots.append(mpf.make_addplot(df['macd_hist'], panel=macd_panel, type='bar', color=hist_colors, alpha=0.5))

        # 4. Generate Plot
        buf = io.BytesIO()
        style = ChartGenerator._create_style()
        
        # Calculate panel ratios based on valid data
        panels = [6] # Price
        if show_volume: panels.append(1.5)
        if has_rsi: panels.append(1.5)
        if has_macd: panels.append(1.0)
        
        # Return Figure for customizations
        fig, axes = mpf.plot(
            df,
            type='candle',
            volume=show_volume,
            addplot=add_plots,
            style=style,
            returnfig=True,
            panel_ratios=panels,
            datetime_format='%b %d',
            xrotation=0,
            figsize=(14, 8),
            scale_padding={'left': 0.5, 'top': 0.8, 'right': 1.2, 'bottom': 0.5},
            tight_layout=True
        )

        # 5. Post-Process Formatting
        
        # Title Data
        last_close = df['close'].iloc[-1]
        prev_close = df['close'].iloc[-2]
        change_pct = ((last_close - prev_close) / prev_close) * 100
        title_color = ChartGenerator.COLORS['candle_up'] if change_pct >= 0 else ChartGenerator.COLORS['candle_down']
        
        # Main Title (Top Left of Price Panel)
        ax_main = axes[0]
        ax_main.text(
            0.01, 1.05, f"{symbol} Daily", 
            transform=ax_main.transAxes, 
            fontsize=16, 
            fontweight='bold',
            color=ChartGenerator.COLORS['text']
        )
        ax_main.text(
            0.01, 0.98, f"${last_close:.2f} ({change_pct:+.2f}%)", 
            transform=ax_main.transAxes, 
            fontsize=12, 
            color=title_color
        )
        
        # Grid adjustments if needed
        for ax in axes:
            ax.grid(True, color=ChartGenerator.COLORS['grid'], linestyle='--', linewidth=0.5)

        # Legend (Custom using Proxy Artists)
        legend_handles = []
        if 'sma_50' in df.columns and should_show('sma_50'):
            legend_handles.append(mlines.Line2D([], [], color=ChartGenerator.COLORS['sma_50'], linewidth=1.0, label=f"SMA 50 ({df['sma_50'].iloc[-1]:.2f})"))
        if 'sma_200' in df.columns and should_show('sma_200'):
            legend_handles.append(mlines.Line2D([], [], color=ChartGenerator.COLORS['sma_200'], linewidth=1.0, label=f"SMA 200 ({df['sma_200'].iloc[-1]:.2f})"))
        if 'ema_9' in df.columns and should_show('ema_9'):
            legend_handles.append(mlines.Line2D([], [], color=ChartGenerator.COLORS['ema_9'], linewidth=1.5, label=f"EMA 9 ({df['ema_9'].iloc[-1]:.2f})"))
        if 'sma_20' in df.columns and should_show('sma_20'):
            legend_handles.append(mlines.Line2D([], [], color=ChartGenerator.COLORS['sma_20'], linewidth=1.5, label=f"SMA 20 ({df['sma_20'].iloc[-1]:.2f})"))

        if legend_handles:
            # Move to Center Left as requested
            ax_main.legend(handles=legend_handles, loc='center left', framealpha=0.6, labelcolor=ChartGenerator.COLORS['text'], fontsize=8, facecolor=ChartGenerator.COLORS['background'], edgecolor=ChartGenerator.COLORS['grid'])

        # RSI Zones (if present)
        # panels: 0=Main, 2=Volume (mplfinance internal logic puts volume at index 2 if present? NO, wait.)
        # mpf panel order with volume=True: 
        # ax[0] = Main
        # ax[2] = Volume (usually)
        # It's safer to find the axis by knowing the panel index passed to addplot
        # Panel 0: Price, Panel 1: Volume (by default logic if volume=True is separate? No, MPF puts Volume at bottom usually unless panel specified)
        # Let's rely on the count. 
        # Axes list contains 2 * panels (main + secondary y). 
        # Standard: axes[0]=Main, axes[2]=Volume.
        # RSI Zones (if present)
        # Determine panel indices dynamically
        # Axes list has 2 entries per panel (primary + secondary y-axis)
        # Order: Main(0,1) -> [Volume(2,3)] -> [RSI(4,5 or 2,3)] -> [MACD(...)]
        
        current_ax_idx = 0
        current_ax_idx += 2 # Skip Main
        
        if show_volume:
            current_ax_idx += 2 # Skip Volume
            
        if has_rsi and len(axes) > current_ax_idx:
            ax_rsi = axes[current_ax_idx]
            ax_rsi.axhline(70, color=ChartGenerator.COLORS['rsi_zone'], linestyle='--', linewidth=0.8, alpha=0.7)
            ax_rsi.axhline(30, color=ChartGenerator.COLORS['candle_up'], linestyle='--', linewidth=0.8, alpha=0.7)
            ax_rsi.axhspan(70, 100, color=ChartGenerator.COLORS['rsi_zone'], alpha=0.1)
            ax_rsi.axhspan(0, 30, color=ChartGenerator.COLORS['candle_up'], alpha=0.1)
            ax_rsi.set_ylim(0, 100)
            current_ax_idx += 2 # Move past RSI
        
        if has_macd and len(axes) > current_ax_idx:
            # Maybe add zero line
            ax_macd = axes[current_ax_idx]
            ax_macd.axhline(0, color=ChartGenerator.COLORS['text'], linestyle=':', linewidth=0.5, alpha=0.5)

        # Save
        fig.savefig(buf, dpi=120, format='png', bbox_inches='tight', facecolor=ChartGenerator.COLORS['background'])
        buf.seek(0)
        return buf
