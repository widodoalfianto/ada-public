# Scanner Service

Scans market data to detect trading signals.

## Responsibilities
- Evaluate stocks against signal conditions
- Detect crossovers, RSI extremes, volume spikes
- Send signals to alert-service

## API Endpoints
- `POST /run-scan` - Trigger market scan

## Configuration
| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | PostgreSQL connection string |
| `ALERT_SERVICE_URL` | Alert service endpoint |

## Scripts
- `scan.py` - Manual scan with optional date replay
