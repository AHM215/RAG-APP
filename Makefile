.PHONY: help install dev up-dev down-dev build up down logs \
        db-create db-migrate db-migrate-undo db-migration db-migrate-dev \
        db-create-migration db-reset db-recreate db-seed db-merge-heads \
        lint format test

# =============================================================================
# HELP & DOCUMENTATION
# =============================================================================

help: ## Show available commands
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  %-20s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

# =============================================================================
# INSTALLATION & SETUP
# =============================================================================

install: ## Install all dependencies
	cd src && poetry lock && poetry install

# =============================================================================
# DEVELOPMENT COMMANDS
# =============================================================================

POETRY_ENV_PATH := $(shell cd src && poetry env info --path)
COMPOSE := docker compose -f docker/docker-compose.yml

dev: ## Run src in development mode
	cd src && poetry run uvicorn main:app --reload --host 0.0.0.0 --port 8000

POSTGRES_PASSWORD := $(shell grep POSTGRES_PASSWORD docker/env/.env.postgres | cut -d= -f2 | tr -d '"')

db-create: ## Create the minirag database if it doesn't exist
	@echo "Creating database if not exists..."
	$(COMPOSE) exec -e PGPASSWORD=$(POSTGRES_PASSWORD) pgvector psql -U postgres -tc \
		"SELECT 1 FROM pg_database WHERE datname = 'minirag'" | grep -q 1 || \
		$(COMPOSE) exec -e PGPASSWORD=$(POSTGRES_PASSWORD) pgvector psql -U postgres -c "CREATE DATABASE minirag;"

up-dev: ## Start infrastructure services and run app locally #  rabbitmq redis
	@echo "Starting infrastructure services..."
	$(COMPOSE) up -d pgvector pgadmin 
	@echo "Waiting for services to be ready..."
	@sleep 5
	$(MAKE) db-create
	(. $(POETRY_ENV_PATH)/bin/activate && \
	cd src && \
	echo "Starting database migrations..." && \
	cd models/minirag && \
	poetry run alembic upgrade head && \
	cd ../.. && \
	poetry run uvicorn main:app --reload --host 0.0.0.0 --port 8000)

down-dev: ## Stop all development services
	@echo "Stopping development services..."
	@fuser -k 8000/tcp 2>/dev/null || true
	@echo "Stopping infrastructure services..."
	$(COMPOSE) down
	@echo "All services stopped successfully"

# =============================================================================
# DOCKER COMMANDS
# =============================================================================

build: ## Build all services
	$(COMPOSE) build

up: ## Start all services
	$(COMPOSE) up -d

up-infra: ## Start infrastructure services only (pgvector, redis, rabbitmq, qdrant)
	$(COMPOSE) up -d pgvector pgadmin rabbitmq redis qdrant

up-monitoring: ## Start monitoring stack (prometheus, grafana, exporters)
	$(COMPOSE) up -d prometheus grafana node-exporter postgres-exporter

up-workers: ## Start celery workers and flower
	$(COMPOSE) up -d celery-worker celery-beat flower

down: ## Stop all services
	$(COMPOSE) down

down-volumes: ## Stop all services and remove volumes
	$(COMPOSE) down -v

logs: ## Show logs from all services
	$(COMPOSE) logs -f

logs-app: ## Show logs from app services only
	$(COMPOSE) logs -f fastapi celery-worker celery-beat flower

logs-infra: ## Show logs from infrastructure services only
	$(COMPOSE) logs -f pgvector rabbitmq redis qdrant

# =============================================================================
# DATABASE COMMANDS
# =============================================================================

# Database migrations (Docker)
db-migrate: ## Run database migrations
	$(COMPOSE) exec fastapi poetry run alembic upgrade head

db-migrate-undo: ## Undo the last migration
	$(COMPOSE) exec fastapi poetry run alembic downgrade -1

db-migration: ## Create new migration (usage: make db-migration NAME="description")
	$(COMPOSE) exec fastapi poetry run alembic revision --autogenerate -m "$(NAME)"

# Database migrations (Development)
db-migrate-dev: ## Run migrations in development mode
	(. $(POETRY_ENV_PATH)/bin/activate && \
	cd src/models/minirag && \
	poetry run alembic upgrade head)

db-create-migration: ## Create a new migration in dev mode (usage: make db-create-migration NAME="description")
	(. $(POETRY_ENV_PATH)/bin/activate && \
	cd src/models/minirag && \
	poetry run alembic revision --autogenerate -m "$(NAME)")

# Database utilities
db-reset: ## Drop and recreate the database
	@echo "Resetting database..."
	$(COMPOSE) exec pgvector psql -U postgres -c "DROP DATABASE IF EXISTS minirag;"
	$(COMPOSE) exec pgvector psql -U postgres -c "CREATE DATABASE minirag;"

db-recreate: db-reset db-migrate-dev ## Full reset: drop, create, and migrate

db-seed: ## Populate database with demo data
	cd src && poetry run python -m scripts.seeder

db-merge-heads: ## Merge alembic heads
	(. $(POETRY_ENV_PATH)/bin/activate && \
	cd src/models/minirag && \
	poetry run alembic merge heads)

# =============================================================================
# CELERY COMMANDS
# =============================================================================

celery-worker: ## Start celery worker locally
	cd src && poetry run celery -A celery_app worker --queues=default,file_processing,data_indexing --loglevel=info

celery-beat: ## Start celery beat locally
	cd src && poetry run celery -A celery_app beat --loglevel=info

celery-flower: ## Start flower dashboard locally
	cd src && poetry run celery -A celery_app flower --conf=flowerconfig.py

# =============================================================================
# CODE QUALITY & TESTING
# =============================================================================

lint: ## Check code quality
	cd src && poetry run ruff check .
	cd src && poetry run black --check .

format: ## Format code
	cd src && poetry run black .
	cd src && poetry run ruff --fix .

test: ## Run tests
	cd src && poetry run pytest