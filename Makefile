.DEFAULT_GOAL := help
SHELL := /bin/bash

# Docker Compose command is auto-detected, but can be overridden:
#   make docker-up COMPOSE="docker-compose"
COMPOSE ?= $(shell if docker compose version >/dev/null 2>&1; then printf 'docker compose'; elif command -v docker-compose >/dev/null 2>&1; then printf 'docker-compose'; else printf 'docker compose'; fi)

DOCKER_SERVICES := postgres redis backend worker beat frontend

PID_DIR ?= .make/pids
LOG_DIR ?= .make/logs
BACKEND_VENV ?= backend/.venv
BACKEND_BIN := $(CURDIR)/$(BACKEND_VENV)/bin
LOCAL_BACKEND_HOST ?= 0.0.0.0
LOCAL_BACKEND_PORT ?= 8000
LOCAL_FRONTEND_HOST ?= 0.0.0.0
LOCAL_FRONTEND_PORT ?= 3000
LOCAL_WAIT_SECONDS ?= 30
CELERY_LOG_LEVEL ?= info

# Local infrastructure defaults to Homebrew services on macOS.
# Use LOCAL_INFRA=external when PostgreSQL/Redis are managed outside Make.
LOCAL_INFRA ?= brew
BREW_POSTGRES_SERVICE ?= postgresql@16
BREW_REDIS_SERVICE ?= redis
LOCAL_DB_NAME ?= aifc
LOCAL_DB_USER ?= aifc
LOCAL_DB_PASSWORD ?= aifc
POSTGRES_HOST ?= localhost
POSTGRES_PORT ?= 5432
REDIS_HOST ?= localhost
REDIS_PORT ?= 6379

.PHONY: help
help: ## Show available Make targets
	@awk 'BEGIN {FS = ":.*##"; printf "\nDrawLift service management\n\nUsage:\n  make <target> [VARIABLE=value]\n\nTargets:\n"} /^[a-zA-Z0-9_.-]+:.*##/ {printf "  \033[36m%-28s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)
	@printf "\nSpecific Docker service targets:\n"
	@printf "  \033[36m%-28s\033[0m %s\n" "docker-up-postgres" "Start PostgreSQL with Docker" "docker-up-redis" "Start Redis with Docker" "docker-up-backend" "Start FastAPI with Docker" "docker-up-worker" "Start Celery worker with Docker" "docker-up-beat" "Start Celery Beat with Docker" "docker-up-frontend" "Start Next.js with Docker"
	@printf "  \033[36m%-28s\033[0m %s\n" "docker-stop-postgres" "Stop PostgreSQL Docker service" "docker-stop-redis" "Stop Redis Docker service" "docker-stop-backend" "Stop FastAPI Docker service" "docker-stop-worker" "Stop Celery worker Docker service" "docker-stop-beat" "Stop Celery Beat Docker service" "docker-stop-frontend" "Stop Next.js Docker service"
	@printf "\nCommon variables:\n  COMPOSE=%s\n  LOCAL_INFRA=%s (brew|external)\n  BACKEND_VENV=%s\n\n" "$(COMPOSE)" "$(LOCAL_INFRA)" "$(BACKEND_VENV)"

define start_local_service
	@mkdir -p "$(PID_DIR)" "$(LOG_DIR)"
	@if [ -f "$(PID_DIR)/$(1).pid" ] && kill -0 "$$(cat "$(PID_DIR)/$(1).pid")" 2>/dev/null; then \
		echo "$(1) already running (pid $$(cat "$(PID_DIR)/$(1).pid"))"; \
	else \
		echo "Starting $(1)..."; \
		nohup $(SHELL) -lc '$(2)' > "$(LOG_DIR)/$(1).log" 2>&1 & echo $$! > "$(PID_DIR)/$(1).pid"; \
		echo "$(1) started (pid $$(cat "$(PID_DIR)/$(1).pid"), log $(LOG_DIR)/$(1).log)"; \
	fi
endef

define stop_local_service
	@if [ -f "$(PID_DIR)/$(1).pid" ]; then \
		PID="$$(cat "$(PID_DIR)/$(1).pid")"; \
		if kill -0 "$$PID" 2>/dev/null; then \
			echo "Stopping $(1) (pid $$PID)..."; \
			kill "$$PID" 2>/dev/null || true; \
			for _ in $$(seq 1 10); do \
				kill -0 "$$PID" 2>/dev/null || break; \
				sleep 1; \
			done; \
			if kill -0 "$$PID" 2>/dev/null; then \
				echo "Force stopping $(1) (pid $$PID)..."; \
				kill -9 "$$PID" 2>/dev/null || true; \
			fi; \
		else \
			echo "$(1) pid file exists, but process $$PID is not running"; \
		fi; \
		rm -f "$(PID_DIR)/$(1).pid"; \
	else \
		echo "$(1) is not running"; \
	fi
endef

define wait_port
	@echo "Waiting for $(1) on $(2):$(3)..."
	@for _ in $$(seq 1 $(LOCAL_WAIT_SECONDS)); do \
		if nc -z "$(2)" "$(3)" >/dev/null 2>&1; then \
			echo "$(1) is reachable"; \
			exit 0; \
		fi; \
		sleep 1; \
	done; \
	echo "$(1) did not become reachable on $(2):$(3) within $(LOCAL_WAIT_SECONDS)s"; \
	exit 1
endef

.PHONY: check-compose
check-compose:
	@if ! $(COMPOSE) version >/dev/null 2>&1; then \
		echo "Docker Compose is unavailable. Install Docker Compose or override COMPOSE, e.g. make docker-up COMPOSE=docker-compose"; \
		exit 1; \
	fi

.PHONY: check-brew
check-brew:
	@if [ "$(LOCAL_INFRA)" = "brew" ] && ! command -v brew >/dev/null 2>&1; then \
		echo "Homebrew is required for LOCAL_INFRA=brew. Install brew or run with LOCAL_INFRA=external after starting PostgreSQL/Redis yourself."; \
		exit 1; \
	fi

.PHONY: check-backend-venv
check-backend-venv:
	@if [ ! -x "$(BACKEND_BIN)/uvicorn" ] || [ ! -x "$(BACKEND_BIN)/celery" ] || [ ! -x "$(BACKEND_BIN)/alembic" ]; then \
		echo "Backend virtualenv is missing required commands under $(BACKEND_VENV)."; \
		echo "Run: cd backend && python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt"; \
		exit 1; \
	fi

.PHONY: check-frontend-deps
check-frontend-deps:
	@if [ ! -d "frontend/node_modules" ]; then \
		echo "Frontend dependencies are missing. Run: cd frontend && npm install"; \
		exit 1; \
	fi

.PHONY: docker-up docker-down docker-restart docker-build docker-ps docker-logs docker-migrate docker-up-dwg
docker-up: check-compose ## Start all Docker services (frontend, backend, worker, beat, postgres, redis)
	$(COMPOSE) up -d --build $(DOCKER_SERVICES)

docker-down: check-compose ## Stop and remove all Docker services
	$(COMPOSE) down

docker-restart: docker-down docker-up ## Restart all Docker services

docker-build: check-compose ## Build Docker service images
	$(COMPOSE) build $(DOCKER_SERVICES)

docker-ps: check-compose ## Show Docker service status
	$(COMPOSE) ps

docker-logs: check-compose ## Follow logs for all Docker services
	$(COMPOSE) logs -f --tail=100

docker-migrate: check-compose ## Run Alembic migrations in the Docker backend service
	$(COMPOSE) exec backend alembic upgrade head

docker-up-dwg: check-compose ## Start default Docker services plus the optional DWG converter profile
	$(COMPOSE) --profile dwg up -d --build $(DOCKER_SERVICES) dwg-converter

.PHONY: docker-up-postgres docker-up-redis docker-up-backend docker-up-worker docker-up-beat docker-up-frontend docker-up-service
docker-up-postgres docker-up-redis docker-up-backend docker-up-worker docker-up-beat docker-up-frontend: check-compose ## Start one Docker service (target suffix selects service)
	$(COMPOSE) up -d --build $(subst docker-up-,,$@)

docker-up-service: check-compose ## Start one Docker service with SERVICE=<name>
	@test -n "$(SERVICE)" || (echo "Usage: make docker-up-service SERVICE=backend" && exit 1)
	$(COMPOSE) up -d --build $(SERVICE)

.PHONY: docker-stop-postgres docker-stop-redis docker-stop-backend docker-stop-worker docker-stop-beat docker-stop-frontend docker-stop-service
docker-stop-postgres docker-stop-redis docker-stop-backend docker-stop-worker docker-stop-beat docker-stop-frontend: check-compose ## Stop one Docker service (target suffix selects service)
	$(COMPOSE) stop $(subst docker-stop-,,$@)

docker-stop-service: check-compose ## Stop one Docker service with SERVICE=<name>
	@test -n "$(SERVICE)" || (echo "Usage: make docker-stop-service SERVICE=backend" && exit 1)
	$(COMPOSE) stop $(SERVICE)

.PHONY: local-up local-down local-restart local-status local-db-setup local-migrate local-logs
local-up: local-up-postgres local-db-setup local-up-redis local-migrate local-up-backend local-up-worker local-up-beat local-up-frontend ## Start all services without Docker (Homebrew infra + local app processes)
	@echo "Local stack started. Frontend: http://localhost:$(LOCAL_FRONTEND_PORT) Backend: http://localhost:$(LOCAL_BACKEND_PORT)/api/v1/health"

local-down: local-down-frontend local-down-beat local-down-worker local-down-backend local-down-redis local-down-postgres ## Stop all non-Docker services started by Make
	@echo "Local stack stopped."

local-restart: local-down local-up ## Restart all non-Docker services

local-status: ## Show local PID-managed service status and infrastructure ports
	@mkdir -p "$(PID_DIR)"
	@for service in backend worker beat frontend; do \
		if [ -f "$(PID_DIR)/$$service.pid" ] && kill -0 "$$(cat "$(PID_DIR)/$$service.pid")" 2>/dev/null; then \
			echo "$$service: running (pid $$(cat "$(PID_DIR)/$$service.pid"))"; \
		else \
			echo "$$service: stopped"; \
		fi; \
	done
	@nc -z "$(POSTGRES_HOST)" "$(POSTGRES_PORT)" >/dev/null 2>&1 && echo "postgres: reachable on $(POSTGRES_HOST):$(POSTGRES_PORT)" || echo "postgres: not reachable on $(POSTGRES_HOST):$(POSTGRES_PORT)"
	@nc -z "$(REDIS_HOST)" "$(REDIS_PORT)" >/dev/null 2>&1 && echo "redis: reachable on $(REDIS_HOST):$(REDIS_PORT)" || echo "redis: not reachable on $(REDIS_HOST):$(REDIS_PORT)"

local-db-setup: ## Create the local PostgreSQL role/database expected by .env
	@if [ "$(LOCAL_INFRA)" = "external" ]; then \
		echo "LOCAL_INFRA=external: skipping PostgreSQL role/database setup"; \
	elif ! command -v psql >/dev/null 2>&1; then \
		echo "psql is unavailable; install PostgreSQL client tools or create role/database manually"; \
		exit 1; \
	else \
		if ! psql postgres -tAc "SELECT 1 FROM pg_roles WHERE rolname='$(LOCAL_DB_USER)'" | grep -q 1; then \
			echo "Creating PostgreSQL role $(LOCAL_DB_USER)..."; \
			psql postgres -v ON_ERROR_STOP=1 -c "CREATE ROLE $(LOCAL_DB_USER) LOGIN PASSWORD '$(LOCAL_DB_PASSWORD)'"; \
		fi; \
		if ! psql postgres -tAc "SELECT 1 FROM pg_database WHERE datname='$(LOCAL_DB_NAME)'" | grep -q 1; then \
			echo "Creating PostgreSQL database $(LOCAL_DB_NAME)..."; \
			createdb -O "$(LOCAL_DB_USER)" "$(LOCAL_DB_NAME)"; \
		fi; \
	fi

local-migrate: check-backend-venv ## Run Alembic migrations without Docker
	cd backend && "$(BACKEND_BIN)/alembic" upgrade head

local-logs: ## Follow all local app logs created by Make
	@mkdir -p "$(LOG_DIR)"
	tail -n 100 -f "$(LOG_DIR)"/*.log

.PHONY: local-up-postgres local-up-redis local-down-postgres local-down-redis
local-up-postgres: check-brew ## Start local PostgreSQL without Docker (Homebrew by default)
	@if [ "$(LOCAL_INFRA)" = "external" ]; then \
		echo "LOCAL_INFRA=external: assuming PostgreSQL is managed outside Make"; \
	else \
		brew services start "$(BREW_POSTGRES_SERVICE)"; \
	fi
	$(call wait_port,PostgreSQL,$(POSTGRES_HOST),$(POSTGRES_PORT))

local-up-redis: check-brew ## Start local Redis without Docker (Homebrew by default)
	@if [ "$(LOCAL_INFRA)" = "external" ]; then \
		echo "LOCAL_INFRA=external: assuming Redis is managed outside Make"; \
	else \
		brew services start "$(BREW_REDIS_SERVICE)"; \
	fi
	$(call wait_port,Redis,$(REDIS_HOST),$(REDIS_PORT))

local-down-postgres: check-brew ## Stop local PostgreSQL if LOCAL_INFRA=brew
	@if [ "$(LOCAL_INFRA)" = "external" ]; then \
		echo "LOCAL_INFRA=external: leaving PostgreSQL untouched"; \
	else \
		brew services stop "$(BREW_POSTGRES_SERVICE)" || true; \
	fi

local-down-redis: check-brew ## Stop local Redis if LOCAL_INFRA=brew
	@if [ "$(LOCAL_INFRA)" = "external" ]; then \
		echo "LOCAL_INFRA=external: leaving Redis untouched"; \
	else \
		brew services stop "$(BREW_REDIS_SERVICE)" || true; \
	fi

.PHONY: local-up-backend local-up-worker local-up-beat local-up-frontend
local-up-backend: check-backend-venv ## Start FastAPI without Docker in the background
	$(call start_local_service,backend,cd backend && "$(BACKEND_BIN)/uvicorn" app.main:app --reload --host "$(LOCAL_BACKEND_HOST)" --port "$(LOCAL_BACKEND_PORT)")

local-up-worker: check-backend-venv ## Start Celery worker without Docker in the background
	$(call start_local_service,worker,cd backend && "$(BACKEND_BIN)/celery" -A app.tasks.celery_app worker --loglevel="$(CELERY_LOG_LEVEL)")

local-up-beat: check-backend-venv ## Start Celery Beat without Docker in the background
	$(call start_local_service,beat,cd backend && "$(BACKEND_BIN)/celery" -A app.tasks.celery_app beat --loglevel="$(CELERY_LOG_LEVEL)")

local-up-frontend: check-frontend-deps ## Start Next.js without Docker in the background
	$(call start_local_service,frontend,cd frontend && npm run dev -- --hostname "$(LOCAL_FRONTEND_HOST)" --port "$(LOCAL_FRONTEND_PORT)")

.PHONY: local-down-backend local-down-worker local-down-beat local-down-frontend
local-down-backend: ## Stop local FastAPI process started by Make
	$(call stop_local_service,backend)

local-down-worker: ## Stop local Celery worker process started by Make
	$(call stop_local_service,worker)

local-down-beat: ## Stop local Celery Beat process started by Make
	$(call stop_local_service,beat)

local-down-frontend: ## Stop local Next.js process started by Make
	$(call stop_local_service,frontend)

.PHONY: logs-backend logs-worker logs-beat logs-frontend clean-local-runtime
logs-backend logs-worker logs-beat logs-frontend: ## Follow one local service log (target suffix selects service)
	@mkdir -p "$(LOG_DIR)"
	tail -n 100 -f "$(LOG_DIR)/$(subst logs-,,$@).log"

clean-local-runtime: ## Remove local Make PID/log runtime files
	rm -rf "$(PID_DIR)" "$(LOG_DIR)"

.PHONY: up down restart
up: local-up ## Alias: start all services without Docker

down: local-down ## Alias: stop all services without Docker

restart: local-restart ## Alias: restart all services without Docker