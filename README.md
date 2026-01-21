# Zoea Collab

**Agent Cowork Toolkit** - An AI-powered productivity suite for research, workflow collaboration, and knowledge management.

## Overview

Zoea Collab combines AI agents with knowledge bases for research, business processes, and workflow management. Flow between chat, documents, and canvas to take control.

## Monorepo Structure

| Package | Type | Description |
|---------|------|-------------|
| `zoea-core` | Python | Backend API (Django + django-ninja) + CLI (Typer) |
| `zoea-web-components` | npm | Reusable React AI/chat components |
| `zoea-studio` | npm | Productivity suite frontend |
| `zoea-docs` | MkDocs | Documentation site |
| `zoea-vm` | Python | VM management (placeholder) |

## Quick Start

```bash
# Install tools
mise install

# Install all dependencies
mise run install

# Run migrations and initialize
cd packages/zoea-core
uv run python manage.py migrate
uv run python manage.py initialize_local_user

# Start development servers
mise run dev
```

Open http://localhost:5173 and login with `admin` / `admin`.

## Technology Stack

**Backend:** Django 5.1+, django-ninja APIs, django-organizations, OpenAI/Gemini, Python 3.12 via `uv`

**Frontend:** Vite + React 19, Zustand, React Router, Tailwind CSS, Node.js 24 via `mise`

**Tools:** `mise` for task orchestration, `pnpm` for JS packages, `turborepo` for builds

## Development

```bash
mise run dev              # Start all dev servers
mise run test             # Run all tests
mise run build            # Build all packages
mise run lint             # Lint all code
mise run docs             # Serve documentation
```

## Environment Variables

Copy `.env.example` to `.env` and configure:
- `OPENAI_API_KEY` - Required for AI agent chat
- `GEMINI_API_KEY` - Optional, for document search/RAG
- `SECRET_KEY` - Django secret key

## Documentation

Full documentation at [zoea-collab docs](https://unbracketed.github.io/zoea-collab/) or run locally:

```bash
mise run docs
```

## License

MIT
