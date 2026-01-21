# ZoeaStudio Deployment on exe.dev

This guide covers deploying and managing ZoeaStudio on exe.dev VM instances.

## Overview

exe.dev provides Ubuntu-based VMs (exeuntu) with:
- Persistent disk storage
- HTTPS proxy on ports 3000-9999 (`https://<vmname>.exe.xyz:<port>/`)
- Optional built-in authentication via `X-ExeDev-*` headers
- Docker support
- systemd for persistent services

ZoeaStudio requires:
- Python 3.12 (pre-installed on exeuntu)
- Node.js 24 (install via nvm)
- PostgreSQL (Docker or SQLite for development)
- uv and mise (install manually)

---

## Quick Start

```bash
# 1. Install tooling
curl -LsSf https://astral.sh/uv/install.sh | sh
curl https://mise.run | sh
echo 'eval "$(~/.local/bin/mise activate bash)"' >> ~/.bashrc
source ~/.bashrc

# Install Node.js via nvm
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.3/install.sh | bash
source ~/.bashrc
nvm install 24
nvm alias default 24

# 2. Clone and setup
cd ~
gh auth login  # or use token-based auth
gh repo clone CitrusGroveTechnology/ZoeaStudio
cd ZoeaStudio

# 3. Install dependencies
mise install
mise run install

# 4. Configure environment
cp .env.example .env
# Edit .env with your API keys and settings (see Configuration section)

# 5. Initialize database
cd backend
uv run python manage.py migrate
uv run python manage.py initialize_local_user
cd ..

# 6. Start services (see systemd section for persistence)
mise run dev-backend &   # Port 8000
mise run dev-frontend &  # Port 5173
```

Your app will be available at:
- Backend API: `https://<vmname>.exe.xyz:8000/api/`
- Frontend: `https://<vmname>.exe.xyz:5173/`

---

## Environment Configuration

### Required `.env` Settings

```bash
# Django Security
SECRET_KEY=your-secure-random-key-here
DEBUG=False
ALLOWED_HOSTS=<vmname>.exe.xyz,localhost,127.0.0.1

# AI Providers (at least one required)
OPENAI_API_KEY=sk-...
GEMINI_API_KEY=...

# Database (SQLite by default, or PostgreSQL)
# DATABASE_URL=postgresql://zoea:zoea@localhost:5432/zoeastudio

# exe.dev specific
FRONTEND_URL=https://<vmname>.exe.xyz:5173
```

### exe.dev-Specific Settings

Add these to `backend/zoeastudio/settings.py` or create a production settings module:

```python
# Trust exe.dev reverse proxy headers
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
USE_X_FORWARDED_HOST = True
USE_X_FORWARDED_PORT = True

# CORS for exe.dev domain
CORS_ALLOWED_ORIGINS = [
    f"https://{os.environ.get('EXE_DEV_HOSTNAME', 'localhost')}.exe.xyz",
    f"https://{os.environ.get('EXE_DEV_HOSTNAME', 'localhost')}.exe.xyz:5173",
    f"https://{os.environ.get('EXE_DEV_HOSTNAME', 'localhost')}.exe.xyz:8000",
]

CSRF_TRUSTED_ORIGINS = CORS_ALLOWED_ORIGINS
```

### Environment Variables Reference

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `SECRET_KEY` | Yes | - | Django secret key |
| `DEBUG` | No | True | Set to False for production |
| `ALLOWED_HOSTS` | Yes | localhost | Comma-separated hostnames |
| `DATABASE_URL` | No | SQLite | PostgreSQL connection string |
| `OPENAI_API_KEY` | Yes* | - | OpenAI API key |
| `GEMINI_API_KEY` | Yes* | - | Google Gemini API key |
| `FRONTEND_URL` | No | - | Frontend URL for CORS |
| `EXE_DEV_HOSTNAME` | No | - | VM hostname for CORS config |

*At least one AI provider key required.

---

## Database Options

### Option 1: SQLite (Development/Simple)

Default configuration. Database stored at `backend/db.sqlite3`.

Pros:
- No setup required
- Persistent on exe.dev disk
- Sufficient for single-user/demo

Cons:
- Not suitable for concurrent users
- No separate backup strategy

### Option 2: PostgreSQL via Docker

```bash
# Start PostgreSQL container
docker run -d \
  --name zoea-postgres \
  --restart unless-stopped \
  -e POSTGRES_USER=zoea \
  -e POSTGRES_PASSWORD=zoea \
  -e POSTGRES_DB=zoeastudio \
  -p 5432:5432 \
  -v zoea-pgdata:/var/lib/postgresql/data \
  postgres:16-alpine

# Update .env
echo 'DATABASE_URL=postgresql://zoea:zoea@localhost:5432/zoeastudio' >> .env

# Run migrations
cd backend && uv run python manage.py migrate
```

### Option 3: External PostgreSQL (Supabase/Neon/etc.)

Set `DATABASE_URL` to your external database connection string. SSL is automatically enabled for non-localhost hosts.

---

## Deployment Strategies

### Strategy A: Development Mode (Simple)

Run Django dev server and Vite dev server directly. Good for development and demos.

```bash
# Backend
cd ~/ZoeaStudio/backend
uv run python manage.py runserver 0.0.0.0:8000

# Frontend (separate terminal)
cd ~/ZoeaStudio/frontend
npm run dev -- --host 0.0.0.0
```

### Strategy B: Production Mode (Recommended)

Use Gunicorn for backend and serve pre-built frontend via Nginx or a static server.

```bash
# Build frontend
cd ~/ZoeaStudio/frontend
npm run build

# Backend with Gunicorn
cd ~/ZoeaStudio/backend
uv run gunicorn zoeastudio.wsgi:application \
  --bind 0.0.0.0:8000 \
  --workers 2 \
  --timeout 120

# Serve frontend with a simple static server on port 5173
npx serve -s dist -l 5173
```

### Strategy C: Docker Compose (Full Stack)

Use existing Docker Compose configuration:

```bash
cd ~/ZoeaStudio

# Development
docker compose up -d

# Production
docker compose -f docker-compose.prod.yml up -d
```

---

## systemd Service Configuration

For persistent services that survive reboots.

### Backend Service

Create `/etc/systemd/system/zoea-backend.service`:

```ini
[Unit]
Description=ZoeaStudio Django Backend
After=network.target

[Service]
Type=simple
User=exedev
WorkingDirectory=/home/exedev/ZoeaStudio/backend
Environment="PATH=/home/exedev/.local/bin:/home/exedev/.cargo/bin:/usr/local/bin:/usr/bin:/bin"
EnvironmentFile=/home/exedev/ZoeaStudio/.env
ExecStart=/home/exedev/.local/bin/uv run gunicorn zoeastudio.wsgi:application --bind 0.0.0.0:8000 --workers 2 --timeout 120
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

### Frontend Service (Production Build)

Create `/etc/systemd/system/zoea-frontend.service`:

```ini
[Unit]
Description=ZoeaStudio React Frontend
After=network.target

[Service]
Type=simple
User=exedev
WorkingDirectory=/home/exedev/ZoeaStudio/frontend
Environment="PATH=/home/exedev/.nvm/versions/node/v24.0.0/bin:/usr/local/bin:/usr/bin:/bin"
ExecStart=/home/exedev/.nvm/versions/node/v24.0.0/bin/npx serve -s dist -l 5173
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

### Django-Q2 Worker (Background Tasks)

Create `/etc/systemd/system/zoea-worker.service`:

```ini
[Unit]
Description=ZoeaStudio Background Worker (Django-Q2)
After=network.target zoea-backend.service

[Service]
Type=simple
User=exedev
WorkingDirectory=/home/exedev/ZoeaStudio/backend
Environment="PATH=/home/exedev/.local/bin:/home/exedev/.cargo/bin:/usr/local/bin:/usr/bin:/bin"
EnvironmentFile=/home/exedev/ZoeaStudio/.env
ExecStart=/home/exedev/.local/bin/uv run python manage.py qcluster
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

### Enable and Start Services

```bash
sudo systemctl daemon-reload
sudo systemctl enable zoea-backend zoea-frontend zoea-worker
sudo systemctl start zoea-backend zoea-frontend zoea-worker

# Check status
systemctl status zoea-backend zoea-frontend zoea-worker

# View logs
journalctl -u zoea-backend -f
journalctl -u zoea-frontend -f
journalctl -u zoea-worker -f
```

---

## exe.dev Authentication Integration

exe.dev provides authentication headers that can be used to identify users:

- `X-ExeDev-UserID`: Stable unique user identifier
- `X-ExeDev-Email`: User's email address

### Optional: Trust exe.dev Authentication

Create middleware to use exe.dev auth headers (add to `backend/zoeastudio/middleware.py`):

```python
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser

User = get_user_model()

class ExeDevAuthMiddleware:
    """
    Authenticate users via exe.dev proxy headers.
    Only use this if your VM is NOT set to public.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user_id = request.headers.get('X-Exedev-Userid')
        email = request.headers.get('X-Exedev-Email')

        if user_id and email:
            # Get or create user based on exe.dev identity
            user, created = User.objects.get_or_create(
                username=f'exedev_{user_id}',
                defaults={'email': email}
            )
            request.user = user

        return self.get_response(request)
```

Add to `MIDDLEWARE` in settings.py (after `AuthenticationMiddleware`):

```python
MIDDLEWARE = [
    # ... existing middleware ...
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'zoeastudio.middleware.ExeDevAuthMiddleware',  # Add this
    # ...
]
```

**Security Note**: Only enable this if your VM requires exe.dev login (not public). Public VMs won't have these headers for unauthenticated users.

---

## Port Configuration

exe.dev proxies ports 3000-9999 via HTTPS:

| Service | Port | URL |
|---------|------|-----|
| Backend API | 8000 | `https://<vmname>.exe.xyz:8000/` |
| Frontend | 5173 | `https://<vmname>.exe.xyz:5173/` |
| PostgreSQL | 5432 | Internal only (not proxied) |

### Single-Port Deployment (Alternative)

Use Nginx to serve both frontend and proxy API on a single port:

```bash
sudo apt install nginx
```

Create `/etc/nginx/sites-available/zoeastudio`:

```nginx
server {
    listen 8000;
    server_name _;

    # Frontend static files
    location / {
        root /home/exedev/ZoeaStudio/frontend/dist;
        try_files $uri $uri/ /index.html;
    }

    # API proxy
    location /api/ {
        proxy_pass http://127.0.0.1:8001/api/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Media files
    location /media/ {
        proxy_pass http://127.0.0.1:8001/media/;
    }

    # Static files (Django admin, etc.)
    location /static/ {
        alias /home/exedev/ZoeaStudio/backend/staticfiles/;
    }
}
```

```bash
sudo ln -s /etc/nginx/sites-available/zoeastudio /etc/nginx/sites-enabled/
sudo rm /etc/nginx/sites-enabled/default
sudo nginx -t && sudo systemctl restart nginx
```

Update backend to run on port 8001 (internal) and access everything via port 8000.

---

## Operations

### Updating the Application

```bash
cd ~/ZoeaStudio
git pull origin main

# Update dependencies
mise run install

# Run migrations
cd backend && uv run python manage.py migrate

# Rebuild frontend
cd ../frontend && npm run build

# Restart services
sudo systemctl restart zoea-backend zoea-frontend zoea-worker
```

### Backup

```bash
# SQLite backup
cp ~/ZoeaStudio/backend/db.sqlite3 ~/backups/db-$(date +%Y%m%d).sqlite3

# PostgreSQL backup (if using Docker)
docker exec zoea-postgres pg_dump -U zoea zoeastudio > ~/backups/db-$(date +%Y%m%d).sql

# Media files backup
tar -czf ~/backups/media-$(date +%Y%m%d).tar.gz ~/ZoeaStudio/backend/media/
```

### Monitoring

```bash
# Service status
systemctl status zoea-backend zoea-frontend zoea-worker

# Live logs
journalctl -u zoea-backend -f

# Resource usage
htop

# Disk usage
df -h
du -sh ~/ZoeaStudio
```

### Troubleshooting

**Service won't start:**
```bash
journalctl -u zoea-backend --no-pager -n 50
```

**Database connection errors:**
```bash
# Check if PostgreSQL is running
docker ps | grep postgres

# Test connection
cd ~/ZoeaStudio/backend
uv run python manage.py dbshell
```

**Frontend build errors:**
```bash
cd ~/ZoeaStudio/frontend
rm -rf node_modules
npm install
npm run build
```

**Permission errors:**
```bash
sudo chown -R exedev:exedev ~/ZoeaStudio
```

---

## Resource Considerations

exe.dev VMs share CPU/RAM across your account. ZoeaStudio resource usage:

| Component | Memory | CPU | Notes |
|-----------|--------|-----|-------|
| Django + Gunicorn (2 workers) | ~200-400MB | Low | Scales with worker count |
| Django-Q2 worker | ~100-200MB | Low | Background task processing |
| Vite dev server | ~150-300MB | Medium | Hot reload overhead |
| Static frontend (serve) | ~50MB | Minimal | Production recommended |
| PostgreSQL (Docker) | ~100-200MB | Low | Optional |

**Recommendations:**
- Use production mode (built frontend) to reduce memory
- Start with 2 Gunicorn workers, increase if needed
- Consider SQLite for single-user deployments
- Monitor with `htop` and adjust as needed

---

## Security Checklist

- [ ] Set strong `SECRET_KEY` in `.env`
- [ ] Set `DEBUG=False` for production
- [ ] Configure `ALLOWED_HOSTS` with actual hostname
- [ ] Use PostgreSQL for multi-user deployments
- [ ] Keep VM private (require exe.dev login) unless intentionally public
- [ ] Regularly update dependencies (`mise run install`)
- [ ] Back up database and media files regularly
- [ ] Review Django security settings in `settings.py`

---

## Quick Reference

```bash
# Start all services
sudo systemctl start zoea-backend zoea-frontend zoea-worker

# Stop all services
sudo systemctl stop zoea-backend zoea-frontend zoea-worker

# Restart all services
sudo systemctl restart zoea-backend zoea-frontend zoea-worker

# View logs
journalctl -u zoea-backend -f
journalctl -u zoea-frontend -f
journalctl -u zoea-worker -f

# Django shell
cd ~/ZoeaStudio/backend && uv run python manage.py shell

# Database shell
cd ~/ZoeaStudio/backend && uv run python manage.py dbshell

# Run migrations
cd ~/ZoeaStudio/backend && uv run python manage.py migrate

# Collect static files
cd ~/ZoeaStudio/backend && uv run python manage.py collectstatic --noinput
```

---

## URLs

After deployment, your application will be available at:

| Environment | Frontend | Backend API |
|-------------|----------|-------------|
| Development | `https://<vmname>.exe.xyz:5173/` | `https://<vmname>.exe.xyz:8000/api/` |
| Production (separate ports) | `https://<vmname>.exe.xyz:5173/` | `https://<vmname>.exe.xyz:8000/api/` |
| Production (Nginx unified) | `https://<vmname>.exe.xyz:8000/` | `https://<vmname>.exe.xyz:8000/api/` |

Replace `<vmname>` with your actual exe.dev VM name (run `hostname` to check).
