# Ada Project Makefile

DEV_COMPOSE ?= docker compose -p ada-dev --env-file .env.dev -f docker-compose.dev-full.yml
PROD_COMPOSE ?= docker compose --env-file .env -f docker-compose.yml

.PHONY: dev prod down logs db-shell clean help test test-unit test-suites test-smoke test-integration test-simulate test-e2e test-full

help: ## Show this help message
	@echo 'Usage: make [target]'
	@echo ''
	@echo 'Targets:'
	@echo '  dev        Start full development environment'
	@echo '  prod       Start production environment'
	@echo '  down       Stop all services'
	@echo '  logs       Tail logs for all services (or S=service_name for specific)'
	@echo '  db-shell   Access the database shell (Dev by default, env=prod for Prod)'
	@echo '  clean      Remove all volumes and data (Warning: Destructive!)'
	@echo '  test       Run unit tests (alias: test-unit)'
	@echo '  test-suites Deprecated (no standalone suite scripts in active services)'
	@echo '  test-smoke   Run pipeline smoke suite (pytest)'
	@echo '  test-simulate Run simulated daily flow smoke (requires SIM_DATE)'
	@echo '  test-e2e   Alias for test-simulate'
	@echo '  test-full  Run unit + smoke + simulate'
	@echo ''

dev: ## Start Development Environment
	@echo "Starting Development Environment..."
	@./dev.bat

prod: ## Start Production Environment
	@echo "Starting Production Environment..."
	@$(PROD_COMPOSE) up -d

down: ## Stop all services
	@echo "Stopping all services..."
	@$(DEV_COMPOSE) down
	@$(PROD_COMPOSE) down

logs: ## Tail logs. Usage: make logs [S=service_name]
ifdef S
	@$(DEV_COMPOSE) logs -f $(S)
else
	@$(DEV_COMPOSE) logs -f
endif

db-shell: ## Access DB Shell. Usage: make db-shell [env=prod]
ifeq ($(env),prod)
	@$(PROD_COMPOSE) exec db psql -U user -d stock_db
else
	@$(DEV_COMPOSE) exec db psql -U user -d stock_dev_db
endif

test: test-unit ## Run unit tests

test-unit: ## Run unit tests across services
	@echo "Running tests..."
	@echo "-----------------------------------"
	@echo "Testing Shared Libs (via Data Service)..."
	@$(DEV_COMPOSE) exec -T data-service pytest /libs/shared/tests
	@echo "-----------------------------------"
	@echo "Testing Data Service..."
	@$(DEV_COMPOSE) exec -T data-service pytest /app/tests
	@echo "-----------------------------------"
	@echo "Testing Indicator Service..."
	@$(DEV_COMPOSE) exec -T indicator-service pytest /app/tests
	@echo "-----------------------------------"
	@echo "Testing Scanner Service..."
	@$(DEV_COMPOSE) exec -T scanner-service pytest /app/tests
	@echo "-----------------------------------"
	@echo "Testing Alert Service..."
	@$(DEV_COMPOSE) exec -T alert-service pytest /app/tests
	@echo "-----------------------------------"
	@echo "Testing Scheduler Service..."
	@$(DEV_COMPOSE) exec -T scheduler-service pytest /app/tests

test-suites: ## Run service test suites
	@echo "No standalone service suite scripts configured in active services."

test-smoke: ## Run pipeline smoke suite
	@echo "Running pipeline smoke tests..."
	@$(DEV_COMPOSE) exec -T scanner-service pytest /ada/tests/pipeline_smoke_test.py -v

test-integration: test-smoke ## Alias for test-smoke

test-simulate: ## Run simulated daily flow smoke (requires SIM_DATE=YYYY-MM-DD)
ifndef SIM_DATE
	@echo "SIM_DATE is required. Example: make test-simulate SIM_DATE=2026-02-06"
	@exit 1
endif
	@echo "Running simulated daily flow for $(SIM_DATE)..."
	@$(DEV_COMPOSE) exec -T scanner-service /bin/sh -c "RUN_SIMULATION=1 SIMULATION_DATE=$(SIM_DATE) python /ada/tests/pipeline_smoke_test.py"

test-e2e: test-simulate ## Alias for test-simulate

test-full: test-unit test-smoke test-simulate ## Full test run
