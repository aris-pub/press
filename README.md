# Scroll Press

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Code style: ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![CI](https://github.com/aris-pub/press/actions/workflows/ci.yml/badge.svg)](https://github.com/aris-pub/press/actions/workflows/ci.yml)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](http://makeapullrequest.com)

A modern HTML-native preprint server for academic research documents. Built with
FastAPI, Scroll Press accepts research from any authoring tool that produces HTML—Typst,
Quarto, MyST, Jupyter, or handwritten HTML. Format freedom, instant publication,
permanent URLs.

**Governance**: Press is fully community-owned—open source, community contributions
accepted, roadmap driven by community needs, forever free. Supported by community
donations and academic grants.

## Features

- **HTML-native publishing**: Upload complete HTML documents with embedded CSS and JavaScript
- **Session-based authentication**: Secure user registration and login system with email verification
- **Email verification**: Token-based email verification with password reset functionality
- **GDPR compliance**: Data export endpoint for user data portability (Article 20)
- **Subject categorization**: Organize research by academic disciplines
- **Draft and publish workflow**: Save drafts and publish when ready
- **Scroll cards**: Browse recent submissions with rich metadata
- **Responsive design**: Clean, academic-focused UI with HTMX interactions
- **Performance optimized**: Static file caching with CDN-ready headers

## Quick Start

### Prerequisites

- Python 3.11+
- PostgreSQL database
- [uv](https://docs.astral.sh/uv/) package manager
- `just` to run common commands
- `pandoc` for building documentation (install: `brew install pandoc` on macOS)

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

docs/                  # Documentation source (markdown)
├── quick-start.md     # Quick start guide (source)
├── faq.md             # FAQ (source)
├── docs-meta-template.html  # Jinja wrapper template
└── build.sh           # Build script (markdown → HTML templates)

tests/                 # Comprehensive test suite
```

### Documentation Build Pipeline

Documentation pages are written in Markdown and built into Jinja2 templates at build time:

**Source files** (edit these):
- `docs/quick-start.md` - Quick start guide
- `docs/faq.md` - Frequently asked questions
- `docs/docs-meta-template.html` - Wrapper template with Jinja blocks

**Generated files** (do not edit directly):
- `app/templates/docs/quick-start.html` - Built from quick-start.md
- `app/templates/docs/faq.html` - Built from faq.md

**When to build**:
```bash
just build
```

Run this command whenever you:
- Edit any `.md` file in `docs/`
- Edit `docs-meta-template.html`
- After pulling changes that modify documentation source

The build process uses `pandoc` to convert Markdown to HTML fragments, then injects them into the Jinja template wrapper. At runtime, these are served as normal Jinja templates with full access to base template styling and navigation.

### Architecture

- **Backend**: FastAPI with async/await patterns
- **Database**: PostgreSQL with SQLAlchemy 2.0 async
- **Authentication**: Session-based with in-memory storage and token-based email verification
- **Email Service**: Resend API for transactional emails (verification, password reset)
- **Frontend**: Jinja2 templates with HTMX for dynamic interactions
- **Security**: HTTPS-only development with self-signed certificates
- **Testing**: pytest with asyncio support, parallel execution, and Playwright e2e tests

## Documentation

- [Database Setup & Models](docs/DATABASE.md) - Database configuration, migrations, and data models
- [Authentication](docs/AUTHENTICATION.md) - Session management, email verification, and security
- [GDPR Compliance](docs/GDPR.md) - Data export and privacy features
- [Testing](docs/TESTING.md) - Unit, integration, and E2E testing guide
- [Deployment](docs/DEPLOYMENT.md) - Production deployment instructions
- [Backup Setup](docs/BACKUP_SETUP.md) - Database backup configuration

## Contributing

1. **Run all checks**: `just check` (includes lint, unit tests, and e2e tests)
2. **Follow existing patterns**: Session-based auth, macro components, async/await
3. **Write tests**: All new features should include test coverage
4. **Documentation changes**: Edit `.md` files in `docs/`, then run `just build`
5. **Read the docs**: See [Testing Guide](docs/TESTING.md) for testing best practices

Contributions are welcome! Please open an issue to discuss major changes before submitting a PR.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Support

For issues and questions, please use the GitHub issue tracker.
