# Alert Service

Handles signal notifications and Discord bot functionality.

## Responsibilities
- Receive signals from scanner-service
- Generate chart images for alerts
- Send Discord notifications
- Provide slash commands for backtesting

## API Endpoints
- `POST /signal` - Receive trading signal
- `GET /health` - Health check

## Discord Commands
- `/backtest` - Interactive backtest form
- `/quick {symbol}` - Quick 1Y backtest
- `/strategy` - Custom strategy builder

## Configuration
| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | PostgreSQL connection string |
| `DISCORD_TOKEN` | Discord bot token |
| `DISCORD_CHANNEL_ALERTS` | Alert channel ID |
| `DISCORD_CHANNEL_BACKTEST` | Backtest channel ID |

## Scripts
- `test_discord_alert.py` - Test alert sending
- `populate_registry.py` - Populate signal registry
