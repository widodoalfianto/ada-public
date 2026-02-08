# Ada Testing Guide

## Dev Mode Prefix
If you started the stack via `dev.bat`, prefix commands with:
```bash
docker compose -p ada-dev --env-file .env.dev -f docker-compose.dev-full.yml <command>
```

## Testing Paradigm (Recommended)
1. Preflight: containers up, DB reachable, and services healthy.
2. Unit Tests: pytest per service + shared libs.
3. Service Suites: `scripts/test_suite.py` for data, indicator, backtest.
4. Integration: `tests/integration_test_suite.py` (health + pipeline + idempotency).
5. End-to-End Simulation: run the full loop for a specific trading day.

## One-Command Runner (Windows)
Use the PowerShell runner for consistent, repeatable execution:
```powershell
.\scripts\run_tests.ps1 -Mode quick
.\scripts\run_tests.ps1 -Mode full
.\scripts\run_tests.ps1 -Mode e2e -SimulationDate 2026-02-06
.\scripts\run_tests.ps1 -Mode full -SkipBacktest
```

## One-Command Runner (Cross-Platform)
Use the Python runner on Windows/macOS/Linux:
```bash
python scripts/run_tests.py --mode quick
python scripts/run_tests.py --mode full
python scripts/run_tests.py --mode e2e --simulation-date 2026-02-06
python scripts/run_tests.py --mode full --skip-backtest
```

## One-Command Runner (Makefile)
```bash
make test-unit
make test-suites
make test-integration
make test-e2e SIM_DATE=2026-02-06
make test-full SIM_DATE=2026-02-06
```

## Test Suites Overview

### 1. Data Service Tests
**Location:** `services/data-service/scripts/test_suite.py`

**Tests:**
- Health check endpoint
- Daily price update functionality
- Database statistics

**Run:**
```bash
docker compose exec data-service python scripts/test_suite.py
```

---

### 2. Indicator Service Tests
**Location:** `services/indicator-service/scripts/test_suite.py`

**Tests:**
- Health check endpoint
- Get indicators for specific stock
- Daily indicator calculation (incremental)
- Indicator coverage across multiple stocks

**Run:**
```bash
docker compose exec indicator-service python scripts/test_suite.py
```

---

### 3. Backtest Service Tests
**Location:** `services/backtest-service/scripts/test_suite.py`

**Tests:**
- Single stock backtest
- Multi-stock backtest
- Save functionality (comprehensive schema)
- Strategy comparison
- Metrics calculation (54 metrics)

**Run:**
```bash
docker compose exec backtest-service python scripts/test_suite.py
```

---

### 4. Integration Tests
**Location:** `tests/integration_test_suite.py`

**Tests:**
- Service health checks (all services)
- Data freshness validation
- Full daily pipeline (end-to-end)

**Run:**
```bash
docker compose exec backtest-service python /ada/tests/integration_test_suite.py
```

---

## Quick Test Commands

### Test Individual Services
```bash
# Data Service
docker compose exec data-service python scripts/test_suite.py

# Indicator Service
docker compose exec indicator-service python scripts/test_suite.py

# Backtest Service
docker compose exec backtest-service python scripts/test_suite.py
```

### Test Daily Pipeline (Manual Trigger)
```bash
# Step 1: Fetch prices
docker compose exec data-service python -c "
import asyncio
import httpx
async def test():
    async with httpx.AsyncClient(timeout=600) as client:
        r = await client.post('http://data-service:8000/api/daily-update')
        print(r.json())
asyncio.run(test())
"

# Step 2: Calculate indicators
docker compose exec indicator-service python -c "
import asyncio
import httpx
async def test():
    async with httpx.AsyncClient(timeout=300) as client:
        r = await client.post('http://indicator-service:8000/api/daily-calculate')
        print(r.json())
asyncio.run(test())
"
```

### Run All Tests
```bash
# Run all service tests sequentially
docker compose exec data-service python scripts/test_suite.py && \
docker compose exec indicator-service python scripts/test_suite.py && \
docker compose exec backtest-service python scripts/test_suite.py
```

---

## Database Validation Queries

### Check Data Coverage
```bash
# Price data coverage
docker compose exec db psql -U user -d stock_db -c "
SELECT COUNT(DISTINCT stock_id) as stocks_with_prices,
       MIN(date) as earliest_date,
       MAX(date) as latest_date
FROM price_data;
"

# Indicator coverage
docker compose exec db psql -U user -d stock_db -c "
SELECT COUNT(DISTINCT stock_id) as stocks_with_indicators,
       COUNT(*) as total_indicators,
       MAX(date) as latest_date
FROM indicators;
"

# Backtest results
docker compose exec db psql -U user -d stock_db -c "
SELECT COUNT(*) as total_backtests,
       COUNT(DISTINCT name) as unique_strategies
FROM backtests;
"
```

### Verify Today's Data
```bash
docker compose exec db psql -U user -d stock_db -c "
SELECT 
    (SELECT COUNT(DISTINCT stock_id) FROM price_data WHERE date = CURRENT_DATE) as prices_today,
    (SELECT COUNT(DISTINCT stock_id) FROM indicators WHERE date = CURRENT_DATE) as indicators_today;
"
```

---

## Expected Results

### Data Service
- ✅ 502 stocks with price data
- ✅ < 10% failure rate on daily update
- ✅ Completes in < 10 minutes

### Indicator Service
- ✅ 17 indicators per stock per day
- ✅ ~8,534 new indicators daily (502 stocks × 17)
- ✅ Completes in < 5 minutes
- ✅ Skips already-calculated indicators

### Backtest Service
- ✅ Successfully runs all 3 strategies
- ✅ Saves to 4-table schema
- ✅ Calculates 54 performance metrics
- ✅ Handles multi-stock portfolios

### Integration
- ✅ All services respond to health checks
- ✅ Full pipeline completes successfully
- ✅ Data is current (within 1 trading day)

---

## Troubleshooting

### Test Timeouts
**Symptom:** Tests timeout after 60-120 seconds  
**Cause:** 502 stocks with API rate limiting takes time  
**Solution:** This is expected. Check service logs:
```bash
docker compose logs data-service | tail -50
docker compose logs indicator-service | tail -50
```

### Missing Indicators
**Symptom:** No indicators for specific stocks  
**Cause:** No price data available  
**Solution:** Run daily price fetch first

### Backtest Failures
**Symptom:** "No data loaded" error  
**Cause:** Missing indicators for date range  
**Solution:** Ensure indicators calculated for test period

---

## Continuous Testing

### Schedule Tests (Weekly)
Add to scheduler-service for weekly validation:
```python
@scheduler.scheduled_job('cron', day_of_week='sun', hour=2)
async def weekly_validation():
    # Run integration test suite
    # Alert on failures
```

### Monitor Test Results
- Set up alerts for test failures
- Track success rates over time
- Log all test runs for debugging

---

## Next Steps

1. **Automate Testing:** Add CI/CD pipeline with GitHub Actions
2. **Performance Testing:** Load test with 1000+ stocks
3. **Error Injection:** Test failure scenarios and recovery
4. **Monitoring:** Set up Grafana dashboard for test metrics
