# Backtesting Framework

A standardized framework for testing trading strategies on historical data.

## Quick Start

### 1. Test on Single Stock
```bash
python scripts/test_single.py triple_confirmation.json AAPL
```

### 2. Save Results with Full Metrics (54 metrics calculated)
```bash
python scripts/test_single.py moderate_filter.json AAPL \
  --save \
  --tags "baseline,production" \
  --notes "Production baseline run" \
  --baseline
```

### 3. Test on List of Stocks
```bash
python scripts/test_list.py triple_confirmation.json AAPL MSFT GOOGL AMZN --save
```

### 4. Test on All S&P 500
```bash
python scripts/test_all_sp500.py triple_confirmation.json
```

### 5. Compare Multiple Strategies
```bash
python scripts/compare_strategies.py simple_ma_crossover.json triple_confirmation.json
```

---

## Features

- **Comprehensive Metrics**: 54 performance metrics (Sharpe, Sortino, CAGR, Win Rate, Max Drawdown, etc.)
- **4-Table Schema**: Detailed tracking in `backtests`, `backtest_performance`, `backtest_trades`, `backtest_tags`
- **Categorization**: Tag-based organization and baseline tracking
- **Constants-Based**: All magic numbers in `src/constants.py` for easy configuration
- **Proper Logging**: Structured logging throughout (no more print statements)

---

## Strategy Definitions

Strategies are defined in JSON format in the `strategies/` directory.

### Available Strategies

| Strategy | Description | Type |
|----------|-------------|------|
| `simple_ma_crossover.json` | EMA 9 x SMA 20 with no filters | ma_crossover |
| `triple_confirmation.json` | MA cross + RSI + Volume + Trend | multi_indicator |
| `moderate_filter.json` | MA cross + relaxed filters | multi_indicator |

### Strategy JSON Format

```json
{
  "name": "My Strategy",
  "description": "Brief description",
  "type": "ma_crossover | multi_indicator | rsi_extremes",
  "params": {
    "rsi_min": 30,
    "rsi_max": 70,
    "volume_multiplier": 1.5,
    "require_trend": true
  },
  "execution": {
    "long_only": true,
    "initial_capital": 100000,
    "position_size_pct": 0.02,
    "commission_per_share": 0.005,
    "slippage_percent": 0.001,
    "exit_after_days": 20,
    "stop_loss_pct": -5.0,
    "take_profit_pct": 10.0
  }
}
```

---

## CLI Reference

### test_single.py
Test strategy on a single stock.

```bash
python scripts/test_single.py <strategy.json> <SYMBOL> [--start YYYY-MM-DD] [--end YYYY-MM-DD]

# Examples
python scripts/test_single.py triple_confirmation.json AAPL
python scripts/test_single.py simple_ma_crossover.json TSLA --start 2024-01-01
```

### test_list.py
Test strategy on multiple stocks.

```bash
python scripts/test_list.py <strategy.json> <SYMBOL1> <SYMBOL2> ... [options]
python scripts/test_list.py <strategy.json> --file symbols.txt [options]

# Examples
python scripts/test_list.py triple_confirmation.json AAPL MSFT GOOGL
python scripts/test_list.py moderate_filter.json --file faang.txt --start 2024-01-01
```

### test_all_sp500.py
Test strategy on all S&P 500 stocks in database.

```bash
python scripts/test_all_sp500.py <strategy.json> [--start YYYY-MM-DD] [--end YYYY-MM-DD] [--top N]

# Examples
python scripts/test_all_sp500.py triple_confirmation.json
python scripts/test_all_sp500.py moderate_filter.json --top 50  # Test top 50 only
```

### compare_strategies.py
Compare multiple strategies side-by-side.

```bash
python scripts/compare_strategies.py <strategy1.json> <strategy2.json> ... [options]

# Examples
python scripts/compare_strategies.py simple_ma_crossover.json triple_confirmation.json
python scripts/compare_strategies.py *.json --symbols AAPL MSFT
python scripts/compare_strategies.py *.json --all  # Test all S&P 500
```

---

## Creating New Strategies

1. Copy an existing strategy JSON from `strategies/`
2. Modify the parameters
3. Save with a descriptive name
4. Test it!

### Example: Creating a Relaxed RSI Strategy

```json
{
  "name": "Relaxed RSI + MA",
  "description": "MA crossover with very relaxed RSI filter",
  "type": "multi_indicator",
  "params": {
    "rsi_min": 20,
    "rsi_max": 80,
    "volume_multiplier": 1.0,
    "require_trend": false
  },
  "execution": {
    "long_only": true,
    "initial_capital": 100000,
    "exit_after_days": 30,
    "stop_loss_pct": -7.0,
    "take_profit_pct": 15.0
  }
}
```

---

## Strategy Types

### 1. `ma_crossover`
Simple moving average crossover (EMA 9 x SMA 20).

**Params:** None (fixed to EMA 9 vs SMA 20)

### 2. `multi_indicator`
Triple confirmation with multiple filters.

**Params:**
- `rsi_min`: Minimum RSI (default: 30)
- `rsi_max`: Maximum RSI (default: 70)
- `volume_multiplier`: Volume threshold (default: 1.5x)
- `require_trend`: Require price > SMA 50 (default: true)

### 3. `rsi_extremes`
RSI reversal signals.

**Params:**
- `oversold`: Oversold threshold (default: 30)
- `overbought`: Overbought threshold (default: 70)

---

## Tips

**Quality vs Quantity:**
- Strict filters = fewer trades, higher win rate
- Loose filters = more trades, lower win rate

**Parameter Optimization:**
- Test multiple variations
- Use `compare_strategies.py` to find winners
- Watch for overfitting on small datasets

**Best Practices:**
1. Start with relaxed filters on new data
2. Gradually tighten based on results
3. Always test on multiple stocks (50+)
4. Compare against simple baseline

---

## Code Maintainability

This service follows best practices for maintainability:

**Configuration Constants** (`src/constants.py`):
- All magic numbers centralized
- Easy to modify defaults
- Type-safe with helper functions

**Logging**:
- Structured logging throughout
- No print statements in production code
- Proper error levels (INFO/DEBUG/ERROR)

**Clean Architecture**:
- Dead code removed (obsolete save methods)
- Type hints on all functions
- Strategy category mapping centralized

**Database Schema**:
- Single comprehensive schema file
- 4-table design for analytics
- 54 metrics auto-calculated

When contributing:
1. Add new constants to `src/constants.py`
2. Use `logger` instead of `print()`
3. Add type hints to functions
4. Test with `--save` to verify database integration

