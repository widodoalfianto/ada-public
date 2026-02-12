# Indicator Service

Calculates technical indicators from price data.

## Responsibilities
- Calculate EMA, SMA, RSI, MACD, Bollinger Bands
- Calculate and persist daily indicator snapshots for active stocks
- Serve indicator views for downstream services

## API Endpoints
- `POST /api/daily-calculate` - Incremental daily indicator calculation (latest date only)
- `GET /indicators/{symbol}` - On-demand indicator response for a symbol (`days` query param supported)

## Configuration
| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | PostgreSQL connection string |

## Core Modules
- `src/main.py` - FastAPI routes and service entrypoints
- `src/daily_calculate.py` - Daily incremental indicator calculation workflow
- `src/indicators.py` - Indicator math library used by API and daily jobs

## Tests
- `tests/test_indicators.py` - Unit tests for indicator calculations
- `tests/test_api_integration.py` - Endpoint smoke/integration tests (skips if service is unreachable)
