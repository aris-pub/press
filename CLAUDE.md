# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in
this repository.

## Project Overview

**Scroll Press** is a modern HTML-native preprint server for
academic research documents. Built with FastAPI, it allows researchers to upload and
share research manuscripts written in web-native formats (HTML/CSS/JS).

## Development Commands

### Using Just (Recommended)
The project includes a `justfile` with common development tasks:

```bash
# Setup project from scratch
just init

# Run development server (checks if already running)
just dev

# Run tests
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

### Direct Commands
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

## Code Generation Guidelines
- You MUST NEVER use emoji for any reason under any circumstance

## Communication Guidelines
- Never say 'you are absolutely right' or anything along those lines
- Do not be sycophantic, a yes-man, or attempt to validate everything said

## Testing Best Practices
- Never try to fix a test by adding a longer wait without making absolutely sure beyond doubt that a longer wait is strictly necessary

## Database Backup Strategy

### Production Backups
- **Current**: GitHub Actions automated backups (daily at 2 AM UTC)
- **Storage**: GitHub Actions artifacts (30-day retention, last 7 backups kept)
- **Security**: Private artifacts, only repository collaborators can access
- **Cost**: Free using GitHub Actions minutes
- **Future**: Upgrade to Supabase Pro Plan ($25/month) for official backups when user base grows

### Backup Configuration
- **Workflow**: `.github/workflows/database-backup.yml`
- **Setup**: Repository secrets required (see `BACKUP_SETUP.md`)
- **Verification**: Each backup is compressed and integrity-tested
- **Cleanup**: Automatic removal of old backups to manage storage
- **Manual Trigger**: Backups can be triggered manually from GitHub Actions

### Restore Process
1. Download backup artifact from GitHub Actions
2. Extract compressed SQL file (`gunzip backup.sql.gz`)
3. Restore to target database (`psql target_db < backup.sql`)
4. Update environment configuration if switching databases