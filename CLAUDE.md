# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in
this repository.

## Project Overview

**Preview Press**, sometimes just **Press** is a modern HTML-native preprint server for
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
- **Preview**: Academic manuscripts with HTML content, versioning, draft/published status
- **Subject**: Academic categorization system
- **Relationships**: Users own previews, previews belong to subjects

### Authentication System
- Session-based authentication (not JWT) with 24-hour expiration
- In-memory session storage in `app/auth/session.py`

### Template Architecture
- Jinja2 with macro-based components (not includes)
- Component pattern: `{% from "components/form_input.html" import form_input %}`
- Use `xmlattr` filter for conditional HTML attributes
- HTMX for form submissions and dynamic interactions

### Database Configuration
- **Production/Development**: PostgreSQL with asyncpg
- **Testing**: SQLite in-memory with automatic cleanup
- **ORM**: SQLAlchemy 2.0 async throughout codebase
- **Migrations**: Alembic for schema changes

### Frontend Patterns
- HTMX-first approach for dynamic interactions
- CSS organization: Single `main.css` file (HTMX best practice)
- Typography: Source Sans 3 + Georgia serif for headers
- Component styling: Use `preview-` class prefix (not `paper-`)

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
