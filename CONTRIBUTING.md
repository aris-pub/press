# Contributing to Scroll Press

Thank you for considering contributing to Scroll Press! This document provides guidelines for contributing to the project.

## Code of Conduct

Scroll Press is a community-owned project. We expect all contributors to:
- Be respectful and constructive in discussions
- Focus on what's best for the community
- Welcome newcomers and help them get started

## Getting Started

### Prerequisites

- Python 3.11+
- PostgreSQL database
- [uv](https://docs.astral.sh/uv/) package manager
- `just` command runner
- `pandoc` for building documentation

### Initial Setup

1. **Fork and clone the repository**
   ```bash
   git clone https://github.com/YOUR_USERNAME/press.git
   cd press
   ```

2. **Set up environment**
   ```bash
   cp .env.example .env
   # Edit .env with your database URL, port, and email credentials
   ```

3. **Initialize project (REQUIRED)**
   ```bash
   just init
   ```

   This command is essential - it installs dependencies, builds docs, runs migrations, seeds data, and installs git hooks.

4. **Start development server**
   ```bash
   just dev
   ```

   Visit `https://localhost:7999` (HTTPS with self-signed certificate)

## Development Workflow

### Making Changes

1. **Create a feature branch**
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make your changes**
   - Follow existing code patterns
   - Keep changes focused and minimal
   - Avoid over-engineering

3. **Run tests and linting**
   ```bash
   just check  # Runs linting and all tests
   ```

   The pre-commit hook will automatically lint your code before commits.

### Code Style

- **Linter**: ruff (automatically enforced via pre-commit hook)
- **Format**: Run `just lint` to format code
- **Comments**: Only add comments that explain *why*, not *what*
- **Simplicity**: Prefer simple solutions over abstractions

### Testing

All changes should include test coverage:

- **Unit tests**: Test individual functions and components
- **Integration tests**: Test database interactions
- **E2E tests**: Test complete user workflows with Playwright

See [docs/TESTING.md](docs/TESTING.md) for detailed testing guide.

```bash
# Run all tests
just test

# Run specific test file
uv run pytest tests/test_file.py -v

# Run with coverage
uv run pytest --cov=app --cov-report=html
```

### Documentation

- **User-facing docs**: Edit markdown files in `docs/` directory
- **Build docs**: Run `just build` after editing `.md` files
- **Code docs**: Add docstrings for non-obvious functions
- **README**: Keep README focused on quick start

## Submitting Changes

### Pull Request Process

1. **Ensure all checks pass**
   ```bash
   just check  # Linting + tests
   ```

2. **Commit your changes**
   ```bash
   git add .
   git commit -m "Brief description of changes"
   ```

   The pre-commit hook will run linting automatically.

3. **Push to your fork**
   ```bash
   git push origin feature/your-feature-name
   ```

4. **Open a Pull Request**
   - Use a clear, descriptive title
   - Describe what changed and why
   - Reference any related issues
   - Ensure CI passes

### PR Guidelines

- **Keep PRs focused**: One feature or bug fix per PR
- **Write clear commit messages**: Describe *what* and *why*
- **Respond to feedback**: Address review comments promptly
- **Be patient**: Maintainers review PRs as time allows

## Project Structure

```
app/
├── auth/           # Session management and authentication
├── models/         # SQLAlchemy database models
├── routes/         # FastAPI route handlers
├── templates/      # Jinja2 templates with component macros
└── database.py     # Async database configuration

static/
├── css/           # Stylesheet
└── images/        # Static assets

docs/              # Documentation source (markdown)
tests/             # Comprehensive test suite
```

## Development Resources

- [Database Setup](docs/DATABASE.md) - Database models and migrations
- [Authentication](docs/AUTHENTICATION.md) - Session and email verification
- [Testing Guide](docs/TESTING.md) - Unit, integration, and E2E testing
- [Deployment](docs/DEPLOYMENT.md) - Production deployment guide

## Common Commands

```bash
just init          # Complete project setup
just dev           # Start development server
just dev attach    # Start server in foreground
just stop          # Stop development server
just test          # Run all tests
just lint          # Format and check code
just check         # Run linting and tests
just migrate       # Apply database migrations
just seed          # Seed database with sample data
just reset-db      # Fresh database with seed data
just build         # Build documentation templates
```

## Getting Help

- **Issues**: Check existing issues or open a new one
- **Questions**: Use GitHub Discussions
- **Bugs**: Include steps to reproduce and expected behavior

## Recognition

All contributors will be recognized in release notes and project documentation.

## License

By contributing to Scroll Press, you agree that your contributions will be licensed under the MIT License.
