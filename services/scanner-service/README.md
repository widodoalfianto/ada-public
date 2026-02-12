# Scanner Service

Scans market data to detect trading signals.

## Responsibilities
- Load strategy definitions from JSON files
- Evaluate top-liquidity stocks against enabled strategy rules
- Emit strategy-scoped Entry/Exit signals (currently `ESM`, `PF`)

## API Endpoints
- `POST /run-scan` - Trigger all enabled strategy scans (`target_date`, `send_notifications` optional)
- `POST /run-esm-scan` - Trigger ESM scan
- `POST /run-pf-scan` - Trigger PF scan
- `POST /run-strategy-scan/{strategy_code}` - Trigger one strategy scan (`target_date`, `send_notifications` optional)

## Configuration
| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | PostgreSQL connection string |
| `ALERT_SERVICE_URL` | Alert service endpoint |

## Scripts
- `scan.py` - Manual trigger for all strategies or one strategy (`ESM`/`PF`) with optional `--date` and `--no-notify`
