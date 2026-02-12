# Ada Testing Guide

## Dev Compose Prefix
Use:
```bash
docker compose -p ada-dev --env-file .env.dev -f docker-compose.dev-full.yml <command>
```

## Current Test Layers
1. Unit tests per active service (`data`, `indicator`, `scanner`, `alert`, `scheduler`) plus shared libs.
2. Pipeline smoke (`tests/pipeline_smoke_test.py`).
3. Simulated daily flow (same smoke suite in manual simulation mode).
4. Optional live data-service integration probes (opt-in).

## One-Command Runner
```bash
python scripts/run_tests.py --mode quick
python scripts/run_tests.py --mode smoke
python scripts/run_tests.py --mode simulate --simulation-date 2026-02-10
python scripts/run_tests.py --mode full
```

Legacy aliases still work:
- `--mode integration` (alias of `smoke`)
- `--mode e2e` (alias of `simulate`)

## Makefile Shortcuts
```bash
make test-unit
make test-smoke
make test-simulate SIM_DATE=2026-02-10
make test-full SIM_DATE=2026-02-10
```

Legacy aliases still work:
- `make test-integration` (alias of `test-smoke`)
- `make test-e2e` (alias of `test-simulate`)

`make test-suites` is currently a no-op because standalone `scripts/test_suite.py` files were removed from active services.

## Manual Smoke Invocation
```bash
docker compose -p ada-dev --env-file .env.dev -f docker-compose.dev-full.yml exec -T scanner-service pytest /ada/tests/pipeline_smoke_test.py -v
```

## Simulated Daily Flow (Manual)
```bash
docker compose -p ada-dev --env-file .env.dev -f docker-compose.dev-full.yml exec -T scanner-service /bin/sh -c "RUN_SIMULATION=1 SIMULATION_DATE=2026-02-10 python /ada/tests/pipeline_smoke_test.py"
```

## Data-Service Live Integration (Opt-In)
The live integration tests mutate and repair real dev DB rows.

```bash
docker compose -p ada-dev --env-file .env.dev -f docker-compose.dev-full.yml exec -T data-service /bin/sh -c "RUN_LIVE_DATA_SERVICE_INTEGRATION=1 pytest /app/tests/test_api_integration.py -v"
```

These tests are skipped by default in normal unit runs.
