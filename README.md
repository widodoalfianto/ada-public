# Ada: Advanced Stock Scanner & Alert System 🦅

Ada is a powerful, microservices-based platform designed to scan the **S&P 500** for high-probability technical setups. It processes market data, calculates indicators, and delivers rich, actionable alerts directly to Discord.

## 🚀 Key Features

- **Liquidity-Weighted Focus**: Scans the **top 100** S&P 500 stocks by average dollar volume (Avg Volume × Avg Price).
- **Advanced Technical Analysis**:
  - **Moving Averages**: EMA 9 / SMA 20.
  - **Crossovers**: Golden Cross (Bullish) & Death Cross (Bearish).
- **Rich Alerts**:
  - **Semantic Meaning**: Explains *why* the alert was triggered.
  - **Actionable Advice**: Suggests potential moves (e.g., "🐂 Bullish - Potential Entry").
  - **Categorized Routing**: Alerts can be routed to Discord channels (MA, system, fallback).
- **Architecture**:
  - **Dockerized**: Fully containerized for easy deployment.
  - **TimescaleDB**: High-performance time-series data handling.
  - **Redis**: Fast message queuing between services.

## 🏗️ Architecture

The system consists of 4 decoupled microservices:

1.  **Data Service**:
    - Manages the S&P 500 watchlist (scraped from Wikipedia).
    - Fetches daily OHLCV data from yfinance.
    - Historical backfill & daily updates.
2.  **Indicator Service**:
    - Calculates technical indicators on-demand.
    - Optimized with Pandas/NumPy for speed.
3.  **Scanner Service**:
    - The "Brain". Orchestrates scans.
    - Evaluates complex conditions (e.g., "SMA 50 crossed SMA 200 today").
4.  **Alert Service**:
    - Formats and delivers alerts to Discord.
    - Routing logic based on alert category.

## 📚 Documentation

Detailed documentation for developers and operators:
- **[Environment Guide](docs/ENVIRONMENTS.md)**: Deep dive into Development vs. Production isolation, ports, and safety mechanisms.
- **[Deployment Guide](docs/DEPLOYMENT.md)**: Step-by-step instructions for production deployment.
- **[Onboarding Guide](docs/ONBOARDING.md)**: New developer setup and workflows.
- **[Testing Guide](TESTING.md)**: End-to-end testing paradigm and runners.
- **[Audit Reports](docs/audit/)**: System analysis and refactoring history.

## 🌍 Environment Architecture

The system runs in two strictly isolated environments. See [ENVIRONMENTS.md](docs/ENVIRONMENTS.md) for full details.

### Production
- **Purpose**: Live trading and alerts.
- **Database**: `stock_db` (Internal).
- **Command**: `docker compose up -d`

### Development
- **Purpose**: Testing and code changes.
- **Safety**: `TEST_MODE=True`, Safety Banners, Isolated DB (`stock_dev_db`).
- **Command**: `./dev.bat` (Windows)

## 🛠️ Setup & Installation

### Prerequisites
- Docker & Docker Compose
- A Discord Server (with Webhooks/Bot Token)

### Configuration
1.  Clone the repository.
2.  Create a `.env` file in the root directory:
    ```ini
    DISCORD_BOT_TOKEN=your_discord_bot_token
    
    # Discord Channel Configuration
    DISCORD_CHANNEL_ESM=123456789...    # ESM Signals
    DISCORD_CHANNEL_PF=123456789...     # PF Signals
    DISCORD_CHANNEL_FALLBACK=123456789... # Catch-all
    ```

### Running the System
```bash
# Build and Start configured services
docker compose up -d --build
```

The system will automatically:
1.  Initialize the database.
2.  Fetch the latest S&P 500 list.
3.  Begin scanning (Daily at Market Close).

## 🎮 Usage

### Manual Scan
To manually run scanner strategies (all enabled, or a specific strategy/date):
```bash
docker compose exec scanner-service python scripts/scan.py --strategy ESM --date 2026-02-10
```

### Resetting Data
To purge all data and restart fresh (e.g., to re-backfill):
```bash
docker compose exec data-service python scripts/reset_db.py
```

## 📝 License
MIT License.
