FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Accept build arg for git commit (for Sentry release tracking)
ARG GIT_COMMIT=dev
ENV GIT_COMMIT=$GIT_COMMIT

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    git \
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

# Fetch brand assets. The brand submodule is not preserved in the build context
# (.git is excluded via .dockerignore), so we clone the public brand repo directly.
# This guarantees /brand/* assets are present regardless of submodule init state.
RUN if [ ! -d brand ] || [ -z "$(ls -A brand 2>/dev/null)" ]; then \
        rm -rf brand && \
        git clone --depth 1 https://github.com/leotrs/brand.git brand && \
        rm -rf brand/.git; \
    fi

# Create non-root user for security
RUN groupadd -r appuser && useradd -r -g appuser appuser -m
RUN chown -R appuser:appuser /app /root/.cache
RUN mkdir -p /home/appuser/.cache && chown -R appuser:appuser /home/appuser/.cache
USER appuser

# Expose port
EXPOSE 8000

# Start application
CMD ["uv", "run", "--frozen", "--no-dev", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]