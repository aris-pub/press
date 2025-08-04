# Scroll Press development commands

# Install dependencies
install:
    uv sync

# Run development server (detached by default, add 'attach' to run in foreground)
dev MODE="detached":
    #!/usr/bin/env bash
    set -a && source .env && set +a
    PORT=${PORT:-8000}
    
    # Check mode parameter
    if [[ "{{MODE}}" == "attach" ]]; then
        ATTACH_MODE=true
    else
        ATTACH_MODE=false
    fi
    
    if lsof -i :$PORT > /dev/null 2>&1; then
        echo "Server already running on port $PORT"
    else
        if [[ "$ATTACH_MODE" == "true" ]]; then
            echo "Starting server on port $PORT (attached mode)"
            uv run uvicorn main:app --reload --port $PORT
        else
            nohup uv run uvicorn main:app --reload --port $PORT > server.log 2>&1 &
            sleep 2
            echo "Server started on port $PORT (detached mode - use 'just dev attach' for attached mode)"
        fi
    fi

# Stop the development server
stop:
    #!/usr/bin/env bash
    set -a && source .env && set +a
    PORT=${PORT:-8000}
    
    if lsof -i :$PORT > /dev/null 2>&1; then
        echo "Stopping server on port $PORT..."
        lsof -ti:$PORT | xargs kill -9
        echo "Server stopped"
    else
        echo "No server running on port $PORT"
    fi

# Run all tests (unit + e2e)
test:
    uv run pytest -n auto -m "not e2e"
    uv run pytest tests/e2e/ -v

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
    PYTHONPATH=. uv run python app/seed.py

# Reset database (migrate + seed)
reset-db: migrate seed

# Run all checks
check: lint test

# Setup project from scratch
init: install migrate seed
    @echo "Project setup complete! Run 'just dev' to start the server."
