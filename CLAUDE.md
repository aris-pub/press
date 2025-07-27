# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in
this repository.

## Project Overview

**Preview Press**, sometimes just **Press** is a modern HTML-native preprint server for
academic research documents. Built with FastAPI, it allows researchers to upload and
share research manuscripts written in web-native formats (HTML/CSS/JS).

## Development Commands

### Essential Commands
```bash
# Install dependencies
uv sync

# Run development server
uvicorn main:app --reload

# Run tests
pytest

# Database setup/management
alembic upgrade head                           # Apply migrations
alembic revision --autogenerate -m "message"  # Create migration
python app/seed.py                            # Seed database with sample data

# Code quality
ruff check .
ruff format .
```

### Environment Setup
1. Copy `.env.example` to `.env` and configure `DATABASE_URL`
2. Set up PostgreSQL database
3. Install dependencies with `uv sync`
4. Run migrations and seed data

## Architecture

### Database Models
- **User**: UUID-based with email verification, bcrypt password hashing
- **Preview**: Academic manuscripts with HTML content, versioning, draft/published status
- **Subject**: Academic categorization system
- **Relationships**: Users own previews, previews belong to subjects

### Authentication System
- Session-based authentication (not JWT) with 24-hour expiration
- In-memory session storage in `app/auth/session.py`
- Function naming: `_get_user_id_from_session_id()` for internal helpers

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

### Security
- POST-only for logout routes (CSRF protection)
- Required field validation with red asterisks
- Session-based auth over JWT for this use case

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
