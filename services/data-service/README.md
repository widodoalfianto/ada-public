# Data Service

Handles stock data fetching, storage, and maintenance.

## Responsibilities
- Fetch daily price data from yfinance
- Store price history in PostgreSQL
- Provide data cleanup and archival

## API Endpoints
- `POST /api/daily-update` - Trigger daily price fetch
- `POST /api/cleanup` - Trigger data cleanup
- `POST /api/record-alert` - Record alert history
- `GET /api/alert-history` - Fetch alert history by date

## Configuration
| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | PostgreSQL connection string |

## Scripts
- `backfill_history.py` - Manual historical backfill (optional)
- `update_watchlist.py` - Refresh S&P 500 watchlist membership
- `reset_db.py` - Destructive reset utility (guarded; requires `ENV in {dev,test,local}` or `ALLOW_DB_RESET=true`)
