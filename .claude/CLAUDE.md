# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in
this repository.

## Project Overview

**Scroll Press** is a modern HTML-native preprint server for
academic research documents. Built with FastAPI, it allows researchers to upload and
share research manuscripts written in web-native formats (HTML/CSS/JS).

## Development Commands

### Using Just (REQUIRED)
**CRITICAL: Always use justfile commands for development tasks. Do NOT use direct commands unless absolutely necessary.**

The project includes a `justfile` with common development tasks:

```bash
# Setup project from scratch
just init

# Run development server (checks if already running)
just dev

# Run tests - ALWAYS USE THIS, NOT `uv run pytest` or `python -m pytest`
just test
just test-cov  # with coverage

# Database management
just migrate                    # Apply migrations
just migration "description"    # Create new migration
just seed                      # Add sample data
just reset-db                  # Fresh database with seed data

# Code quality
just lint      # Format and check code
just check     # Run both lint and tests
```

### Direct Commands (Avoid - Use Just Instead)
```bash
# Install dependencies
uv sync

# Run development server
uvicorn main:app --reload --port ${PORT:-8000}

# Database setup/management
alembic upgrade head                           # Apply migrations
alembic revision --autogenerate -m "message"  # Create migration
python app/seed.py                            # Seed database with sample data

# Code quality
ruff check . && ruff format .
```

### Environment Setup
1. Copy `.env.example` to `.env` and configure `DATABASE_URL` and `PORT`
2. Set up PostgreSQL database
3. Run `just init` for complete setup

## Architecture

### Database Models
- **User**: UUID-based with email verification, bcrypt password hashing
- **Scroll**: Academic manuscripts with HTML content, versioning, draft/published status
- **Subject**: Academic categorization system
- **Relationships**: Users own scrolls, scrolls belong to subjects

### Authentication System
- Session-based authentication (not JWT) with 24-hour expiration
- In-memory session storage in `app/auth/session.py`

### Template Architecture
- Jinja2 with macro-based components (not includes)
- Component pattern: `{% from "components/form_input.html" import form_input %}`
- Use `xmlattr` filter for conditional HTML attributes
- HTMX for form submissions and dynamic interactions

### Database Configuration

#### Environment-Specific Databases
- **Local Development**: PostgreSQL (`postgresql+asyncpg://leo.torres@localhost:5432/press`)
- **Local Testing**: SQLite in-memory (`sqlite+aiosqlite:///:memory:`) with automatic cleanup
- **CI Testing**: PostgreSQL (`postgresql+asyncpg://postgres:password@localhost:5432/press`)
- **Production**: Supabase PostgreSQL (`postgresql+asyncpg://postgres.peaxwmgmmjxtvffpzyrn:...@aws-0-eu-central-1.pooler.supabase.com:6543/postgres`)

#### Database Settings
- **ORM**: SQLAlchemy 2.0 async throughout codebase
- **Migrations**: Alembic for schema changes
- **Connection Pooling**: NullPool for Supabase compatibility (avoids pgbouncer prepared statement issues)
- **Time Zone**: All dates/times stored in UTC, frontend handles user timezone conversion

### Frontend Patterns
- HTMX-first approach for dynamic interactions
- CSS organization: Single `main.css` file (HTMX best practice)
- Typography: Source Sans 3 + Georgia serif for headers
- Component styling: Use `scroll-` class prefix (not `paper-`)
- Icons: All icons use Lucide Icons (https://lucide.dev) - inline SVG with `stroke="currentColor"` for theming

### Code Organization
```
app/
├── auth/           # Session management and authentication
├── models/         # SQLAlchemy database models
├── routes/         # FastAPI route handlers
├── templates/      # Jinja2 templates with component macros
└── database.py     # Async database configuration
```

## Important Patterns

### Form Handling
- Use macro components: `form_input()`, `button()`, `auth_form()`
- HTMX forms target containers with `hx-swap="innerHTML"`
- 422 status codes for validation errors

### Database Operations
- Always use async/await with database operations
- Use `get_current_user_from_session()` for auth checks
- Cross-platform compatibility with custom TypeDecorators

### Testing
- pytest-asyncio with in-memory SQLite
- Test fixtures in `tests/conftest.py`
- Database isolation per test

### Security: User HTML Isolation & CSP
- User HTML served in iframe at `/scroll/{url_hash}/paper` endpoint
- CSP includes `'unsafe-inline'` and `'unsafe-eval'` to support interactive academic libraries (Bokeh, Plotly, Observable)
- Security model: Treat entire iframe content as untrusted; rely on upload validation (HTMLValidator) as primary XSS defense
- Defense-in-depth: Cookie HttpOnly flags, same-origin policy, CSP resource restrictions
- Trade-off rationale: `'unsafe-eval'` does not meaningfully increase risk vs `'unsafe-inline'` when serving fully untrusted user HTML in isolated iframe

## Dependencies
- FastAPI + Uvicorn (web framework)
- SQLAlchemy + asyncpg (database)
- Jinja2 (templating)
- HTMX (frontend interactivity)
- pytest + httpx (testing)
- Alembic (migrations)
- uv (package management)

## Database Time Handling
- All dates and times in the DB are stored in UTC time zone, the client/frontend is responsible for converting to the user's browser's timezone

## Puppeteer and Screenshot Handling
- Whenever taking screenshots with Puppeteer, specify width/height or the MCP will hang

## Playwright E2E Testing
- **CRITICAL**: Do NOT use session-scoped Playwright fixtures (`page`, `browser`, `browser_context`) in e2e tests
- Session fixtures cause deadlocks with pytest-asyncio due to event loop conflicts
- **SOLUTION**: Use `async with async_playwright()` directly in test functions:
  ```python
  async with async_playwright() as p:
      browser = await p.chromium.launch(headless=True)
      page = await browser.new_page()
      # ... test code ...
      await browser.close()
  ```
- This pattern avoids event loop conflicts and ensures tests don't hang

## API Endpoints

### GDPR Data Export
- **Endpoint**: `GET /user/export-data`
- **Purpose**: GDPR Article 20 compliance (right to data portability)
- **Auth**: Requires session authentication
- **Response**: JSON with user profile, scrolls, and sessions
- **Implementation**: `app/routes/auth.py:810-881`
- **Tests**: `tests/test_data_export.py`

## Performance & Caching

### Static File Caching
- Static files cached for 1 year with `immutable` flag
- SEO files (robots.txt, sitemap.xml) cached for 1 day
- Implemented via `StaticFilesCacheMiddleware` in `app/middleware.py`
- Middleware must be added first in stack (runs last) to set headers after response

### Scaling Limitation
- **CRITICAL**: Application limited to 1 machine in `fly.toml`
- CSRF tokens (`app/auth/csrf.py`) use in-memory module-level dictionary
- Rate limiting (`app/middleware.py`) uses in-memory module-level counters
- Must migrate to database/Redis before scaling horizontally
- Current capacity: 100 concurrent requests per machine (hard limit)

## Monitoring & Error Tracking

### Sentry Configuration
- Release tracking via `GIT_COMMIT` build arg in `fly.toml`
- Configured in `Dockerfile` with ARG/ENV pattern
- Fly.io replaces "auto" with actual git commit hash during build
- See `SENTRY_SETUP.md` for complete configuration and alert setup

## Code Generation Guidelines
- You MUST NEVER use emoji for any reason under any circumstance

## Communication Guidelines
- Never say 'you are absolutely right' or anything along those lines
- Do not be sycophantic, a yes-man, or attempt to validate everything said

## Testing Best Practices
- **CRITICAL: ALWAYS use `just test` for running tests** - NEVER use `uv run pytest` or `python -m pytest` directly
- For all tests: `just test`
- For tests with coverage: `just test-cov`
- For specific test files, you may use: `uv run pytest tests/test_file.py` (only when targeting a single file)
- Never try to fix a test by adding a longer wait without making absolutely sure beyond doubt that a longer wait is strictly necessary

## Documentation

For detailed information, see:
- **Database**: `docs/DATABASE.md` - Database configuration, migrations, models, backups
- **Authentication**: `docs/AUTHENTICATION.md` - Session management, email verification, security
- **GDPR**: `docs/GDPR.md` - Data export and compliance features
- **Testing**: `docs/TESTING.md` - Unit, integration, and E2E testing guide
- **Deployment**: `docs/DEPLOYMENT.md` - Production deployment instructions
- **Backup Setup**: `docs/BACKUP_SETUP.md` - Database backup configuration
- **Sentry**: `docs/SENTRY_SETUP.md` - Error tracking and monitoring setup