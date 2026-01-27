# CLAUDE.md

Guidance for Claude Code when working with this monorepo.

## Project Overview

**Zoea Collab** (Agent Cowork Toolkit) is an AI-powered productivity suite organized as a pnpm monorepo with five packages:

| Package | Type | Description |
|---------|------|-------------|
| `zoea-core` | Python | Backend API (Django + django-ninja) + CLI (Typer) |
| `zoea-web-components` | npm | Reusable React AI/chat components |
| `zoea-studio` | npm | Productivity suite frontend |
| `zoea-docs` | MkDocs | Documentation site |
| `zoea-vm` | Python | VM management (placeholder) |

## Technology Stack

**Backend (zoea-core):** Django 5.1+, django-ninja APIs, django-organizations, OpenAI/Gemini, Python 3.12 via `uv`

**Frontend (zoea-studio):** Vite + React 19, Zustand, React Router, Tailwind CSS, Node.js 24 via `mise`

**Web Components:** React, Vite library mode, TypeScript

**Tools:** `mise` for task orchestration, `pnpm` for JS packages, `turborepo` for builds, `ruff` for Python linting

## Quick Start

```bash
mise install                    # Install Python 3.12 + Node.js 24
mise run install                # Install all dependencies
cd packages/zoea-core && uv run python manage.py migrate
cd packages/zoea-core && uv run python manage.py initialize_local_user
```

## Running

```bash
mise run dev                    # Start all development servers
mise run dev-backend            # Django at localhost:${ZOEA_CORE_BACKEND_PORT:-8000}
mise run dev-frontend           # Vite at localhost:${ZOEA_FRONTEND_PORT:-5173}
```

## Testing

```bash
mise run test                   # All tests (backend + frontend)
mise run test-backend           # Backend pytest
mise run test-frontend          # Frontend vitest
mise run test-e2e               # Playwright E2E
mise run lint                   # All linters
mise run format                 # Format Python code
```

## Building

```bash
mise run build                  # Build all packages (via turborepo)
mise run build:web-components   # Build @zoea/web-components
mise run build:studio           # Build zoea-studio
```

## Directory Structure

```
zoea-collab/
├── packages/
│   ├── zoea-core/              # Django backend + CLI
│   ├── zoea-web-components/    # @zoea/web-components npm package
│   ├── zoea-studio/            # React productivity app
│   ├── zoea-docs/              # MkDocs documentation
│   └── zoea-vm/                # VM tooling (placeholder)
├── .mise.toml                  # Root task orchestration
├── pnpm-workspace.yaml         # pnpm workspaces config
├── turbo.json                  # JS build orchestration
├── docker-compose.yml          # Development services
└── package.json                # Root package.json
```

## Critical Patterns

### Multi-Tenant Architecture

All tenant-scoped resources in zoea-core MUST include `organization` ForeignKey.
See `packages/zoea-docs/docs/architecture/multi-tenant.md` for required patterns.

### Web Components Usage

AI components are imported from `@zoea/web-components`:

```jsx
import { AIConversation, AIMessage, AIPromptInput } from '@zoea/web-components';
```

### React StrictMode

Read `packages/zoea-docs/docs/development/react-patterns.md` before implementing data loading.

## Documentation

```bash
mise run docs                   # Serve docs locally at :8001
```

## Environment Variables

Required in `.env`:
- `OPENAI_API_KEY` - Agent chat
- `GEMINI_API_KEY` - Document search/RAG
- `SECRET_KEY` - Django secret

See `.env.example` for all options.
