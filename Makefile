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

dev: ## Run src in development mode
	cd src && poetry run uvicorn main:app --reload --host 0.0.0.0 --port 8000

db-create: ## Create the minirag database if it doesn't exist
	@echo "Creating database if not exists..."
	docker compose -f docker/docker-compose.yml exec pgvector psql -U postgres -tc \
		"SELECT 1 FROM pg_database WHERE datname = 'minirag'" | grep -q 1 || \
		docker compose -f docker/docker-compose.yml exec pgvector psql -U postgres -c "CREATE DATABASE minirag;"

up-dev: ## Start all development services and servers
	@echo "Starting infrastructure services..."
	cd docker && docker compose up -d pgvector pgadmin
	@sleep 3
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
	@cd docker && docker compose down
	@echo "All services stopped successfully"

# =============================================================================
# DOCKER COMMANDS
# =============================================================================

build: ## Build all services
	cd docker && docker compose build

up: ## Start all services
	cd docker && docker compose up -d

down: ## Stop all services
	cd docker && docker compose down

logs: ## Show logs from all services
	cd docker && docker compose logs -f

# =============================================================================
# DATABASE COMMANDS
# =============================================================================

# Database migrations (Docker)
db-migrate: ## Run database migrations
	docker compose -f docker/docker-compose.yml exec fastapi poetry run alembic upgrade head

db-migrate-undo: ## Undo the last migration
	docker compose -f docker/docker-compose.yml exec fastapi poetry run alembic downgrade -1

db-migration: ## Create new migration (usage: make db-migration NAME="description")
	docker compose -f docker/docker-compose.yml exec fastapi poetry run alembic revision --autogenerate -m "$(NAME)"

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
	docker compose -f docker/docker-compose.yml exec pgvector psql -U postgres -c "DROP DATABASE IF EXISTS minirag;"
	docker compose -f docker/docker-compose.yml exec pgvector psql -U postgres -c "CREATE DATABASE minirag;"

db-recreate: db-reset db-migrate-dev ## Full reset: drop, create, and migrate

db-seed: ## Populate database with demo data
	cd src && poetry run python -m scripts.seeder

db-merge-heads: ## Merge alembic heads
	(. $(POETRY_ENV_PATH)/bin/activate && \
	cd src/models/minirag && \
	poetry run alembic merge heads)

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