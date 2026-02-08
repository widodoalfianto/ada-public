# Backtest Service - File Structure

## Active Files

### Core Source Files (`src/`)
- `main.py` - FastAPI application (REST API endpoints)
- `backtest_engine.py` - Main backtesting orchestration
- `backtest_runner.py` - Unified test runner for CLI scripts
- `signal_detector.py` - Signal detection (MA crossover, multi-indicator, RSI)
- `trade_simulator.py` - Trade simulation with P&L calculation
- `data_loader.py` - Database data loading utilities
- `database.py` - Database connection setup
- `config.py` - Application settings
- `models.py` - SQLAlchemy model for `backtest_runs` table

### CLI Scripts (`scripts/`)
- `test_single.py` - Test strategy on single stock
- `test_list.py` - Test strategy on list of stocks
- `test_all_sp500.py` - Test strategy on all S&P 500 stocks
- `compare_strategies.py` - Compare multiple strategies side-by-side
- `test_multi_indicator.py` - Legacy comparison script (can be removed)

### Schema (`migrations/`)
- `backtest_schema.sql` - Single definitive schema file

### Documentation (`docs/`)
- `schema_comparison.sql` - Schema design options (reference)
- `storage_strategy.md` - Backtest results storage approach

### Configuration
- `requirements.txt` - Python dependencies
- `Dockerfile` - Container build instructions
- `README.md` - Usage guide

## User-Specific (Gitignored)

### Strategy Definitions (`strategies/`)
User-created JSON strategy files:
- `simple_ma_crossover.json`
- `triple_confirmation.json`
- `moderate_filter.json`

### Results (`results/`)
JSON files with full backtest results:
- `YYYY-MM-DD_HHMMSS_strategy_name_sp500.json`

## Removed/Deprecated Files
- ❌ `src/models_simple.py` → renamed to `models.py`
- ❌ `scripts/test_backtest.py` → replaced by standardized scripts
- ❌ `scripts/test_sp500.py` → replaced by `test_all_sp500.py`
- ❌ `migrations/001_initial_backtest_tables.sql` → replaced by `backtest_schema.sql`
- ❌ `migrations/002_simplify_backtest_schema.sql` → replaced by `backtest_schema.sql`
