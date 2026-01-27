# Getting Started with Zoea Collab

Welcome to Zoea Collab! This guide will help you set up and run the application on your local machine.

## Quick Start with Docker

The fastest way to get started is with Docker:

```bash
# Clone the repository
git clone https://github.com/unbracketed/zoea-collab.git
cd zoea-collab

# Copy environment file and add your API key
cp .env.example .env
# Edit .env and set OPENAI_API_KEY=your-key-here

# Start the application
docker-compose up
```

Once running, open **http://localhost:5173** in your browser.

**Default Login:**

- Username: `admin`
- Password: `admin`

The first startup automatically creates a demo user with sample documents to explore.

---

## Prerequisites (Manual Installation)

For development without Docker, ensure you have the following:

- **Python 3.12+** (managed via mise)
- **Node.js 22+** (managed via mise)
- **mise** - Environment variables, tool versions, and task management
- **OpenAI API key** - Required for AI agent functionality
- **Gemini API key** - Optional, for file search features

## Manual Setup Overview

Setting up Zoea Studio involves five main steps:

1. **[Installation](installation.md)** - Install mise, clone the repository, and install dependencies
2. **[Development Setup](development.md)** - Configure environment variables and learn development commands
3. **[User Initialization](initialization.md)** - Set up your first user, organization, and workspace
4. **Running the Application** - Start the backend and frontend servers
5. **Verification** - Confirm everything is working correctly

## Manual Quick Start

If you prefer to run without Docker, here's the condensed version:

```bash
# 1. Install mise (if not already installed)
curl https://mise.run | sh

# 2. Clone and navigate to the project
cd zoea-collab

# 3. Install tools and dependencies
mise install
mise run install

# 4. Configure environment
cp .env.example .env
# Edit .env and add your OPENAI_API_KEY

# 5. Run migrations and initialize
cd packages/zoea-core
uv run python manage.py migrate
uv run python manage.py initialize_local_user --demo-docs

# 6. Start the servers (in two separate terminals)
# Terminal 1:
mise run dev-backend

# Terminal 2:
mise run dev-frontend
```

Open `http://localhost:5173` in your browser and start chatting!

## Detailed Guides

For more detailed information, follow these guides in order:

### 1. Installation Guide

Learn how to install mise, set up the project, and install all dependencies.

[:octicons-arrow-right-24: Go to Installation Guide](installation.md)

### 2. Development Setup

Configure your environment variables, understand the project structure, and learn the development workflow.

[:octicons-arrow-right-24: Go to Development Setup](development.md)

### 3. Local User Initialization

Create your first user account, organization, project, and workspace using the management command.

[:octicons-arrow-right-24: Go to Initialization Guide](initialization.md)

## What's Next?

Once you have Zoea Collab running locally:

- Explore the [Architecture](../architecture/overview.md) to understand the system design
- Learn about [Multi-Tenant Patterns](../architecture/multi-tenant.md) for building features
- Review [Testing Guidelines](../development/testing.md) before making changes
- Check out the [API Reference](../development/api-reference.md) for available endpoints

## Getting Help

If you run into issues:

1. Check the [Troubleshooting](#troubleshooting) section below
2. Review the detailed guides linked above
3. Search or create an issue on [GitHub](https://github.com/unbracketed/zoea-collab/issues)

## Troubleshooting

### Backend won't start

- Ensure `.env` file exists with valid `OPENAI_API_KEY`
- Run `mise run install` to ensure dependencies are installed
- Check that port 8000 (or your configured `ZOEA_CORE_BACKEND_PORT`) is not already in use
- **Port Conflict**: If port 8000 is taken, edit `.env` and change `ZOEA_CORE_BACKEND_PORT=8001`

### Frontend won't connect to backend

- Ensure backend is running on the configured port (default: 8000)
- Check browser console for CORS errors
- Verify both services are using the same port configuration from `.env`
- **Port Conflict**: If port 5173 is taken, edit `.env` and change `ZOEA_FRONTEND_PORT=5174`
- The API base URL is automatically configured based on `ZOEA_CORE_BACKEND_PORT` in `.env`

### Tests failing

- Ensure all dependencies are installed: `mise run install`
- For backend tests: `cd packages/zoea-core && uv run pytest`
- For E2E tests: `mise run test-e2e`

### Migration errors

- Ensure you're in the backend directory: `cd packages/zoea-core`
- Try running migrations again: `uv run python manage.py migrate`
- If issues persist, delete `db.sqlite3` and run migrations again (development only)
