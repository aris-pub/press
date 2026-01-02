# Scroll Press

A modern HTML-native preprint server for academic research documents. Built with
FastAPI, Scroll Press allows researchers to upload and share research manuscripts
written in web-native formats (HTML/CSS/JS).

## Features

- **HTML-native publishing**: Upload complete HTML documents with embedded CSS and JavaScript
- **Session-based authentication**: Secure user registration and login system with email verification
- **Email verification**: Token-based email verification with password reset functionality
- **Subject categorization**: Organize research by academic disciplines
- **Draft and publish workflow**: Save drafts and publish when ready
- **Scroll cards**: Browse recent submissions with rich metadata
- **Responsive design**: Clean, academic-focused UI with HTMX interactions

## Quick Start

### Prerequisites

- Python 3.11+
- PostgreSQL database
- [uv](https://docs.astral.sh/uv/) package manager
- `just` to run common commands

### Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd press
   ```

2. **Set up environment**
   ```bash
   cp .env.example .env
   # Edit .env with your database URL, port, and email service credentials
   ```

   Required environment variables:
   - `DATABASE_URL`: PostgreSQL connection string
   - `PORT`: Server port (default: 7999)
   - `RESEND_API_KEY`: API key for Resend email service (for email verification)
   - `FROM_EMAIL`: Email address to send from (default: noreply@updates.aris.pub)
   - `BASE_URL`: Base URL for email links (defaults to https://127.0.0.1:{PORT})

3. **Install dependencies and setup**
   ```bash
   just init
   ```

4. **Start the development server**
   ```bash
   just dev
   ```

Visit `https://localhost:7999` to access Scroll Press (HTTPS with self-signed certificate).

## Development

### Project Structure

```
app/
├── auth/               # Session-based authentication and token management
│   ├── session.py      # Session handling
│   └── tokens.py       # Email verification and password reset tokens
├── emails/             # Email service integration
│   ├── service.py      # Resend email service
│   └── templates.py    # Email HTML templates
├── models/             # SQLAlchemy database models
│   ├── user.py         # User model with email verification
│   ├── token.py        # Token model for verification/reset
│   ├── scroll.py       # Research manuscript model
│   └── subject.py      # Academic subject categorization
├── routes/             # FastAPI route handlers
├── templates/          # Jinja2 templates with component macros
│   └── auth/           # Authentication templates (login, register, verify, reset)
└── database.py         # Async database configuration

static/
├── css/               # Stylesheet
└── images/            # Static assets

tests/                 # Comprehensive test suite
```

### Architecture

- **Backend**: FastAPI with async/await patterns
- **Database**: PostgreSQL with SQLAlchemy 2.0 async
- **Authentication**: Session-based with in-memory storage and token-based email verification
- **Email Service**: Resend API for transactional emails (verification, password reset)
- **Frontend**: Jinja2 templates with HTMX for dynamic interactions
- **Security**: HTTPS-only development with self-signed certificates
- **Testing**: pytest with asyncio support, parallel execution, and Playwright e2e tests

## Database Setup

Scroll Press uses different databases for each environment:

| Environment | Database | Purpose |
|-------------|----------|---------|
| **Local Development** | PostgreSQL (localhost) | Development work with persistent data |
| **Local Testing** | SQLite (in-memory) | Fast, isolated test execution |
| **CI Testing** | PostgreSQL (CI container) | Production-like testing environment |
| **Production** | Supabase PostgreSQL | Hosted production database |

### Environment Configuration

Set your `DATABASE_URL` in `.env`:

```bash
# Local development (adjust username as needed)
DATABASE_URL=postgresql+asyncpg://leo.torres@localhost:5432/press

# Production (Supabase)
DATABASE_URL=postgresql+asyncpg://postgres.xyz:password@aws-0-region.pooler.supabase.com:6543/postgres
```

### Database Migrations

```bash
# Apply migrations
just migrate
# or: uv run alembic upgrade head

# Create new migration
just migration "description"
# or: uv run alembic revision --autogenerate -m "description"

# Reset database with fresh seed data
just reset-db
```

## Backup Strategy

### Current Setup (Bootstrap Phase)
- **Method**: Automated GitHub Actions backups
- **Schedule**: Daily at 2 AM UTC
- **Retention**: 30 days (last 7 backups kept)
- **Cost**: Free using GitHub Actions
- **Security**: Private artifacts, repository collaborators only

### Setup Instructions
1. Add required secrets to GitHub repository (see `BACKUP_SETUP.md`)
2. Backups run automatically via `.github/workflows/database-backup.yml`
3. Manual backups can be triggered from GitHub Actions tab

### Future Migration
Plan to upgrade to **Supabase Pro Plan** ($25/month) for official backups once user base grows:
- 14-day automated backups
- Point-in-time recovery
- Professional support
- Integrated dashboard management

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

## Email Verification Flow

1. **Registration**: User registers and receives verification email via Resend
2. **Verification**: User clicks email link with time-limited token
3. **Access Control**: Unverified users can view dashboard but cannot upload or export data
4. **Password Reset**: Secure token-based password reset with 1-hour expiration

## Testing

Scroll Press includes comprehensive testing with both unit/integration tests and end-to-end browser tests.

### Unit and Integration Tests
```bash
# Run all tests
just test

# Run with coverage
just test-cov

# Run specific test file
uv run pytest tests/test_main.py -v
```

### End-to-End Tests
E2E tests use Playwright to verify complete user journeys in real browsers.

```bash
# Install e2e dependencies (one time)
uv run playwright install chromium firefox

# Start development server
just dev

# Run e2e tests (in another terminal)
just test-e2e

# Or run directly
./scripts/run-e2e-tests.sh
```

#### Critical E2E Test Scenarios
- **Registration → Upload → Public Access**: Verifies scrolls remain publicly accessible
- **Registration → Upload → Account Deletion → Public Access**: Verifies scroll persistence after user deletion
- **License Selection**: Tests CC BY 4.0 and All Rights Reserved license workflows
- **Mobile Responsive**: Validates mobile upload and interaction flows
- **Search & Discovery**: Tests content search and subject browsing

See [E2E Testing Documentation](tests/e2e/README.md) for detailed information.

## Contributing

1. **Run all checks**: `just check` (includes lint, unit tests, and e2e tests)
2. **Run tests only**: `just test`
3. **Run e2e tests only**: `just test-e2e`
4. **Follow existing patterns**: Session-based auth, macro components, async/await
4. **Write tests**: All new features should include test coverage

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Support

For issues and questions, please use the GitHub issue tracker.
