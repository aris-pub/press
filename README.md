# Scroll Press

A modern HTML-native preprint server for academic research documents. Built with
FastAPI, Scroll Press allows researchers to upload and share research manuscripts
written in web-native formats (HTML/CSS/JS).

## Features

- **HTML-native publishing**: Upload complete HTML documents with embedded CSS and JavaScript
- **Session-based authentication**: Secure user registration and login system
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
   # Edit .env with your database URL and port
   ```

3. **Install dependencies and setup**
   ```bash
   just init
   ```

4. **Start the development server**
   ```bash
   just dev
   ```

Visit `http://localhost:8000` to access Scroll Press.

## Development

### Project Structure

```
app/
├── auth/               # Session-based authentication
├── models/             # SQLAlchemy database models
├── routes/             # FastAPI route handlers
├── templates/          # Jinja2 templates with component macros
└── database.py         # Async database configuration

static/
├── css/               # Stylesheet
└── images/            # Static assets

tests/                 # Comprehensive test suite
```

### Architecture

- **Backend**: FastAPI with async/await patterns
- **Database**: PostgreSQL with SQLAlchemy 2.0 async
- **Authentication**: Session-based with in-memory storage
- **Frontend**: Jinja2 templates with HTMX for dynamic interactions
- **Testing**: pytest with asyncio support, parallel execution, and Playwright e2e tests

## Database Models

### User
- UUID primary keys
- Email verification and password hashing
- Display names and timestamps

### Scroll
- Academic manuscript storage with HTML content
- Draft/published status workflow
- Version tracking and unique scroll IDs
- Metadata (title, authors, abstract, keywords)

### Subject
- Academic discipline categorization
- Hierarchical organization for research areas

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
