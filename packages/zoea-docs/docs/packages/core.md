# zoea-core

The backend API and CLI package for Zoea CoWorking Toolkit.

## Overview

`zoea-core` provides:

- **Django Backend**: REST API built with Django and django-ninja
- **CLI Tool**: Command-line interface built with Typer
- **Multi-tenant Architecture**: Organization-based resource isolation
- **LLM Integration**: Support for OpenAI, Gemini, and local models

## Installation

```bash
cd packages/zoea-core
uv sync
```

## Development

### Running the Development Server

```bash
# Django development server
uv run python manage.py runserver 0.0.0.0:8000

# ASGI server with uvicorn
uv run uvicorn zoea.asgi:app --reload --host 0.0.0.0 --port 8000
```

### Running Tests

```bash
uv run pytest
```

### Database Migrations

```bash
uv run python manage.py migrate
```

## CLI Usage

The `zoea` CLI provides commands for managing projects, workspaces, and documents:

```bash
# List projects
zoea projects list

# List workspaces
zoea workspaces list

# List documents
zoea documents list
```

Run `zoea --help` for all available commands.

## API Documentation

The API is documented with OpenAPI/Swagger. Access the docs at:

- `/api/docs` - Interactive API documentation

## Module Structure

```
zoea-core/
├── zoea/                 # Django settings & configuration
├── accounts/             # User & organization management
├── chat/                 # Chat conversations & agents
├── documents/            # Document models & storage
├── workflows/            # Workflow engine
├── cli/                  # Typer CLI commands
└── ...
```
