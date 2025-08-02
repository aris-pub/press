#!/bin/bash

# E2E Test Runner for Scroll Press
#
# This script runs end-to-end tests against a development server.
# It handles server startup, test execution, and cleanup.

set -e  # Exit on any error

# Configuration
SERVER_HOST="localhost"
SERVER_PORT="8000"
SERVER_URL="http://${SERVER_HOST}:${SERVER_PORT}"
SERVER_PID=""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to check if server is running
check_server() {
    curl -s -f "$SERVER_URL" > /dev/null 2>&1
}

# Function to start development server
start_server() {
    print_status "Starting development server on $SERVER_URL..."

    # Check if server is already running
    if check_server; then
        print_warning "Server is already running on $SERVER_URL"
        return 0
    fi

    # Start server in background
    uv run uvicorn main:app --host "$SERVER_HOST" --port "$SERVER_PORT" --log-level error &
    SERVER_PID=$!

    # Wait for server to start
    print_status "Waiting for server to start..."
    for i in {1..30}; do
        if check_server; then
            print_status "Server started successfully (PID: $SERVER_PID)"
            return 0
        fi
        sleep 1
    done

    print_error "Server failed to start within 30 seconds"
    return 1
}

# Function to stop server
stop_server() {
    if [ -n "$SERVER_PID" ]; then
        print_status "Stopping server (PID: $SERVER_PID)..."
        kill "$SERVER_PID" 2>/dev/null || true
        wait "$SERVER_PID" 2>/dev/null || true
        SERVER_PID=""
    fi
}

# Function to run specific test suite
run_test_suite() {
    local test_file="$1"
    local test_name="$2"

    print_status "Running $test_name..."

    if uv run pytest "$test_file" -v --tb=short; then
        print_status "$test_name passed ✓"
        return 0
    else
        print_error "$test_name failed ✗"
        return 1
    fi
}

# Cleanup function
cleanup() {
    print_status "Cleaning up..."
    stop_server

    # Remove any temporary files
    rm -f test_e2e.db
    rm -f debug.png

    exit $1
}

# Set up signal handlers
trap 'cleanup 1' INT TERM

# Main execution
main() {
    print_status "Starting Scroll Press E2E Test Runner"

    # Check dependencies
    if ! command -v uv &> /dev/null; then
        print_error "uv is not installed. Please install uv first."
        exit 1
    fi

    if ! uv run python -c "import playwright" 2>/dev/null; then
        print_error "Playwright is not installed. Run: uv run playwright install chromium firefox"
        exit 1
    fi

    # Run all e2e tests
    TEST_FILES="tests/e2e/test_live_server.py tests/e2e/test_complete_flows.py tests/e2e/test_discovery_flows.py"

    # Start server
    if ! start_server; then
        cleanup 1
    fi

    # Wait a bit more for server to be fully ready
    sleep 2

    # Verify server is responding
    if ! check_server; then
        print_error "Server is not responding at $SERVER_URL"
        cleanup 1
    fi

    # Run tests
    print_status "Running E2E tests..."
    FAILED_TESTS=0

    for test_file in $TEST_FILES; do
        if [[ "$test_file" == *"::"* ]]; then
            # Specific test
            test_name=$(basename "$test_file")
        else
            # Entire file
            test_name=$(basename "$test_file" .py)
        fi

        if ! run_test_suite "$test_file" "$test_name"; then
            ((FAILED_TESTS++))
        fi

        # Small delay between test suites
        sleep 1
    done

    # Report results
    if [ $FAILED_TESTS -eq 0 ]; then
        print_status "All E2E tests passed! ✓"
        cleanup 0
    else
        print_error "$FAILED_TESTS test suite(s) failed ✗"
        cleanup 1
    fi
}

# Run main function
main
