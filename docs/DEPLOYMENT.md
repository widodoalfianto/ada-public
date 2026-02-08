# Production Deployment Guide

This guide outlines the steps to deploy the Ada system to a production environment.

## Prerequisites
- Docker Engine & Docker Compose (v2.10+)
- `git`
- Access to the target server
- Valid `.env` file (See `.env.example`)

## 1. Prepare Environment
Ensure the repository is up to date and the configuration is correct.

```bash
git pull origin main
cp .env.example .env
# Edit .env and ensure TEST_MODE=False
nano .env
```

## 2. Pre-Deployment Check
Run the safety check script to verify the specific environment configuration.

```bash
# Verify PRODUCTION configuration
./scripts/pre_deploy_check.sh prod
```
*If this script fails, DO NOT PROCEED.*

## 3. Build & Deploy
Build the production images (immutable tags) and start the stack.

```bash
# Build images (tagged ada/service:prod)
docker compose build

# Start services in detached mode
docker compose up -d
```

## 4. Verification
1.  Check running containers:
    ```bash
    docker ps
    ```
2.  Check logs for errors:
    ```bash
    docker logs ada-data-service-1
    ```
3.  Verify **NO** "TEST MODE" banner is present in logs.

## 5. Rollback
If issues arise, rollback to the previous state.

```bash
# Stop current deployment
docker compose down

# If you have previous images or tags, revert to them
# (Assuming tag versioning strategy is implemented in future)
```

## Troubleshooting
*   **Database Connection Failed**: check `stock_db` existence and credentials in `.env`.
*   **Safety Check Failed**: Ensure `TEST_MODE=False` in `.env`.
