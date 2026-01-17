# Database Documentation

## Overview

Scroll Press uses different databases for each environment to optimize for speed, isolation, and production fidelity.

## Environment Configuration

| Environment | Database | Purpose |
|-------------|----------|---------|
| **Local Development** | PostgreSQL (localhost) | Development work with persistent data |
| **Local Testing** | SQLite (in-memory) | Fast, isolated test execution |
| **CI Testing** | PostgreSQL (CI container) | Production-like testing environment |
| **Production** | Supabase PostgreSQL | Hosted production database |

### Setting Up Your Database URL

Configure your `DATABASE_URL` in `.env`:

```bash
# Local development (adjust username as needed)
DATABASE_URL=postgresql+asyncpg://leo.torres@localhost:5432/press

# Production (Supabase)
DATABASE_URL=postgresql+asyncpg://postgres.xyz:password@aws-0-region.pooler.supabase.com:6543/postgres
```

## Database Migrations

### Apply Migrations
```bash
just migrate
# or: uv run alembic upgrade head
```

### Create New Migration
```bash
just migration "description"
# or: uv run alembic revision --autogenerate -m "description"
```

### Reset Database with Fresh Seed Data
```bash
just reset-db
```

## Database Models

### User
- UUID primary keys
- Email verification status and password hashing
- Display names and timestamps

### Token
- Email verification and password reset tokens
- Hashed token storage for security
- Expiration timestamps (1 hour for password reset, 24 hours for email verification)
- One active token per user per type

### Scroll
- Academic manuscript storage with HTML content
- Draft/published status workflow
- Version tracking and unique scroll IDs
- Metadata (title, authors, abstract, keywords)

### Subject
- Academic discipline categorization
- Hierarchical organization for research areas

## Database Configuration Details

### ORM and Connection
- **ORM**: SQLAlchemy 2.0 async throughout codebase
- **Migrations**: Alembic for schema changes
- **Connection Pooling**: NullPool for Supabase compatibility (avoids pgbouncer prepared statement issues)
- **Time Zone**: All dates/times stored in UTC, frontend handles user timezone conversion

## Backup Strategy

### Current Setup (Bootstrap Phase)
- **Method**: Automated GitHub Actions backups
- **Schedule**: Daily at 2 AM UTC
- **Retention**: 30 days (last 7 backups kept)
- **Cost**: Free using GitHub Actions
- **Security**: Private artifacts, repository collaborators only

For detailed backup setup instructions, see [BACKUP_SETUP.md](BACKUP_SETUP.md).

### Future Migration
Plan to upgrade to **Supabase Pro Plan** ($25/month) for official backups once user base grows:
- 14-day automated backups
- Point-in-time recovery
- Professional support
- Integrated dashboard management
