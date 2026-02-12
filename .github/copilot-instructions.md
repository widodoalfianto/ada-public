# Ada: AI Agent Instructions

**Ada** is a microservices-based stock scanner & alert system that processes S&P 500 data, calculates technical indicators, and delivers rich Discord alerts based on chart patterns and technical analysis.

## 🏗️ Architecture Overview

### Service Topology (4 Active Microservices)

| Service | Role | Tech | Key Files |
|---------|------|------|-----------|
| **Data Service** | Manages S&P 500 watchlist, fetches/backfills OHLCV data from yfinance | FastAPI + AsyncPG | `services/data-service/src/main.py`, `daily_update.py` |
| **Indicator Service** | Calculates technical indicators (SMA, RSI, MACD, Volume) on-demand | FastAPI + Pandas/NumPy | `services/indicator-service/src/indicators.py`, `daily_calculate.py` |
| **Scanner Service** | Orchestrates scans, evaluates complex conditions (crossovers, reversions) | FastAPI + Background Tasks | `services/scanner-service/src/worker.py`, `crossover_worker.py` |
| **Alert Service** | Formats and sends alerts to Discord via webhooks/bot | FastAPI + Discord.py | `services/alert-service/src/bot.py`, signal registry system |

### Data Flow

```
Data Service → (OHLCV stored in TimescaleDB, yfinance)
    ↓
Indicator Service → (Calculates indicators, stored in DB)
    ↓
Scanner Service → (Evaluates conditions, emits signals)
    ↓
Alert Service → (Formats via SignalRegistry, sends Discord)
```

**Current scan scope**:
- Only EMA9/SMA20 golden/death crossovers.
- Universe limited to top 100 S&P 500 stocks by average dollar volume (Avg Volume × Avg Price).

### Infrastructure

- **Database**: TimescaleDB (PostgreSQL 15) with time-series optimization
- **Message Queue**: Redis (async task distribution)
- **Environment Isolation**: Strict Dev/Prod separation via `TEST_MODE` flag and database names (`stock_dev_db` vs `stock_db`)
- **Container Orchestration**: Docker Compose

## 🔑 Critical Patterns & Conventions

### 1. Environment Separation (Non-Negotiable)

**Rule**: Dev and Prod run in completely isolated environments.

- **Dev Mode**: `TEST_MODE=True` → `stock_dev_db`, DEBUG logging, safety banners on Discord
- **Prod Mode**: `TEST_MODE=False` → `stock_db`, INFO logging, live signals

**Enforcement** (`services/shared/config.py`):
```python
# Services validate on startup:
# - Dev mode MUST use *_dev_db database
# - Prod mode CANNOT use *_dev_db
# - Mismatches raise SystemExit
```

**When adding features**: Always check `TEST_MODE` in `BaseConfig.validate_environment()` if it affects data safety.

### 2. Shared Library Pattern

All services import from `services/shared/`:

```python
from shared.models import Stock, PriceData, Indicator
from shared.exceptions import AdaException, DatabaseError, ValidationError
from shared.transactions import transaction_scope, batch_transaction
from shared.idempotency import check_duplicate, IdempotencyChecker
```

**Shared exports** (`services/shared/__init__.py`):
- **Models**: `Stock` (watchlist), `PriceData` (OHLCV), `Indicator` (computed values)
- **Exceptions**: Typed errors with codes (e.g., `ValidationError`, `RateLimitError`)
- **Transactions**: Context managers for safe commit/rollback with automatic cleanup
- **Idempotency**: Deduplication for re-entrant operations

### 3. Transaction Management Pattern

All database writes use `transaction_scope()` context manager:

```python
async with transaction_scope(session, "create_stock") as txn:
    session.add(Stock(symbol="AAPL"))
    # Auto-commits on success, auto-rolls back on exception
```

For bulk operations, use `batch_transaction()` to avoid memory buildup:

```python
async with batch_transaction(session, batch_size=100) as batch:
    for stock in stocks:
        session.add(stock)
        await batch.increment()  # Auto-commits every 100
```

### 4. Model Relationships

**Core Schema** (`services/shared/models.py`):
- `Stock`: `id`, `symbol`, `sector`, `avg_volume_30d`, `is_active` (indexed for filtering)
- `PriceData`: `(stock_id, date)` composite primary key (TimescaleDB partitioning)
- `Indicator`: `(stock_id, date, indicator_name)` composite key

**Design principle**: Relationships use SQLAlchemy backrefs; service-specific relations (e.g., `AlertHistory`) injected via backref in their services.

### 5. Signal Registry (Alert Routing)

Alerts are **template-driven**, not hardcoded. The `SignalRegistry` table stores:

- `signal_code`: Unique identifier (e.g., `"MA_GOLDEN_CROSS"`)
- `template_text`: Discord message format with placeholders like `{data[price]}`, `{symbol}`
- `enabled`: Boolean to toggle signals without code changes

**Pattern** (`alert-service/src/main.py`):
```python
# Incoming signal from Scanner
signal = RawSignal(signal_code="MA_GOLDEN_CROSS", symbol="AAPL", data={...})

# Lookup definition in registry
definition = session.query(SignalRegistry).filter_by(signal_code=...).first()

# Format using safe template substitution
message = definition.template_text.format_map(SafeDict({'data': signal.data, ...}))
```

### 6. API Endpoint Patterns

All services follow FastAPI conventions:

- **GET** `/`: Health check
- **GET** `/indicators/{symbol}?days=1`: Fetch computed indicators
- **POST** `/api/daily-update`: Trigger daily data refresh (idempotent, called post-market close)
- **POST** `/api/daily-calculate`: Trigger indicator recalculation (incremental, not historical)
- **POST** `/run-scan`: Trigger market scan in background task

**Key pattern**: Heavy operations use `BackgroundTasks` to avoid timeout.

### 7. Logging & Error Handling

**Standard across all services**:

```python
import logging
logging.basicConfig(level=os.getenv('LOG_LEVEL', 'INFO'), ...)
logger = logging.getLogger(__name__)

# Use logger, not print()
logger.info(f"Processing {symbol}")
logger.error(f"Failed to fetch data", exc_info=True)
```

**Exception hierarchy** (all inherit from `AdaException`):
- `DatabaseError`: Database operation failed
- `ValidationError`: Input validation failed
- `ExternalServiceError`: API/yfinance call failed
- `RateLimitError`: Rate limit exceeded

Use `safe_execute()` wrapper for external API calls:

```python
from shared.exceptions import safe_execute

data = await safe_execute(
    lambda: fetch_from_yfinance(symbol),
    context="fetch_market_data",
    fallback=None
)
```

## 🚀 Developer Workflows

### Local Development

```bash
# Windows:
./dev.bat                      # Start full dev environment (TEST_MODE=True, isolated DB)
make logs S=data-service       # Tail specific service logs
make db-shell                  # Access dev DB (stock_dev_db)
make test                      # Run unit tests

# Production:
make prod                      # Start prod environment (docker-compose.yml)
make db-shell env=prod         # Access prod DB (stock_db)
```

### Testing

Preferred (cross-platform) runner:
```bash
python scripts/run_tests.py --mode quick
python scripts/run_tests.py --mode full
python scripts/run_tests.py --mode simulate --simulation-date 2026-02-06
```

Makefile shortcuts:
```bash
make test-unit
make test-smoke
make test-simulate SIM_DATE=2026-02-06
```

`make test-suites` is currently a no-op (standalone suite scripts are deprecated).

**Unit tests** in `tests/` use pytest:

```bash
docker compose exec data-service pytest tests/
```

### Database Access

TimescaleDB queries:

```sql
-- Check data age
SELECT symbol, MAX(date) FROM price_data JOIN stocks ON price_data.stock_id = stocks.id 
  GROUP BY symbol ORDER BY MAX(date) DESC LIMIT 10;

-- Find active S&P 500 stocks
SELECT symbol, name FROM stocks WHERE is_active=TRUE ORDER BY avg_volume_30d DESC LIMIT 100;
```

## 📋 Common Tasks & Patterns

### Adding a New Technical Indicator

1. **Calculate in Indicator Service** (`services/indicator-service/src/indicators.py`):
   ```python
   def calculate_stoch(df):
       # Return pd.Series with indicator values
       return (df['close'] - df['low'].rolling(14).min()) / \
              (df['high'].rolling(14).max() - df['low'].rolling(14).min())
   ```

2. **Register in daily calculation** (`daily_calculate.py`):
   ```python
   indicators_map = calculate_all_indicators(df)  # Auto-includes new indicator
   ```

3. **Create Scanner condition** (`scanner-service/src/worker.py`):
   ```python
   if indicators['stoch'] > 80:  # Overbought
       emit_signal("STOCH_OVERBOUGHT", symbol, data=...)
   ```

4. **Add Signal Registry entry** (via admin API or direct DB insert):
   ```python
   SignalRegistry(
       signal_code="STOCH_OVERBOUGHT",
       template_text="Stochastic overbought on {symbol}: {data[value]}",
       enabled=True
   )
   ```

### Running a Manual Scan

```bash
# Single stock:
docker compose exec scanner-service python scripts/manual_scan.py TSLA

# Top 100 stocks by volume:
docker compose exec scanner-service python scripts/manual_scan.py --top-100
```

### Backfilling Historical Data

```bash
# Fetch N years of history for all active stocks:
docker compose exec data-service python scripts/backfill_history.py --years=5
```

## ⚠️ Anti-Patterns to Avoid

| Anti-Pattern | Why | Correct Approach |
|--------------|-----|------------------|
| Hardcoding Discord messages in Scanner | Alert logic shouldn't couple to formatting | Use SignalRegistry templates |
| Using `sync` SQLAlchemy in async code | Deadlocks and performance issues | Always use `AsyncSessionLocal()`, `await` queries |
| Skipping `transaction_scope()` context manager | Data inconsistency, orphaned rows | Wrap all DB writes with context manager |
| Ignoring `TEST_MODE` in logic | Prod data corruption during dev testing | Check `settings.TEST_MODE` for safety-critical code |
| Adding service-specific models to `shared/` | Violates single-responsibility, breaks encapsulation | Keep shared, keep only cross-service models |
| Calling external APIs without timeouts | Service hangs blocking other operations | Use `safe_execute()` with explicit timeout |

## 📚 Key Files Reference

| File | Purpose |
|------|---------|
| [services/shared/models.py](services/shared/models.py) | Core data models (Stock, PriceData, Indicator) |
| [services/shared/exceptions.py](services/shared/exceptions.py) | Exception hierarchy and error handling utilities |
| [services/shared/transactions.py](services/shared/transactions.py) | Transaction context managers and batch operations |
| [services/shared/config.py](services/shared/config.py) | Environment validation (TEST_MODE, DB separation) |
| [services/scanner-service/src/worker.py](services/scanner-service/src/worker.py) | Core scanning logic (condition evaluation) |
| [services/alert-service/src/main.py](services/alert-service/src/main.py) | Signal receipt and template-based formatting |
| [docker-compose.yml](docker-compose.yml) | Production setup (stock_db, service URLs) |
| [docker-compose.dev-full.yml](docker-compose.dev-full.yml) | Development setup (stock_dev_db, DEBUG logging) |

## 🔍 Before Starting Work

- [ ] Confirm `TEST_MODE` behavior if touching safety-critical code
- [ ] Check if feature already exists in shared library (avoid duplication)
- [ ] Review transaction patterns in related services (consistency)
- [ ] Verify database schema changes don't break existing migrations
- [ ] Test in Dev environment first (`./dev.bat`) before production changes
- [ ] Check signal registry for alert customization (don't hardcode messages)
