# Welcome to Zoea Collab

**Agent Cowork Toolkit - An intelligent knowledge base and workflow collaboration platform**

## Overview

Zoea Collab combines AI agents with knowledge bases for research, business process, and workflow management. Flow between chat, documents,
canvas to take control.

## Key Features

- **AI-Powered Chat** - Interactive conversations with AI agents using any model.
- **Workflow Automation** - PocketFlow-based workflows with YAML configuration and automatic document generation
- **Command-Line Interface** - Typer-based CLI (`zoea`) for managing projects, workspaces, and running workflows
- **Multi-Tenant Architecture** - Secure organization-based access control using django-organizations
- **Content Transformations** - Flexible system for transforming documents (Markdown ↔ HTML ↔ PDF)
- **Gemini File Search** - Semantic search and RAG capabilities for project documents
- **Modern Tech Stack** - Django 6.0 + React with Vite
- **Canvas and Diagrams** - scriptable canvas workspace

## Quick Start

New to Zoea Collab? Get up and running in minutes:

<div class="grid cards" markdown>

-   :material-rocket-launch:{ .lg .middle } **Getting Started**

    ---

    Install dependencies, configure your environment, and launch the application

    [:octicons-arrow-right-24: Installation Guide](getting-started/installation.md)

-   :material-book-open-variant:{ .lg .middle } **Architecture**

    ---

    Understand the system design, multi-tenant architecture, and component relationships

    [:octicons-arrow-right-24: Architecture Overview](architecture/overview.md)

-   :material-code-braces:{ .lg .middle } **Development**

    ---

    Learn development workflows, testing patterns, and best practices

    [:octicons-arrow-right-24: Development Guide](development/testing.md)

-   :material-api:{ .lg .middle } **API Reference**

    ---

    Explore the REST API endpoints and interactive API documentation

    [:octicons-arrow-right-24: API Docs](development/api-reference.md)

-   :material-console:{ .lg .middle } **Command-Line Interface**

    ---

    Manage projects, workspaces, and run workflows from the terminal

    [:octicons-arrow-right-24: CLI Guide](features/cli.md)

-   :material-workflow:{ .lg .middle } **Workflows**

    ---

    Automate multi-step processes with PocketFlow and YAML configuration

    [:octicons-arrow-right-24: Workflow Guide](features/workflows.md)

</div>

## Technology Stack

### Backend
- **Django 6.0** with django-ninja for REST APIs
- **PostgreSQL** (SQLite for development)
- **LLM provider abstraction** for AI orchestration
- **OpenAI** for chat completions
- **Google Gemini File Search Tool** for file search and RAG
- **PocketFlow** for workflow orchestration
- **Typer + Rich** for CLI
- **Python 3.12** managed with `uv`
- **pytest** with 99% code coverage

### Frontend
- **Vite + React** with StrictMode enabled
- **Zustand** for state management
- **React Router** with lazy loading
- **Bootstrap 5 + Tailwind CSS** for styling
- **Modular layout system** with LayoutFrame
- **Playwright** for E2E testing

### DevOps
- **mise** for tool versions and task management
- **GitHub Actions** for CI/CD
- **Ruff** for linting and formatting

## Documentation Sections

### [Getting Started](getting-started/index.md)
Step-by-step guides to install, configure, and run Zoea Collab locally.

### [Architecture](architecture/overview.md)
Deep dive into system design, multi-tenant patterns, and component architecture.

### [Features](features/chat-logging.md)
Detailed documentation of key features including chat logging, transformations, Gemini search, CLI, and workflows.

### [Development](development/testing.md)
Development workflows, testing strategies, and coding patterns.

### [Reference](reference/technology-stack.md)
Technology stack details, configuration options, and common workflows.

## Contributing

Contributions are welcome! Please ensure:

- Code is formatted with `ruff`
- Tests are included for new features (maintain 99% coverage)
- Documentation is updated
- Multi-tenant patterns are followed (see [Multi-Tenant Guide](architecture/multi-tenant.md))

## Support

- **GitHub Issues**: [Report bugs or request features](https://github.com/unbracketed/zoea-collab/issues)
- **API Documentation**: Interactive docs at `/api/docs` when running locally
- **Source Code**: Browse the [GitHub repository](https://github.com/unbracketed/zoea-collab)

## License

This project is part of Zoea Collab and follows the project's licensing terms.
