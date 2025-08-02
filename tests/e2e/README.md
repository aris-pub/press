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

1. **`test_live_server.py`** - Tests against running dev server
   - Homepage loading and navigation
   - User registration flow
   - Basic UI interaction

2. **`test_critical_persistence.py`** - Critical scroll persistence tests
   - Registration → Upload → Public Access
   - Registration → Upload → Account Deletion → Public Access
   - Cross-browser compatibility

### Browser Support

- **Chromium**: Primary browser for all tests
- **Firefox**: Secondary browser for compatibility verification
- **Always headless**: Tests run in headless mode by default

## Test Categories

### High Priority (Critical Flows)
- [ ] Registration → Upload → Public Access
- [ ] Registration → Upload → Account Deletion → Public Access

### Medium Priority (Core Features)
- [ ] Upload form license selection
- [ ] Scroll viewing with modal interaction
- [ ] Search and discovery workflow
- [ ] Subject browsing and filtering

### Low Priority (Enhanced Features)
- [ ] Mobile responsive upload flow
- [ ] Dark mode toggle functionality
- [ ] Data export functionality

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