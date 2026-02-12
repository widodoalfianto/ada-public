# Alert Service

Handles signal notifications and Discord bot functionality.

## Responsibilities
- Receive signals from scanner-service
- Generate chart images for alerts
- Send Discord notifications
- Provide Discord commands for alert review and charts

## API Endpoints
- `POST /signal` - Receive trading signal
- `POST /send-morning-summary` - Trigger morning summary broadcast
- `POST /system-alert` - Send operational/system alert to developer system channel

## Discord Commands
- `/alerts` - Show alert history (today/yesterday)
- `/chart {symbol}` - Render EMA9/SMA20 chart for a symbol

## Configuration
| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | PostgreSQL connection string |
| `DISCORD_BOT_TOKEN` | Discord bot token |
| `DISCORD_CHANNEL_ESM` | ESM alert channel ID |
| `DISCORD_CHANNEL_PF` | PF alert channel ID |
| `DISCORD_CHANNEL_FALLBACK` | Fallback channel ID |
| `DISCORD_CHANNEL_SYSTEM` | System/error channel ID |

## Scripts
- `populate_registry.py` - Populate signal registry
