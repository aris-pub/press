# Scroll Press development commands

# Install dependencies
install:
    uv sync

# Run development server (only if not already running)
dev:
    #!/usr/bin/env bash
    set -a && source .env && set +a
    PORT=${PORT:-8000}
    if lsof -i :$PORT > /dev/null 2>&1; then
        echo "Server already running on port $PORT"
    else
        uv run uvicorn main:app --reload --port $PORT
    fi

# Run tests
test:
    uv run pytest -n auto

# Run tests with coverage
test-cov:
    uv run pytest --cov=app --cov-report=term-missing

# Format and lint code
lint:
    uv run ruff check --fix .
    uv run ruff format .

# Database migrations
migrate:
    uv run alembic upgrade head

# Create new migration
migration message:
    uv run alembic revision --autogenerate -m "{{message}}"

# Seed database with sample data
seed:
    uv run python app/seed.py

# Reset database (migrate + seed)
reset-db: migrate seed

# Run all checks (lint + test)
check: lint test

# Setup project from scratch
init: install migrate seed
    @echo "Project setup complete! Run 'just dev' to start the server."
