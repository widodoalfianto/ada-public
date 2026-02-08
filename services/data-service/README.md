# Data Service

Handles stock data fetching, storage, and maintenance.

## Responsibilities
- Fetch daily price data from Finnhub/yfinance
- Store price history in PostgreSQL
- Provide data cleanup and archival

## API Endpoints
- `POST /api/daily-update` - Trigger daily price fetch
- `POST /api/cleanup` - Trigger data cleanup
- `GET /api/stocks` - List all stocks

## Configuration
| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | PostgreSQL connection string |
| `FINNHUB_API_KEY` | Finnhub API key |
| `REDIS_URL` | Redis for rate limiting |

## Scripts
- `fetch_stock.py` - Manual stock fetch
- `cleanup_stocks.py` - Remove inactive stocks
- `backfill_history.py` - Backfill historical data
