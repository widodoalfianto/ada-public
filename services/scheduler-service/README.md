# Scheduler Service

Orchestrates scheduled jobs for the trading system.

## Responsibilities
- Trigger daily price fetch (4:05 PM ET)
- Trigger indicator calculation (4:15 PM ET)
- Trigger evening strategy scans (ESM + PF)
- Trigger morning summary
- Trigger weekly cleanup
- Retry failed upstream job calls (5 retries, exponential backoff from 5m to 60m)
- Send critical observability alerts to alert-service system channel after retry exhaustion
- Handle trading day detection

## Jobs
| Job | Schedule | Description |
|-----|----------|-------------|
| `daily_update` | 4:05 PM ET | Fetch prices |
| `daily_calculate` | 4:15 PM ET | Calculate indicators |
| `evening_esm_scan` | 4:30 PM ET | Run ESM scan |
| `evening_pf_scan` | 4:35 PM ET | Run PF scan |
| `morning_summary` | 9:35 AM ET | Morning summary |
| `weekly_cleanup` | Sunday 2:00 AM ET | Prune old data |

## Configuration
| Variable | Description |
|----------|-------------|
| `DATA_SERVICE_URL` | Data service endpoint |
| `INDICATOR_SERVICE_URL` | Indicator service endpoint |
| `SCANNER_SERVICE_URL` | Scanner service endpoint |
| `ALERT_SERVICE_URL` | Alert service endpoint (morning summary + system observability alerts) |
