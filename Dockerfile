FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Accept build arg for git commit (for Sentry release tracking)
ARG GIT_COMMIT=dev
ENV GIT_COMMIT=$GIT_COMMIT

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    libmagic1 \
    libmagic-dev \
    && rm -rf /var/lib/apt/lists/*

# Install uv
RUN pip install uv

# Copy dependency files first (for better caching)
COPY pyproject.toml ./
COPY uv.lock ./

# Install Python dependencies
RUN uv sync --frozen --no-dev

# Copy application code
COPY . .

# Create non-root user for security
RUN groupadd -r appuser && useradd -r -g appuser appuser -m
RUN chown -R appuser:appuser /app
RUN mkdir -p /home/appuser/.cache && chown -R appuser:appuser /home/appuser/.cache
USER appuser

# Expose port
EXPOSE 8000

# Start application
CMD ["uv", "run", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]