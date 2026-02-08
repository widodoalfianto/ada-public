# Indicator Service

Calculates technical indicators from price data.

## Responsibilities
- Calculate EMA, SMA, RSI, MACD, Bollinger Bands
- Store indicator values in PostgreSQL
- Provide indicator data to other services

## API Endpoints
- `POST /api/daily-calculate` - Calculate indicators for today
- `GET /indicators/{symbol}` - Get indicators for a stock

## Configuration
| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | PostgreSQL connection string |

## Scripts
- `batch_calculate_indicators.py` - Batch calculation
- `verify_indicators.py` - Verify indicator accuracy
