# Preview Press

A modern HTML-native preprint server for academic research documents. Built with
FastAPI, Preview Press allows researchers to upload and share research manuscripts
written in web-native formats (HTML/CSS/JS).

## Features

- **HTML-native publishing**: Upload complete HTML documents with embedded CSS and JavaScript
- **Session-based authentication**: Secure user registration and login system
- **Subject categorization**: Organize research by academic disciplines
- **Draft and publish workflow**: Save drafts and publish when ready
- **Preview cards**: Browse recent submissions with rich metadata
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

Visit `http://localhost:8000` to access Preview Press.

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
- **Testing**: pytest with asyncio support and parallel execution

## Database Models

### User
- UUID primary keys
- Email verification and password hashing
- Display names and timestamps

### Preview
- Academic manuscript storage with HTML content
- Draft/published status workflow
- Version tracking and unique preview IDs
- Metadata (title, authors, abstract, keywords)

### Subject
- Academic discipline categorization
- Hierarchical organization for research areas

## Contributing

1. **Run tests**: `just test`
2. **Check code quality**: `just lint`
3. **Follow existing patterns**: Session-based auth, macro components, async/await
4. **Write tests**: All new features should include test coverage

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Support

For issues and questions, please use the GitHub issue tracker.
