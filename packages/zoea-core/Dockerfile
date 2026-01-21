# Backend Dockerfile for Zoea Collab: Agent Cowork Toolkit
# Uses uv for fast, reliable Python package management

FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy all application code (needed for editable install)
COPY . .

# Create directory for SQLite database and media files
RUN mkdir -p /app/data /app/media

# Install dependencies
RUN uv sync --frozen --no-dev

# Environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV UV_PROJECT_ENVIRONMENT=/app/.venv
ENV PATH="/app/.venv/bin:$PATH"

# Copy and set up entrypoint script
COPY docker-entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

# Expose port
EXPOSE 8000

# Use entrypoint for initialization, CMD for main process
ENTRYPOINT ["docker-entrypoint.sh"]
CMD ["uv", "run", "gunicorn", "zoea.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "2"]
