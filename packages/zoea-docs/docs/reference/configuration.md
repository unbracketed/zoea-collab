# Configuration Reference

Complete reference for all configuration options in Zoea Collab, including environment variables, Django settings, and Vite configuration.

## Environment Variables

All environment variables are defined in the `.env` file at the project root.

### Creating the .env File

```bash
cp .env.example .env
```

Then edit `.env` to configure your environment.

### Required Variables

These variables **must** be set for the application to function:

| Variable | Description | Example |
|----------|-------------|---------|
| `OPENAI_API_KEY` | OpenAI API authentication key | `sk-proj-...` |

!!! danger "OpenAI API Key Required"
    The application will not start without a valid `OPENAI_API_KEY`.

### AI Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENAI_API_KEY` | *Required* | OpenAI API key for chat completions |
| `OPENAI_CHAT_MODEL_ID` | `gpt-4o-mini` | OpenAI model to use for chat |
| `GEMINI_API_KEY` | `None` | Google Gemini API key (optional, for file search) |
| `GEMINI_MODEL_ID` | `gemini-2.5-flash` | Gemini model for file search |
| `FILE_SEARCH_BACKEND` | `chromadb` | File search backend (`chromadb` or `gemini`) |
| `CHROMADB_PERSIST_DIRECTORY` | `None` | Optional directory to persist ChromaDB data |
| `FILE_SEARCH_MAX_TEXT_BYTES` | `2097152` | Max bytes to read from text files when indexing |
| `FILE_SEARCH_DISABLE_BACKGROUND_INDEXING` | `False` | Disable async indexing (run synchronously instead) |
| `IMAGE_CAPTION_PROVIDER` | `openai` | Provider for image captioning |
| `IMAGE_CAPTION_MODEL` | `gpt-4o` | Model for image captioning |
| `IMAGE_CAPTION_PROMPT` | `None` | Override prompt for image captioning |

File search stores are scoped per project and updated as content changes via background tasks.
See [File Search Indexing](../features/file-search-indexing.md) for details on automatic indexing.

### Agent Skills

| Variable | Default | Description |
|----------|---------|-------------|
| `ZOEA_SKILLS_DIRS` | `skills` | Comma-separated directories containing Agent Skills folders (each with `SKILL.md`) |

Relative paths resolve from the repository root (`BASE_DIR.parent`).

### Django Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `SECRET_KEY` | Auto-generated | Django secret key for cryptographic signing |
| `DEBUG` | `True` | Enable Django debug mode (set to `False` in production) |
| `ALLOWED_HOSTS` | `localhost,127.0.0.1` | Comma-separated list of allowed host names |

!!! warning "Production Security"
    Set `DEBUG=False` and use a strong, unique `SECRET_KEY` in production.

### Port Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `ZOEA_CORE_BACKEND_PORT` | `8000` | Port for Django development server |
| `ZOEA_FRONTEND_PORT` | `5173` | Port for Vite development server |
| `ZOEA_CORE_BACKEND_PORT` | `8000` | Host port for the zoea-core Docker Compose backend |
| `ZOEA_CORE_POSTGRES_PORT` | `5432` | Host port for the zoea-core Docker Compose database |

**Port Conflict Resolution:**

If default ports are already in use, change them in `.env`:

```env
ZOEA_CORE_BACKEND_PORT=8001
ZOEA_FRONTEND_PORT=5174
```

The CORS configuration and frontend API base URL will automatically adjust.

### Docker Compose Backend Command

| Variable | Default | Description |
|----------|---------|-------------|
| `ZOEA_CORE_BACKEND_COMMAND` | `uv run python manage.py runserver 0.0.0.0:8000` | Backend command used by the zoea-core Docker Compose stack |

**Example (Gunicorn):**
```env
ZOEA_CORE_BACKEND_COMMAND="uv run gunicorn zoea.wsgi:application --bind 0.0.0.0:8000 --workers 2"
```

### Document Import Limits

| Variable | Default | Description |
|----------|---------|-------------|
| `ZOEA_IMPORT_MAX_FILE_SIZE_BYTES` | `52428800` | Maximum size per file (bytes) |
| `ZOEA_IMPORT_MAX_TOTAL_SIZE_BYTES` | `10737418240` | Maximum total size across the import (bytes) |
| `ZOEA_IMPORT_MAX_FILE_COUNT` | `100000` | Maximum number of files in a single import |
| `ZOEA_IMPORT_MAX_DEPTH` | `10` | Maximum directory depth allowed |
| `ZOEA_IMPORT_ALLOWED_ROOTS` | `$HOME`, temp dir | Comma- or pathsep-separated list of allowed roots for server-side directory/archive imports |

Imports skip unsupported file types. Mermaid, Excalidraw, and JSONCanvas files are not imported yet.
Relative paths in `ZOEA_IMPORT_ALLOWED_ROOTS` resolve from the repository root.
Supported extensions: `.md`, `.markdown`, `.txt`, `.yaml`, `.yml`, `.json`, `.csv`, `.d2`, `.pdf`, `.png`, `.jpg`, `.jpeg`, `.gif`, `.bmp`, `.webp`.
Supported archive types: `.zip`, `.tar`, `.tar.gz`, `.tgz`.

### Database Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | SQLite | Database connection URL (optional, for PostgreSQL) |
| `ZOEA_CORE_DATABASE_URL` | `postgresql://zoea:zoea@db:5432/zoea` | Database URL used by the zoea-core Docker Compose stack |

**Example PostgreSQL URL:**
```env
DATABASE_URL=postgresql://user:password@localhost:5432/zoeastudio
```

**Example (zoea-core Docker Compose):**
```env
ZOEA_CORE_DATABASE_URL=postgresql://zoea:zoea@db:5432/zoea
```

### CORS Configuration

CORS origins are automatically configured based on `ZOEA_FRONTEND_PORT`:

```python
# settings.py (automatic)
CORS_ALLOWED_ORIGINS = [
    f"http://localhost:{os.getenv('ZOEA_FRONTEND_PORT', 5173)}"
]
```

## Django Settings

Settings are in `backend/zoeastudio/settings.py`.

### Installed Apps

```python
INSTALLED_APPS = [
    # Django core
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # Third-party
    'ninja',
    'corsheaders',
    'organizations',

    # Local apps
    'accounts',
    'chat',
    'documents',
    'transformations',
]
```

### Middleware

```python
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'corsheaders.middleware.CorsMiddleware',  # CORS early in stack
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]
```

### Database

**Development (SQLite):**
```python
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}
```

**Production (PostgreSQL):**
```python
import dj_database_url

DATABASES = {
    'default': dj_database_url.config(
        default=os.getenv('DATABASE_URL'),
        conn_max_age=600
    )
}
```

### Static Files

```python
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

STATICFILES_DIRS = [
    BASE_DIR / 'static',
]
```

### Media Files

```python
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'
```

## Vite Configuration

Configuration is in `frontend/vite.config.js`.

### Development Server

```javascript
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '');

  return {
    server: {
      port: parseInt(env.ZOEA_FRONTEND_PORT) || 5173,
      strictPort: false, // Try next port if occupied
    },

    define: {
      'import.meta.env.VITE_API_URL': JSON.stringify(
        `http://localhost:${env.ZOEA_CORE_BACKEND_PORT || 8000}`
      ),
    },
  };
});
```

### Build Output

```javascript
build: {
  outDir: 'dist',
  sourcemap: true,
  rollupOptions: {
    output: {
      manualChunks: {
        'react-vendor': ['react', 'react-dom', 'react-router-dom'],
      },
    },
  },
}
```

## mise Configuration

Task and environment configuration in `.mise.toml`.

### Tool Versions

```toml
[tools]
python = "3.12.8"
node = "24"
```

### Environment Variables

mise loads `.env` automatically for all tasks.

### Tasks

```toml
[tasks.dev-backend]
run = "cd backend && uv run python manage.py runserver $ZOEA_CORE_BACKEND_PORT"
description = "Run Django development server"

[tasks.dev-frontend]
run = "cd frontend && npm run dev"
description = "Run Vite development server"

[tasks.test]
run = "cd backend && uv run pytest"
description = "Run backend tests"
```

View all tasks:
```bash
mise tasks
```

## Python Dependencies

Dependencies are in `backend/pyproject.toml`.

### Main Dependencies

```toml
[project]
	dependencies = [
	    "django>=5.1",
	    "django-ninja>=1.3.0",
	    "django-cors-headers>=4.6.0",
	    "psycopg2-binary>=2.9.9",
	    "openai>=1.0.0",
	    "google-genai>=0.3.0",
	    # ...
	]
```

### Development Dependencies

```toml
[project.optional-dependencies]
dev = [
    "pytest>=8.3.0",
    "pytest-django>=4.9.0",
    "pytest-asyncio>=0.24.0",
    "pytest-cov>=6.0.0",
    "ruff>=0.7.0",
    "mkdocs-material>=9.5.0",
    "pymdown-extensions>=10.0",
]
```

Install with:
```bash
cd backend
uv sync --group dev
```

## Node.js Dependencies

Dependencies are in `frontend/package.json`.

### Main Dependencies

```json
{
  "dependencies": {
    "react": "^18.3.1",
    "react-dom": "^18.3.1",
    "react-router-dom": "^6.x",
    "zustand": "^4.x",
    "bootstrap": "^5.x",
    "reactflow": "^12.x"
  }
}
```

### Development Dependencies

```json
{
  "devDependencies": {
    "@vitejs/plugin-react": "^4.3.1",
    "vite": "^5.4.1",
    "@playwright/test": "^1.x",
    "eslint": "^9.x"
  }
}
```

## Pytest Configuration

Configuration in `backend/pyproject.toml`:

```toml
[tool.pytest.ini_options]
DJANGO_SETTINGS_MODULE = "zoeastudio.settings"
python_files = ["test_*.py", "*_test.py", "tests.py"]
asyncio_mode = "auto"
asyncio_default_fixture_loop_scope = "function"
```

## Ruff Configuration

Configuration in `backend/pyproject.toml`:

```toml
[tool.ruff]
line-length = 100
target-version = "py314"

[tool.ruff.lint]
select = ["E", "F", "I", "N", "W", "UP"]
ignore = []

[tool.ruff.format]
quote-style = "double"
indent-style = "space"
```

## Playwright Configuration

Configuration in `frontend/playwright.config.js`:

```javascript
export default defineConfig({
  testDir: './tests/e2e',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,

  use: {
    baseURL: 'http://localhost:5173',
    trace: 'on-first-retry',
  },

  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],

  webServer: [
    {
      command: 'cd ../backend && uv run python manage.py runserver 8000',
      port: 8000,
      reuseExistingServer: !process.env.CI,
    },
    {
      command: 'npm run dev',
      port: 5173,
      reuseExistingServer: !process.env.CI,
    },
  ],
});
```

## Production Configuration

### Security Settings

```python
# settings.py (production)
DEBUG = False
ALLOWED_HOSTS = ['yourdomain.com', 'www.yourdomain.com']
SECRET_KEY = os.environ['SECRET_KEY']  # Strong, unique key

SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
```

### Database

```python
DATABASES = {
    'default': dj_database_url.config(
        default=os.getenv('DATABASE_URL'),
        conn_max_age=600,
        conn_health_checks=True,
    )
}
```

### Static Files

Use WhiteNoise or S3:

```python
# With WhiteNoise
MIDDLEWARE.insert(1, 'whitenoise.middleware.WhiteNoiseMiddleware')
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# With S3
DEFAULT_FILE_STORAGE = 'storages.backends.s3boto3.S3Boto3Storage'
AWS_STORAGE_BUCKET_NAME = 'your-bucket'
```

## Logging

```python
# settings.py
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
}
```

## Next Steps

- [Technology Stack](technology-stack.md) - All technologies used
- [Common Workflows](common-workflows.md) - Configuration for specific tasks
- [Installation Guide](../getting-started/installation.md) - Initial setup
- [Development Guide](../getting-started/development.md) - Development workflow
