# New Developer Onboarding Guide

Welcome to the Ada project! This guide will help you get your development environment set up in less than 15 minutes.

## 1. Prerequisites
- **Git**
- **Docker Desktop** (Make sure it's running)
- **Make** (Optional, but recommended. Included in Git Bash or WSL)
- **Visual Studio Code** (Recommended)

## 2. Initial Setup
1.  **Clone the repository**:
    ```bash
    git clone <repository_url>
    cd ada
    ```
2.  **Configure Environment**:
    copy `.env.example` to `.env` and `.env.dev`.
    ```bash
    cp .env.example .env
    cp .env.example .env.dev
    ```
    *Note: Ask the team lead for the shared Dev Discord Token.*

## 3. Running the Environment
We use a `Makefile` to simplify common commands (optional on Windows). For cross-platform workflows, see the Python test runner in Section 4.

### Start Development Environment
```bash
make dev
```
This will:
- Build all development images.
- Start the full stack (Data, Indicator, Scanner, Alert, Backtest services).
- Initialize the `stock_dev_db` database.
- Start Redis.

**Verify it works**:
- Open http://localhost:9001/docs (Data Service Swagger UI).
- Check logs: `make logs`

### Common Commands
| Command | Description |
| :--- | :--- |
| `make dev` | Start the full development stack (Hot-reload enabled). |
| `make down` | Stop all containers. |
| `make logs` | Tail logs for all services. |
| `make logs S=data-service` | Tail logs for a specific service. |
| `make test` | Run unit tests (Requires services to be running). |
| `make db-shell` | Connect to the development database (`psql`). |
| `make clean` | WIPE ALL DATA and start fresh (Destructive). |

## 4. Testing (Recommended)
Use the cross-platform Python test runner to keep developer experience consistent across OSes.

```bash
python scripts/run_tests.py --mode quick
python scripts/run_tests.py --mode full
python scripts/run_tests.py --mode e2e --simulation-date 2026-02-06
```

Makefile equivalents:
```bash
make test-unit
make test-suites
make test-integration
make test-e2e SIM_DATE=2026-02-06
```

**Notes**
- `full` includes an end-to-end simulation that may send a Discord summary to the test channel.
- If you want to skip backtest tests: `python scripts/run_tests.py --mode full --skip-backtest`

## 5. Development Workflow
1.  Create a feature branch.
2.  Make code changes in `services/<service>/src`.
3.  The services will auto-reload (thanks to volume mounts).
4.  Run tests: `docker compose -f docker-compose.dev-full.yml exec <service> pytest`

## 6. Troubleshooting
- **Ports already in use**: Check if another instance is running (`docker ps`) or if system services are using ports 9001-9005.
- **Database connection failed**: Ensure `make dev` completed successfully and the specific `healthcheck` passed.
