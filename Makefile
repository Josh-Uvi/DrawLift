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

# Hybrid local development runs frontend/backend on the host, while PostgreSQL,
# Redis, worker, and optional Beat run in Docker. The host backend and Docker
# worker must share storage/model directories so queued jobs can read the same
# files regardless of which process created them.
LOCAL_STORAGE_DIR ?= ./backend/storage
LOCAL_MODELS_DIR ?= ./backend/models
LOCAL_DOCKER_ENV := STORAGE_VOLUME=$(LOCAL_STORAGE_DIR) MODELS_VOLUME=$(LOCAL_MODELS_DIR) STORAGE_PATH=storage MODELS_PATH=models

.PHONY: help
help: ## Show available Make targets
	@awk 'BEGIN {FS = ":.*##"; printf "\nDrawLift service management\n\nUsage:\n  make <target> [VARIABLE=value]\n\nTargets:\n"} /^[a-zA-Z0-9_.-]+:.*##/ {printf "  \033[36m%-28s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)
	@printf "\nSpecific Docker service targets:\n"
	@printf "  \033[36m%-28s\033[0m %s\n" "docker-up-postgres" "Start PostgreSQL with Docker" "docker-up-redis" "Start Redis with Docker" "docker-up-backend" "Start FastAPI with Docker" "docker-up-worker" "Start Celery worker with Docker" "docker-up-beat" "Start Celery Beat with Docker" "docker-up-frontend" "Start Next.js with Docker"
	@printf "  \033[36m%-28s\033[0m %s\n" "docker-stop-postgres" "Stop PostgreSQL Docker service" "docker-stop-redis" "Stop Redis Docker service" "docker-stop-backend" "Stop FastAPI Docker service" "docker-stop-worker" "Stop Celery worker Docker service" "docker-stop-beat" "Stop Celery Beat Docker service" "docker-stop-frontend" "Stop Next.js Docker service"
	@printf "\nHybrid local development:\n"
	@printf "  \033[36m%-28s\033[0m %s\n" "local-up" "Host frontend/backend + Docker postgres/redis/worker" "local-down" "Stop host frontend/backend + Docker local services" "local-up-beat" "Optionally start cleanup scheduler in Docker"
	@printf "\nCommon variables:\n  COMPOSE=%s\n  BACKEND_VENV=%s\n  LOCAL_STORAGE_DIR=%s\n  LOCAL_MODELS_DIR=%s\n\n" "$(COMPOSE)" "$(BACKEND_VENV)" "$(LOCAL_STORAGE_DIR)" "$(LOCAL_MODELS_DIR)"

define start_host_service
	@mkdir -p "$(PID_DIR)" "$(LOG_DIR)"
	@if [ -f "$(PID_DIR)/$(1).pid" ] && kill -0 "$$(cat "$(PID_DIR)/$(1).pid")" 2>/dev/null; then \
		echo "$(1) already running on the host (pid $$(cat "$(PID_DIR)/$(1).pid"))"; \
	else \
		echo "Starting $(1) on the host..."; \
		nohup $(SHELL) -lc '$(2)' > "$(LOG_DIR)/$(1).log" 2>&1 & echo $$! > "$(PID_DIR)/$(1).pid"; \
		echo "$(1) started (pid $$(cat "$(PID_DIR)/$(1).pid"), log $(LOG_DIR)/$(1).log)"; \
	fi
endef

define stop_host_service
	@if [ -f "$(PID_DIR)/$(1).pid" ]; then \
		PID="$$(cat "$(PID_DIR)/$(1).pid")"; \
		if kill -0 "$$PID" 2>/dev/null; then \
			echo "Stopping host $(1) (pid $$PID)..."; \
			kill "$$PID" 2>/dev/null || true; \
			for _ in $$(seq 1 10); do \
				kill -0 "$$PID" 2>/dev/null || break; \
				sleep 1; \
			done; \
			if kill -0 "$$PID" 2>/dev/null; then \
				echo "Force stopping host $(1) (pid $$PID)..."; \
				kill -9 "$$PID" 2>/dev/null || true; \
			fi; \
		else \
			echo "$(1) pid file exists, but process $$PID is not running"; \
		fi; \
		rm -f "$(PID_DIR)/$(1).pid"; \
	else \
		echo "host $(1) is not running"; \
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

.PHONY: check-backend-venv
check-backend-venv:
	@if [ ! -x "$(BACKEND_BIN)/uvicorn" ] || [ ! -x "$(BACKEND_BIN)/alembic" ]; then \
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

.PHONY: prepare-local-docker
prepare-local-docker:
	mkdir -p "$(LOCAL_STORAGE_DIR)" "$(LOCAL_MODELS_DIR)"

.PHONY: docker-up docker-up-dev docker-up-prod docker-down docker-restart docker-build docker-ps docker-logs docker-migrate docker-up-dwg
docker-up: check-compose ## Start all Docker services (frontend, backend, worker, beat, postgres, redis)
	$(COMPOSE) up -d --build $(DOCKER_SERVICES)

docker-up-dev: docker-up ## Alias for all-Docker local development/test startup

docker-up-prod: docker-up ## Alias for all-Docker production-like startup

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

.PHONY: local-up local-down local-restart local-status local-migrate local-logs
local-up: local-up-postgres local-up-redis local-migrate local-up-worker local-up-backend local-up-frontend ## Start hybrid local dev: host frontend/backend + Docker postgres/redis/worker
	@echo "Hybrid local stack started. Frontend: http://localhost:$(LOCAL_FRONTEND_PORT) Backend: http://localhost:$(LOCAL_BACKEND_PORT)/api/v1/health"

local-down: local-down-frontend local-down-backend local-down-beat local-down-worker local-down-redis local-down-postgres ## Stop hybrid local dev services
	@echo "Hybrid local stack stopped."

local-restart: local-down local-up ## Restart hybrid local dev services

local-status: check-compose ## Show host frontend/backend and Docker local service status
	@mkdir -p "$(PID_DIR)"
	@for service in backend frontend; do \
		if [ -f "$(PID_DIR)/$$service.pid" ] && kill -0 "$$(cat "$(PID_DIR)/$$service.pid")" 2>/dev/null; then \
			echo "host $$service: running (pid $$(cat "$(PID_DIR)/$$service.pid"))"; \
		else \
			echo "host $$service: stopped"; \
		fi; \
	done
	$(LOCAL_DOCKER_ENV) $(COMPOSE) ps postgres redis worker beat

local-migrate: check-backend-venv ## Run Alembic migrations from the host backend against Docker PostgreSQL
	cd backend && "$(BACKEND_BIN)/alembic" upgrade head

local-logs: ## Follow host backend/frontend logs created by Make
	@mkdir -p "$(LOG_DIR)"
	tail -n 100 -f "$(LOG_DIR)"/*.log

.PHONY: local-up-postgres local-up-redis local-up-worker local-up-beat local-down-postgres local-down-redis local-down-worker local-down-beat
local-up-postgres: check-compose prepare-local-docker ## Start local-dev PostgreSQL in Docker
	$(LOCAL_DOCKER_ENV) $(COMPOSE) up -d postgres
	$(call wait_port,PostgreSQL,localhost,5432)

local-up-redis: check-compose prepare-local-docker ## Start local-dev Redis in Docker
	$(LOCAL_DOCKER_ENV) $(COMPOSE) up -d redis
	$(call wait_port,Redis,localhost,6379)

local-up-worker: check-compose prepare-local-docker ## Start local-dev Celery worker in Docker
	$(LOCAL_DOCKER_ENV) $(COMPOSE) up -d --build worker

local-up-beat: check-compose prepare-local-docker ## Optionally start local-dev Celery Beat in Docker
	$(LOCAL_DOCKER_ENV) $(COMPOSE) up -d --build beat

local-down-postgres: check-compose ## Stop local-dev Docker PostgreSQL
	$(LOCAL_DOCKER_ENV) $(COMPOSE) stop postgres

local-down-redis: check-compose ## Stop local-dev Docker Redis
	$(LOCAL_DOCKER_ENV) $(COMPOSE) stop redis

local-down-worker: check-compose ## Stop local-dev Docker worker
	$(LOCAL_DOCKER_ENV) $(COMPOSE) stop worker

local-down-beat: check-compose ## Stop local-dev Docker Beat if running
	$(LOCAL_DOCKER_ENV) $(COMPOSE) stop beat || true

.PHONY: local-up-backend local-up-frontend local-down-backend local-down-frontend
local-up-backend: check-backend-venv prepare-local-docker ## Start FastAPI on the host
	$(call start_host_service,backend,cd backend && "$(BACKEND_BIN)/uvicorn" app.main:app --reload --host "$(LOCAL_BACKEND_HOST)" --port "$(LOCAL_BACKEND_PORT)")

local-up-frontend: check-frontend-deps ## Start Next.js on the host
	$(call start_host_service,frontend,cd frontend && npm run dev -- --hostname "$(LOCAL_FRONTEND_HOST)" --port "$(LOCAL_FRONTEND_PORT)")

local-down-backend: ## Stop host FastAPI process started by Make
	$(call stop_host_service,backend)

local-down-frontend: ## Stop host Next.js process started by Make
	$(call stop_host_service,frontend)

.PHONY: logs-backend logs-frontend logs-worker logs-beat clean-local-runtime
logs-backend logs-frontend: ## Follow one host service log (target suffix selects service)
	@mkdir -p "$(LOG_DIR)"
	tail -n 100 -f "$(LOG_DIR)/$(subst logs-,,$@).log"

logs-worker logs-beat: check-compose ## Follow one Docker service log (target suffix selects service)
	$(LOCAL_DOCKER_ENV) $(COMPOSE) logs -f --tail=100 $(subst logs-,,$@)

clean-local-runtime: ## Remove host Make PID/log runtime files
	rm -rf "$(PID_DIR)" "$(LOG_DIR)"

.PHONY: up down restart
up: local-up ## Alias: start hybrid local dev services

down: local-down ## Alias: stop hybrid local dev services

restart: local-restart ## Alias: restart hybrid local dev services