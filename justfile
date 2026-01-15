# Scroll Press development commands

# Install dependencies
install:
    uv sync

# Run development server (HTTPS-only, detached by default, add 'attach' to run in foreground)
dev MODE="detached":
    #!/usr/bin/env bash
    set -a && source .env && set +a
    PORT=${PORT:-7999}
    
    # Auto-generate certificates if they don't exist
    if [[ ! -f "certs/cert.pem" || ! -f "certs/key.pem" ]]; then
        echo "SSL certificates not found. Generating..."
        just gen-certs > /dev/null 2>&1
    fi
    
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
            echo "Starting HTTPS server on port $PORT (attached mode)"
            uv run uvicorn main:app --reload --port $PORT --ssl-keyfile certs/key.pem --ssl-certfile certs/cert.pem
        else
            nohup uv run uvicorn main:app --reload --port $PORT --ssl-keyfile certs/key.pem --ssl-certfile certs/cert.pem > server.log 2>&1 &
            sleep 2
            echo "HTTPS server started on port $PORT (detached mode - use 'just dev attach' for attached mode)"
            echo "Visit: https://localhost:$PORT"
        fi
    fi

# Stop the development server
stop:
    #!/usr/bin/env bash
    set -a && source .env && set +a
    PORT=${PORT:-7999}
    
    if lsof -i :$PORT > /dev/null 2>&1; then
        echo "Stopping server on port $PORT..."
        lsof -ti:$PORT | xargs kill -9
        echo "Server stopped"
    else
        echo "No server running on port $PORT"
    fi

# Run tests (adapts to local vs CI environment)
test:
    #!/usr/bin/env bash
    set -e
    # Run unit tests
    uv run pytest -n auto -m "not e2e"

    # Run E2E tests based on environment
    if [ -n "$CI" ]; then
        # CI: Run all test types separately for cross-browser testing
        echo "CI detected - running full cross-browser test suite"
        uv run pytest -m "e2e and not desktop and not mobile" -v
        uv run pytest -m "e2e and desktop" -v
        uv run pytest -m "e2e and mobile" -v
    else
        # Local: Run universal tests only (faster)
        echo "Local environment - running universal E2E tests"
        uv run pytest -m "e2e and not desktop and not mobile" -v
    fi

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
    #!/usr/bin/env bash
    set -e
    # Check if examples-press submodule exists
    if [[ ! -f "examples-press/scrolls.json" ]]; then
        echo "examples-press submodule not found. Initializing..."
        git submodule update --init examples-press
    fi
    PYTHONPATH=. uv run python scripts/seed.py

# Reset database (migrate + seed)
reset-db: migrate seed

# Run all checks
check: lint test

# Generate self-signed SSL certificates for HTTPS development
gen-certs:
    #!/usr/bin/env bash
    mkdir -p certs
    if [[ -f "certs/cert.pem" && -f "certs/key.pem" ]]; then
        echo "SSL certificates already exist in certs/"
    else
        echo "Generating self-signed SSL certificates..."
        openssl req -x509 -newkey rsa:4096 -keyout certs/key.pem -out certs/cert.pem -days 365 -nodes -subj "/C=US/ST=State/L=City/O=Organization/CN=localhost"
        echo "SSL certificates generated in certs/"
        echo "Use 'just dev-https' to start HTTPS server"
    fi

# Setup project from scratch
init: install migrate seed
    @echo "Project setup complete! Run 'just dev' to start the server."
