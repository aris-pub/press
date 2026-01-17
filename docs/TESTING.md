# Testing Documentation

## Overview

Scroll Press includes comprehensive testing with both unit/integration tests and end-to-end browser tests to ensure reliability and prevent regressions.

## Unit and Integration Tests

### Running Tests
```bash
# Run all tests
just test

# Run with coverage report
just test-cov

# Run specific test file
uv run pytest tests/test_main.py -v

# Run specific test function
uv run pytest tests/test_auth.py::test_registration -v
```

### Test Configuration
- **Framework**: pytest with pytest-asyncio
- **Database**: SQLite in-memory for fast, isolated execution
- **HTTP Client**: httpx for async requests
- **Fixtures**: Defined in `tests/conftest.py`

### Test Coverage
- Authentication (registration, login, email verification, password reset)
- Scroll upload and management (draft/publish workflow)
- GDPR data export
- Subject categorization
- Session management
- Email service integration

### Database Isolation
Each test gets a fresh database:
1. In-memory SQLite created
2. All migrations applied
3. Test executes
4. Database destroyed

This ensures tests don't interfere with each other.

## End-to-End Tests

### Overview
E2E tests use Playwright to verify complete user journeys in real browsers.

### Setup
```bash
# Install Playwright browsers (one-time setup)
uv run playwright install chromium firefox

# Start development server
just dev

# Run e2e tests (in another terminal)
uv run pytest -m e2e
```

### Critical Test Scenarios
- **Registration → Upload → Public Access**: Verifies scrolls remain publicly accessible
- **Registration → Upload → Account Deletion → Public Access**: Verifies scroll persistence after user deletion
- **License Selection**: Tests CC BY 4.0 and All Rights Reserved license workflows
- **Mobile Responsive**: Validates mobile upload and interaction flows
- **Search & Discovery**: Tests content search and subject browsing

### Playwright Best Practices
**CRITICAL**: Do NOT use session-scoped Playwright fixtures (`page`, `browser`, `browser_context`) as they cause deadlocks with pytest-asyncio.

**Correct pattern**:
```python
async def test_something():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        # Test code here

        await browser.close()
```

This pattern avoids event loop conflicts and ensures tests don't hang.

### E2E Documentation
For detailed E2E testing information, see [tests/e2e/README.md](../tests/e2e/README.md).

## Running All Tests

### Pre-commit Checks
```bash
# Run linting and unit/integration tests
just check

# This runs:
# 1. ruff check . && ruff format .
# 2. pytest (unit/integration only, excludes e2e)

# Run all tests including e2e (server must be running)
just check && uv run pytest -m e2e
```

### Continuous Integration
Tests run automatically on:
- Every push to main branch
- Every pull request

CI configuration: `.github/workflows/ci.yml`

## Test Organization

```
tests/
├── conftest.py              # Shared fixtures
├── test_auth.py             # Authentication tests
├── test_data_export.py      # GDPR export tests
├── test_main.py             # Core functionality tests
├── test_scrolls.py          # Scroll management tests
├── test_subjects.py         # Subject categorization tests
└── e2e/                     # End-to-end tests
    ├── README.md            # E2E documentation
    ├── test_upload_flow.py  # Upload workflows
    ├── test_licenses.py     # License selection
    └── test_mobile.py       # Mobile responsive tests
```

## Writing Tests

### Unit Test Example
```python
async def test_registration(client, db_session):
    response = await client.post("/auth/register", json={
        "email": "test@example.com",
        "password": "SecurePassword123",
        "display_name": "Test User"
    })
    assert response.status_code == 200
```

### E2E Test Example
```python
async def test_upload_scroll():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        await page.goto("https://localhost:7999")
        await page.fill("#email", "test@example.com")
        await page.click("button[type=submit]")

        await browser.close()
```

## Test Best Practices

1. **Use descriptive test names**: `test_user_cannot_upload_without_verification`
2. **One assertion focus per test**: Test one thing at a time
3. **Use fixtures for setup**: Don't repeat database/client setup
4. **Clean up resources**: Always close browsers in E2E tests
5. **Avoid sleep()**: Use Playwright's auto-waiting instead of arbitrary waits
6. **Test error cases**: Don't just test happy paths

## Debugging Tests

### Verbose Output
```bash
uv run pytest -v -s tests/test_auth.py
```

### Stop on First Failure
```bash
uv run pytest -x
```

### Run Last Failed Tests
```bash
uv run pytest --lf
```

### E2E Debugging
```bash
# Run with visible browser
uv run pytest tests/e2e/ --headed

# Run with slow motion
uv run pytest tests/e2e/ --slowmo 1000

# Take screenshots on failure
# (Already configured in tests)
```
