# Preview Press development commands

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
        uvicorn main:app --reload --port $PORT
    fi

# Run tests
test:
    pytest

# Run tests with coverage
test-cov:
    pytest --cov=app --cov-report=term-missing

# Format and lint code
lint:
    ruff check .
    ruff format .

# Database migrations
migrate:
    alembic upgrade head

# Create new migration
migration message:
    alembic revision --autogenerate -m "{{message}}"

# Seed database with sample data
seed:
    python app/seed.py

# Reset database (migrate + seed)
reset-db: migrate seed

# Run all checks (lint + test)
check: lint test

# Setup project from scratch
init: install migrate seed
    @echo "Project setup complete! Run 'just dev' to start the server."
