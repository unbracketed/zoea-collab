#!/bin/bash
# Docker entrypoint script for Zoea core backend
# Runs migrations and initializes local user on first start

set -e

# Marker file to track initialization
INIT_MARKER="/app/data/.initialized"

echo "=== Zoea Core Backend Startup ==="

# Run database migrations
echo "Running database migrations..."
uv run python manage.py migrate --noinput

# Check if initialization has been done
if [ ! -f "$INIT_MARKER" ]; then
    echo "First run detected - initializing local user and demo project..."

    # Run initialize_local_user with --use-existing in case migrations created users
    # Use --demo-docs to load sample documents for getting started experience
    # Use --force to skip interactive prompts in Docker environment
    # Demo docs are mounted at /app/demo-docs by docker-compose
    uv run python manage.py initialize_local_user \
        --use-existing \
        --force \
        --demo-docs \
        --demo-docs-path /app/demo-docs \
        || echo "Warning: initialize_local_user failed (may be ok if already exists)"

    # Create marker file to prevent re-initialization
    touch "$INIT_MARKER"
    echo "Initialization complete!"
else
    echo "Already initialized - skipping user setup"
fi

echo "=== Starting application ==="

# Execute the main command (passed as arguments)
exec "$@"
