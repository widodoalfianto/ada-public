# Environment Architecture

This document explains the separation between Development and Production environments in the Ada system.

## Overview

Ada uses a strict isolation strategy to ensure that development activities never impact the production trading environment.

| Feature | Development (Dev) | Production (Prod) |
| :--- | :--- | :--- |
| **Compose File** | `docker-compose.dev-full.yml` | `docker-compose.yml` |
| **Startup Script** | `dev.bat` (Windows) | `docker compose up -d` |
| **Database** | `stock_dev_db` (Port 5433) | `stock_db` (Internal 5432) |
| **Redis** | Port 6380 | Internal 6379 |
| **Service Ports** | 9001-9005 | 8001-8005 |
| **Safety Banner** | ⚠️ YES | ❌ NO |
| **Test Mode** | `True` | `False` |

## Safety Mechanisms

### 1. Database Isolation
*   **Dev**: Forces connection to `stock_dev_db`.
*   **Prod**: Forces connection to `stock_db`.
*   **Enforcement**: Services will **CRASH** if they detect a configuration mismatch (e.g., trying to use Prod DB in Dev mode).

### 2. Configuration Validation (`TEST_MODE`)
All services check the `TEST_MODE` environment variable on startup.
*   **True**: Loads Development/Test configuration (Dev Discord channels, safe execution paths).
*   **False**: Loads Production configuration (Real Trading, Main Discord channels).

### 3. Build Artifact Isolation
*   **Dev Images**: Tagged `ada/service:dev`
*   **Prod Images**: Tagged `ada/service:prod`
*   This prevents accidental deployment of development code to production.

## Running Environments

### Development
To start the full development environment with hot-reloading:
```bash
./dev.bat
```
*   Access Data Service: http://localhost:9001
*   Access DB: localhost:5433

### Production
To start the production environment (Detached, Immutable):
```bash
docker compose --env-file .env -f docker-compose.yml up -d
```
*   Access Data Service: http://localhost:8001

## Concurrent Execution
Both environments can run simultaneously on the same machine without conflict due to distinct port mappings and isolated storage volumes.
