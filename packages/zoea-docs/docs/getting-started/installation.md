# Installation

This guide walks you through installing mise, setting up the Zoea Collab project, and installing all required dependencies.

## Step 1: Install mise

**mise** is a tool version manager and task runner that Zoea Collab uses to manage Python, Node.js, and project tasks.

### Installation Options

=== "macOS/Linux"

    ```bash
    curl https://mise.run | sh
    ```

    After installation, add mise to your shell:

    ```bash
    # For bash
    echo 'eval "$(~/.local/bin/mise activate bash)"' >> ~/.bashrc

    # For zsh
    echo 'eval "$(~/.local/bin/mise activate zsh)"' >> ~/.zshrc

    # For fish
    echo '~/.local/bin/mise activate fish | source' >> ~/.config/fish/config.fish
    ```

    Then restart your shell or run:

    ```bash
    source ~/.bashrc  # or ~/.zshrc, depending on your shell
    ```

=== "Homebrew (macOS)"

    ```bash
    brew install mise
    ```

=== "Other methods"

    For additional installation methods, see the [official mise documentation](https://mise.jdx.dev/getting-started.html).

### Verify Installation

Confirm mise is installed correctly:

```bash
mise --version
```

You should see output like `mise 2024.x.x`.

## Step 2: Clone the Repository

Clone the Zoea Collab repository to your local machine:

```bash
git clone https://github.com/citrusgrovetechnology/ZoeaStudio.git
cd ZoeaStudio
```

!!! tip
    If you plan to contribute, fork the repository first and clone your fork instead.

## Step 3: Install Tool Versions

mise will automatically detect the `.mise.toml` configuration and install the required Python and Node.js versions:

```bash
mise install
```

This command installs:

- **Python 3.12** - Backend runtime
- **Node.js 24** - Frontend runtime

!!! info "Behind the scenes"
    mise reads the `.mise.toml` file which specifies:
    ```toml
    [tools]
    python = "3.12.8"
    node = "24"
    ```

Verify the tools are installed:

```bash
mise current
```

You should see output showing Python 3.12 and Node 24 are active.

## Step 4: Install Project Dependencies

Now install both backend (Python) and frontend (Node.js) dependencies using the mise task:

```bash
mise run install
```

This single command:

1. Installs Python dependencies using `uv` (backend)
2. Installs Node.js dependencies using `npm` (frontend)

!!! note "What is uv?"
    [uv](https://github.com/astral-sh/uv) is a fast Python package installer and resolver. It's much faster than pip and is used throughout the project for dependency management.

### Manual Installation (Alternative)

If you prefer to install dependencies manually:

=== "Backend (Python)"

    ```bash
    cd backend
    uv sync
    cd ..
    ```

=== "Frontend (Node.js)"

    ```bash
    cd frontend
    npm install
    cd ..
    ```

## Step 5: Configure Environment Variables

Create a `.env` file from the example template:

```bash
cp .env.example .env
```

Open `.env` in your text editor and configure the required settings:

```env
# Required: OpenAI API key for AI agents
OPENAI_API_KEY=your-openai-api-key-here
OPENAI_CHAT_MODEL_ID=gpt-4o-mini

# Optional: Gemini API key for file search
GEMINI_API_KEY=your-gemini-api-key-here
GEMINI_MODEL_ID=gemini-2.5-flash

# Django settings
SECRET_KEY=your-secret-key-here
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

# Optional: Port configuration (defaults shown)
ZOEA_BACKEND_PORT=8000    # Django dev server port
ZOEA_FRONTEND_PORT=5173   # Vite dev server port
```

!!! warning "OpenAI API Key Required"
    You **must** provide a valid `OPENAI_API_KEY` for the chat functionality to work. Get your API key from [platform.openai.com](https://platform.openai.com/api-keys).

!!! tip "Port Conflicts"
    If ports 8000 or 5173 are already in use by other applications, you can change the `ZOEA_BACKEND_PORT` and `ZOEA_FRONTEND_PORT` values. The CORS configuration and API base URL will automatically adjust.

## Step 6: Run Database Migrations

Set up the database schema by running Django migrations:

```bash
cd backend
uv run python manage.py migrate
cd ..
```

This creates the SQLite database (`backend/db.sqlite3`) and sets up all required tables.

!!! info "Database Choice"
    Zoea Collab uses SQLite for development and is configured to support PostgreSQL for production. The database configuration is in `backend/zoeastudio/settings.py`.

## Verification

Verify your installation by checking that all components are ready:

```bash
# Check mise tools
mise current

# Check Python packages
cd backend
uv pip list
cd ..

# Check Node packages
cd frontend
npm list --depth=0
cd ..
```

## Next Steps

Now that you have Zoea Collab installed, proceed to:

1. **[Development Setup](development.md)** - Learn about development commands and workflows
2. **[User Initialization](initialization.md)** - Create your first user and organization

## Troubleshooting

### mise not found after installation

Ensure you've added mise to your shell configuration and restarted your terminal. See [Step 1](#step-1-install-mise) above.

### uv: command not found

`uv` should be installed automatically with Python dependencies. If not, install it manually:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### Python version mismatch

Ensure mise installed Python 3.12:

```bash
mise current python
```

If it shows a different version, try:

```bash
mise install python@3.12.8
mise use python@3.12.8
```

### npm install fails

Ensure Node.js 24 is active:

```bash
mise current node
```

If needed, reinstall:

```bash
mise install node@24
mise use node@24
```
