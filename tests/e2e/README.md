# E2E Tests for Scroll Press

This directory contains end-to-end tests using Playwright to verify critical user journeys and browser functionality.

## Setup

E2E testing dependencies are already included in the project:
- `playwright>=1.40.0`
- `pytest-playwright>=0.4.3`

Browsers are installed via:
```bash
uv run playwright install chromium firefox
```

## Running E2E Tests

1. Start the development server:
   ```bash
   just dev
   ```

2. Run the e2e tests in another terminal:
   ```bash
   # Run all e2e tests (recommended)
   just test-e2e
   
   # Or run directly
   ./scripts/run-e2e-tests.sh
   
   # Run as part of full check suite
   just check
   ```

## Test Structure

### Current Tests

1. **`test_app_simple.py`** - Basic application setup tests
   - Server health and configuration
   - Basic page loading

2. **`test_auth_flows.py`** - Authentication flow tests
   - User registration with validation
   - Login with invalid credentials
   - Password mismatch handling
   - Display name validation

3. **`test_email_flows.py`** - Email verification and password reset tests
   - Registration shows verification message
   - Unverified users blocked from upload
   - Email verification with valid token
   - Forgot password page and submission
   - Password reset with invalid token
   - Email verification with invalid token

4. **`test_complete_flows.py`** - End-to-end user journeys
   - Basic upload flow (registration → verification → upload)
   - Homepage and registration page loading

5. **`test_dark_mode.py`** - Dark mode functionality
   - System preference detection
   - Manual override and persistence
   - Theme sync across navigation

6. **`test_security.py`** - Security header validation
   - Security headers present
   - HSTS headers on HTTPS
   - No HSTS on HTTP

7. **`test_subject_filtering_e2e.py`** - Subject filtering
   - Subject filtering works in browser
   - Show all button functionality

8. **`test_html_validation.py`** - HTML structure validation
   - Upload page requires authentication
   - Register page has form elements

### Browser Support

- **Chromium**: Primary browser for all tests
- **Firefox**: Secondary browser for compatibility verification
- **Always headless**: Tests run in headless mode by default

## Test Categories

### High Priority (Critical Flows)
- [x] Registration → Email Verification → Upload
- [x] Email verification with valid/invalid tokens
- [x] Password reset flow
- [x] Unverified user access control

### Medium Priority (Core Features)
- [x] Subject browsing and filtering
- [x] Dark mode toggle functionality
- [x] Security header validation
- [x] Authentication flows with validation

### Completed
- [x] Basic upload flow
- [x] Registration with validation
- [x] Login with invalid credentials
- [x] Mobile responsive authentication
- [x] HTML structure validation

## Test Data

Tests use generated unique data to avoid conflicts:
- Email: `e2etest_{uuid}@example.com`
- User names: `E2E Test User {uuid}`
- Scroll titles: `Test Research Paper {uuid}`

## Debugging E2E Tests

1. **Run with visible browser**:
   ```bash
   uv run pytest tests/e2e/test_live_server.py --headed
   ```

2. **Add debug pauses in test**:
   ```python
   await page.pause()  # Opens Playwright inspector
   ```

3. **Screenshot on failure**:
   ```python
   await page.screenshot(path="debug.png")
   ```

4. **Console logs**:
   ```python
   page.on("console", lambda msg: print(f"Console: {msg.text}"))
   ```

## Configuration

- **Server URL**: `http://localhost:8000` (adjust in test files if needed)
- **Database**: Uses same database as dev server
- **Timeouts**: Default Playwright timeouts (30s for most actions)

## CI/CD Integration (TODO)

E2E tests will be configured to run in GitHub Actions with:
- Headless browser execution
- Test database isolation
- Artifact collection on failures
- Parallel execution across browsers