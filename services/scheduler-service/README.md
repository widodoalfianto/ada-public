# Scheduler Service

Orchestrates scheduled jobs for the trading system.

## Responsibilities
- Trigger daily price fetch (4:05 PM ET)
- Trigger indicator calculation (4:15 PM ET)
- Trigger market scans
- Handle trading day detection

## Jobs
| Job | Schedule | Description |
|-----|----------|-------------|
| `daily_update` | 4:05 PM ET | Fetch prices |
| `daily_calculate` | 4:15 PM ET | Calculate indicators |
| `run_scan` | 4:30 PM ET | Run market scan |
| `morning_summary` | 9:35 AM ET | Morning summary |

## Configuration
| Variable | Description |
|----------|-------------|
| `DATA_SERVICE_URL` | Data service endpoint |
| `INDICATOR_SERVICE_URL` | Indicator service endpoint |
| `SCANNER_SERVICE_URL` | Scanner service endpoint |
