# Development Setup

This guide covers development workflows, commands, and best practices for working with Zoea Collab.

## Running the Application

Zoea Collab consists of two main components that run concurrently:

1. **Backend** - Django API server (default: port 8000)
2. **Frontend** - Vite development server (default: port 5173)

### Starting Both Servers

You'll need **two terminal windows** open:

=== "Terminal 1: Backend"

    ```bash
    mise run dev-backend
    ```

    The Django API will start at `http://localhost:8000`

    You'll see output like:
    ```
    Watching for file changes with StatReloader
    Performing system checks...

    System check identified no issues (0 silenced).
    November 16, 2025 - 14:30:00
    Django version 6.0, using settings 'zoeastudio.settings'
    Starting development server at http://0.0.0.0:8000/
    Quit the server with CONTROL-C.
    ```

=== "Terminal 2: Frontend"

    ```bash
    mise run dev-frontend
    ```

    The React app will start at `http://localhost:5173`

    You'll see output like:
    ```
    VITE v5.x.x ready in 500 ms

    ➜  Local:   http://localhost:5173/
    ➜  Network: use --host to expose
    ➜  press h + enter to show help
    ```

!!! success "Access the Application"
    Open your browser and navigate to `http://localhost:5173` to access Zoea Collab.

### Port Configuration

If you need to use different ports (e.g., to avoid conflicts with other applications), edit the `.env` file:

```env
ZOEA_BACKEND_PORT=8001    # Django will run on port 8001
ZOEA_FRONTEND_PORT=5174   # Vite will run on port 5174
```

The CORS settings and API base URL will automatically update based on these values.

!!! tip "Port Conflicts"
    If you see errors like "Address already in use", another application is using that port. Change the port in `.env` or stop the conflicting application.

## Available mise Tasks

Zoea Collab uses `mise` for task management. View all available tasks:

```bash
mise tasks
```

### Development Tasks

| Task | Description |
|------|-------------|
| `mise run dev-backend` | Start Django development server |
| `mise run dev-frontend` | Start Vite development server |
| `mise run install` | Install all dependencies (backend + frontend) |

### Testing Tasks

| Task | Description |
|------|-------------|
| `mise run test` | Run backend unit tests (pytest) |
| `mise run test-cov` | Run backend tests with coverage report |
| `mise run test-e2e` | Run E2E tests headless (Playwright) |
| `mise run test-e2e-ui` | Run E2E tests with interactive UI |
| `mise run test-e2e-headed` | Run E2E tests in visible browser |
| `mise run test-all` | Run all tests (backend + E2E) |

### Code Quality Tasks

| Task | Description |
|------|-------------|
| `mise run lint` | Run ruff linter on backend code |
| `mise run format` | Format backend code with ruff |

### Documentation Tasks

| Task | Description |
|------|-------------|
| `mise run docs` | Serve documentation locally |
| `mise run docs-build` | Build documentation site |

## Development Workflow

### Making Code Changes

1. **Backend Changes**: Edit files in `backend/`, Django will auto-reload
2. **Frontend Changes**: Edit files in `frontend/src/`, Vite will hot-reload

!!! info "Hot Module Replacement"
    Both Django (via StatReloader) and Vite support automatic reloading. You don't need to manually restart the servers when making code changes.

### Testing Your Changes

Before committing code, always run tests:

```bash
# Run backend tests
mise run test

# Run E2E tests
mise run test-e2e

# Or run everything
mise run test-all
```

!!! tip "Test Coverage"
    Zoea Collab maintains 99% code coverage. New features should include comprehensive tests.

### Code Quality Checks

Ensure code quality with linting and formatting:

```bash
# Check for linting issues
mise run lint

# Auto-format code
mise run format
```

## Project Structure

Understanding the project layout helps with navigation:

```
ZoeaStudio/
├── backend/                      # Django backend
│   ├── zoeastudio/               # Django project settings
│   │   ├── settings.py           # Configuration
│   │   └── urls.py               # URL routing
│   ├── chat/                     # Chat application
│   │   ├── agent_service.py      # LLM chat service
│   │   ├── graphologue_service.py # Diagram generation
│   │   ├── api.py                # API endpoints
│   │   ├── schemas.py            # Pydantic schemas
│   │   ├── models.py             # Database models
│   │   └── tests.py              # Tests
│   ├── accounts/                 # User & organization management
│   ├── documents/                # Document management
│   ├── transformations/          # Content transformation system
│   ├── manage.py                 # Django management script
│   └── pyproject.toml            # Python dependencies
├── frontend/                     # React frontend
│   ├── src/
│   │   ├── App.jsx               # Main component
│   │   ├── components/           # React components
│   │   ├── contexts/             # React contexts
│   │   └── styles/               # CSS files
│   ├── tests/                    # Playwright E2E tests
│   ├── package.json              # Node.js dependencies
│   └── vite.config.js            # Vite configuration
├── docs/                         # Documentation (MkDocs)
├── .env                          # Environment variables (local, not in git)
├── .env.example                  # Environment template
├── .mise.toml                    # mise configuration
└── mkdocs.yml                    # Documentation configuration
```

## API Access

### Interactive API Documentation

Django Ninja provides interactive API documentation:

```
http://localhost:8000/api/docs
```

This Swagger-style interface lets you:

- View all available endpoints
- See request/response schemas
- Try API calls directly from the browser

### Health Check

Verify the backend is running:

```bash
curl http://localhost:8000/api/health
```

Response:
```json
{
  "status": "ok",
  "service": "chat"
}
```

## Database Management

### Migrations

When you change Django models, create and apply migrations:

```bash
cd backend

# Create new migrations
uv run python manage.py makemigrations

# Apply migrations
uv run python manage.py migrate
```

### Django Admin

Access the Django admin interface:

```
http://localhost:8000/admin
```

You'll need to create a superuser first (see [User Initialization](initialization.md)).

### Database Reset (Development Only)

If you need to reset the database during development:

```bash
cd backend
rm db.sqlite3
uv run python manage.py migrate
uv run python manage.py initialize_local_user
```

!!! warning "Data Loss"
    This deletes all data. Only do this in development!

## Common Development Tasks

### Running a Single Test

```bash
cd backend
uv run pytest path/to/test_file.py::TestClass::test_method
```

### Running Tests with Print Statements

```bash
cd backend
uv run pytest -s path/to/test_file.py
```

### Viewing Test Coverage

```bash
mise run test-cov
```

This generates:
- Terminal coverage report
- HTML report in `backend/htmlcov/index.html`

### Installing New Dependencies

=== "Backend (Python)"

    ```bash
    cd backend
    uv add package-name
    ```

=== "Frontend (Node.js)"

    ```bash
    cd frontend
    npm install package-name
    ```

## Environment Variables Reference

Key environment variables in `.env`:

| Variable | Purpose | Default |
|----------|---------|---------|
| `OPENAI_API_KEY` | OpenAI API authentication | Required |
| `OPENAI_CHAT_MODEL_ID` | OpenAI model to use | `gpt-4o-mini` |
| `GEMINI_API_KEY` | Google Gemini API key | Optional |
| `GEMINI_MODEL_ID` | Gemini model for file search | `gemini-2.5-flash` |
| `SECRET_KEY` | Django secret key | Auto-generated |
| `DEBUG` | Django debug mode | `True` |
| `ALLOWED_HOSTS` | Allowed HTTP hosts | `localhost,127.0.0.1` |
| `ZOEA_BACKEND_PORT` | Django server port | `8000` |
| `ZOEA_FRONTEND_PORT` | Vite server port | `5173` |

## Next Steps

Now that you understand the development workflow:

1. **[Initialize a User](initialization.md)** - Create your first user and organization
2. **[Learn the Architecture](../architecture/overview.md)** - Understand the system design
3. **[Review Testing Patterns](../development/testing.md)** - Write effective tests
4. **[Explore Features](../features/chat-logging.md)** - Learn about key features

## Troubleshooting

### Backend server won't start

- Check that port 8000 (or `ZOEA_BACKEND_PORT`) is available
- Ensure `.env` file exists with valid `OPENAI_API_KEY`
- Verify migrations have been run: `cd backend && uv run python manage.py migrate`

### Frontend can't connect to backend

- Ensure backend is running on the correct port
- Check for CORS errors in browser console
- Verify port configuration in `.env` matches

### Tests failing

- Ensure all dependencies are installed: `mise run install`
- Check that you're in the correct directory
- Run with verbose output: `cd backend && uv run pytest -vv`

### Hot reload not working

- **Backend**: Check terminal for Python syntax errors
- **Frontend**: Check browser console for JavaScript errors
- Restart the respective development server
