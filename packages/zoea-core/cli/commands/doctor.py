"""Doctor command - diagnostic checks for project configuration."""

import os
from pathlib import Path
from typing import Any

import typer
from django.conf import settings
from django.db import connection
from rich.console import Console

from cli.utils.django_context import with_django
from cli.utils.formatting import FormatOption, OutputFormat, print_json

console = Console()

# Status indicators
CHECK = "[green]✓[/green]"
CROSS = "[red]✗[/red]"
WARN = "[yellow]⚠[/yellow]"


def get_backend_dir() -> Path:
    """Get the backend directory path (zoea-core package)."""
    return Path(__file__).resolve().parent.parent.parent


def get_project_root() -> Path:
    """Get the project root directory (monorepo root, two levels up from zoea-core)."""
    return get_backend_dir().parent.parent


def mask_key(key: str | None) -> str | None:
    """Mask API key showing only first 3 and last 3 chars."""
    if not key:
        return None
    if len(key) <= 8:
        return "***"
    return f"{key[:3]}...{key[-3:]}"


def print_section(title: str):
    """Print a section header."""
    console.print()
    console.print(f"[bold]{title}[/bold]")
    console.print("─" * 54)


def print_row(label: str, value: str, status: str | None = None):
    """Print a formatted row with label, value, and optional status."""
    label_width = 24
    if status:
        console.print(f"  {label:<{label_width}} {status} {value}")
    else:
        console.print(f"  {label:<{label_width}} {value}")


def check_config_files() -> dict[str, Any]:
    """Check configuration files existence."""
    project_root = get_project_root()
    env_path = project_root / ".env"
    env_example_path = project_root / ".env.example"

    result = {
        "env_exists": env_path.exists(),
        "env_path": str(env_path),
        "env_example_exists": env_example_path.exists(),
        "env_example_path": str(env_example_path),
        "issues": [],
    }

    if not result["env_exists"]:
        result["issues"].append(".env file not found - copy from .env.example and configure")

    return result


def check_environment() -> dict[str, Any]:
    """Check environment variables."""
    debug = getattr(settings, "DEBUG", False)
    secret_key_set = bool(getattr(settings, "SECRET_KEY", None))
    allowed_hosts = getattr(settings, "ALLOWED_HOSTS", [])

    result = {
        "debug": debug,
        "secret_key_set": secret_key_set,
        "allowed_hosts": allowed_hosts,
        "issues": [],
    }

    if not secret_key_set:
        result["issues"].append("SECRET_KEY not set - required for security")

    return result


def check_api_keys() -> dict[str, Any]:
    """Check API key configuration."""
    openai_key = os.environ.get("OPENAI_API_KEY")
    gemini_key = os.environ.get("GEMINI_API_KEY")
    file_search_backend = os.environ.get("FILE_SEARCH_BACKEND", "chromadb")

    result = {
        "openai_key_set": bool(openai_key),
        "openai_key_masked": mask_key(openai_key),
        "gemini_key_set": bool(gemini_key),
        "gemini_key_masked": mask_key(gemini_key),
        "issues": [],
    }

    if not openai_key:
        result["issues"].append("OPENAI_API_KEY not set - required for agent chat")

    if file_search_backend == "gemini" and not gemini_key:
        result["issues"].append("GEMINI_API_KEY not set - required for gemini file search backend")

    return result


def check_llm_config() -> dict[str, Any]:
    """Check LLM configuration."""
    provider = os.environ.get("DEFAULT_LLM_PROVIDER", "openai")
    default_model = os.environ.get("DEFAULT_LLM_MODEL", "")
    openai_model = os.environ.get("OPENAI_CHAT_MODEL_ID", "gpt-4o-mini")
    gemini_model = os.environ.get("GEMINI_MODEL_ID", "gemini-2.5-flash")
    local_endpoint = os.environ.get("LOCAL_MODEL_ENDPOINT", "http://localhost:11434")

    return {
        "provider": provider,
        "default_model": default_model or (openai_model if provider == "openai" else gemini_model),
        "openai_model": openai_model,
        "gemini_model": gemini_model,
        "local_endpoint": local_endpoint,
        "issues": [],
    }


def check_database() -> dict[str, Any]:
    """Check database configuration and connectivity."""
    db_settings = settings.DATABASES.get("default", {})
    engine = db_settings.get("ENGINE", "")

    # Determine database type
    if "sqlite" in engine.lower():
        db_type = "SQLite"
        db_location = str(db_settings.get("NAME", ""))
    elif "postgresql" in engine.lower() or "psycopg" in engine.lower():
        db_type = "PostgreSQL"
        host = db_settings.get("HOST", "localhost")
        port = db_settings.get("PORT", "5432")
        name = db_settings.get("NAME", "")
        db_location = f"{host}:{port}/{name}"
    else:
        db_type = "Unknown"
        db_location = str(db_settings.get("NAME", ""))

    # Test connection
    connection_ok = False
    try:
        connection.ensure_connection()
        connection_ok = True
    except Exception:
        pass

    # Check migrations
    migrations_status = "unknown"
    pending_count = 0
    applied_count = 0
    try:
        from django.db.migrations.executor import MigrationExecutor

        executor = MigrationExecutor(connection)
        targets = executor.loader.graph.leaf_nodes()
        plan = executor.migration_plan(targets)
        pending_count = len(plan)

        # Count applied migrations
        applied_count = len(executor.loader.applied_migrations)

        if pending_count == 0:
            migrations_status = "up_to_date"
        else:
            migrations_status = "pending"
    except Exception:
        migrations_status = "error"

    result = {
        "type": db_type,
        "location": db_location,
        "connection_ok": connection_ok,
        "migrations_status": migrations_status,
        "pending_migrations": pending_count,
        "applied_migrations": applied_count,
        "issues": [],
    }

    if not connection_ok:
        result["issues"].append("Database connection failed")

    if migrations_status == "pending":
        result["issues"].append(f"{pending_count} pending migration(s) - run 'mise run db-migrate'")

    return result


def check_file_search() -> dict[str, Any]:
    """Check file search / vector store configuration."""
    backend = os.environ.get("FILE_SEARCH_BACKEND", "chromadb")
    persist_dir = os.environ.get("CHROMADB_PERSIST_DIRECTORY", "")

    result = {
        "backend": backend,
        "persist_directory": persist_dir,
        "persist_directory_exists": bool(persist_dir) and Path(persist_dir).exists(),
        "issues": [],
    }

    if backend == "chromadb" and not persist_dir:
        result["issues"].append("CHROMADB_PERSIST_DIRECTORY not set - using in-memory storage")

    return result


def check_ports() -> dict[str, Any]:
    """Check port configuration."""
    return {
        "backend": os.environ.get("ZOEA_CORE_BACKEND_PORT", "8000"),
        "frontend": os.environ.get("ZOEA_FRONTEND_PORT", "5173"),
        "docs": os.environ.get("ZOEA_DOCS_PORT", "8001"),
        "postgres": os.environ.get("ZOEA_CORE_POSTGRES_PORT", "5433"),
        "issues": [],
    }


def check_media() -> dict[str, Any]:
    """Check media file configuration."""
    debug = getattr(settings, "DEBUG", False)
    serve_media = os.environ.get("SERVE_MEDIA", "False") == "True"
    media_root = getattr(settings, "MEDIA_ROOT", None)
    media_url = getattr(settings, "MEDIA_URL", "/media/")

    result = {
        "debug": debug,
        "serve_media": serve_media,
        "media_root": str(media_root) if media_root else None,
        "media_root_exists": media_root and Path(media_root).exists(),
        "media_url": media_url,
        "media_serving_enabled": debug or serve_media,
        "issues": [],
    }

    # Check if media can be served
    if not debug and not serve_media:
        result["issues"].append(
            "Media files won't be served - set DEBUG=True or SERVE_MEDIA=True"
        )

    # Check if media root exists
    if media_root and not Path(media_root).exists():
        result["issues"].append(f"MEDIA_ROOT directory does not exist: {media_root}")

    # Count files in media directory
    if media_root and Path(media_root).exists():
        try:
            file_count = sum(1 for _ in Path(media_root).rglob("*") if _.is_file())
            result["file_count"] = file_count
        except Exception:
            result["file_count"] = None

    return result


def check_workers() -> dict[str, Any]:
    """Check Django-Q2 worker status."""
    result = {
        "available": False,
        "workers_running": 0,
        "queue_depth": 0,
        "issues": [],
    }

    try:
        from django_q.models import OrmQ
        from django_q.status import Stat

        result["available"] = True

        # Check for active workers via Stat
        stats = Stat.get_all()
        result["workers_running"] = len(stats) if stats else 0

        # Check queue depth
        result["queue_depth"] = OrmQ.objects.count()

        if result["workers_running"] == 0:
            result["issues"].append("No background workers running - run 'mise run worker'")

    except ImportError:
        result["issues"].append("Django-Q2 not available")
    except Exception as e:
        result["issues"].append(f"Error checking worker status: {e}")

    return result


def output_report(report: dict[str, Any], format: OutputFormat):
    """Output the diagnostic report."""
    if format == OutputFormat.JSON:
        print_json(report)
        return

    # Print header
    console.print()
    console.print("[bold cyan]Zoea Collab Doctor[/bold cyan]")
    console.print("═" * 54)

    # Configuration Files
    config = report["config_files"]
    print_section("Configuration Files")
    status = CHECK if config["env_exists"] else CROSS
    print_row(".env", "Found" if config["env_exists"] else "Not found", status)
    status = CHECK if config["env_example_exists"] else CROSS
    print_row(".env.example", "Found" if config["env_example_exists"] else "Not found", status)
    if not config["env_exists"] and config["env_example_exists"]:
        console.print("  [dim]💡 Copy .env.example to .env and configure[/dim]")

    # Environment
    env = report["environment"]
    print_section("Environment")
    debug_style = "[yellow]" if env["debug"] else "[green]"
    print_row("DEBUG", f"{debug_style}{env['debug']}[/]")
    status = CHECK if env["secret_key_set"] else CROSS
    print_row("SECRET_KEY", "Set" if env["secret_key_set"] else "Not set", status)
    hosts = ", ".join(env["allowed_hosts"]) if env["allowed_hosts"] else "None"
    print_row("ALLOWED_HOSTS", hosts)

    # API Keys
    api = report["api_keys"]
    print_section("API Keys")
    status = CHECK if api["openai_key_set"] else CROSS
    value = f"Set ({api['openai_key_masked']})" if api["openai_key_set"] else "Not set"
    print_row("OPENAI_API_KEY", value, status)
    status = CHECK if api["gemini_key_set"] else CROSS
    value = f"Set ({api['gemini_key_masked']})" if api["gemini_key_set"] else "Not set"
    print_row("GEMINI_API_KEY", value, status)

    # LLM Configuration
    llm = report["llm_config"]
    print_section("LLM Configuration")
    print_row("Provider", llm["provider"])
    print_row("Default Model", llm["default_model"])
    print_row("OpenAI Model", llm["openai_model"])
    print_row("Gemini Model", llm["gemini_model"])
    if llm["provider"] == "local":
        print_row("Local Endpoint", llm["local_endpoint"])

    # Database
    db = report["database"]
    print_section("Database")
    print_row("Engine", db["type"])
    print_row("Location", db["location"])
    status = CHECK if db["connection_ok"] else CROSS
    print_row("Connection", "OK" if db["connection_ok"] else "Failed", status)
    if db["migrations_status"] == "up_to_date":
        status = CHECK
        value = f"Up to date ({db['applied_migrations']} applied)"
    elif db["migrations_status"] == "pending":
        status = WARN
        value = f"{db['pending_migrations']} pending"
    else:
        status = CROSS
        value = "Error checking"
    print_row("Migrations", value, status)

    # File Search
    fs = report["file_search"]
    print_section("File Search")
    print_row("Backend", fs["backend"])
    if fs["backend"] == "chromadb":
        if fs["persist_directory"]:
            status = CHECK if fs["persist_directory_exists"] else CROSS
            value = fs["persist_directory"]
            if not fs["persist_directory_exists"]:
                value += " (not found)"
        else:
            status = WARN
            value = "Not set (using in-memory)"
        print_row("Persist Directory", value, status)

    # Media
    media = report["media"]
    print_section("Media Files")
    if media["media_serving_enabled"]:
        if media["debug"]:
            status = CHECK
            value = "Enabled (DEBUG=True)"
        else:
            status = CHECK
            value = "Enabled (SERVE_MEDIA=True)"
    else:
        status = CROSS
        value = "Disabled"
    print_row("Serving", value, status)
    print_row("MEDIA_URL", media["media_url"])
    if media["media_root"]:
        status = CHECK if media["media_root_exists"] else CROSS
        value = media["media_root"]
        if not media["media_root_exists"]:
            value += " (not found)"
        elif media.get("file_count") is not None:
            value += f" ({media['file_count']} files)"
        print_row("MEDIA_ROOT", value, status)
    else:
        print_row("MEDIA_ROOT", "Not set", CROSS)
    if not media["media_serving_enabled"]:
        console.print("  [dim]💡 Set SERVE_MEDIA=True in .env for development VMs[/dim]")

    # Ports
    ports = report["ports"]
    print_section("Ports")
    print_row("Backend", ports["backend"])
    print_row("Frontend", ports["frontend"])
    print_row("Docs", ports["docs"])
    print_row("PostgreSQL", ports["postgres"])

    # Workers
    workers = report["workers"]
    print_section("Background Workers (Django-Q2)")
    if workers["available"]:
        status = CHECK if workers["workers_running"] > 0 else CROSS
        running = workers["workers_running"]
        value = str(running) if running > 0 else "None running"
        print_row("Workers", value, status)
        print_row("Queue Depth", f"{workers['queue_depth']} task(s)")
        if workers["workers_running"] == 0:
            console.print("  [dim]⚡ Run 'mise run worker' to start background tasks[/dim]")
    else:
        print_row("Status", "Not available", CROSS)

    # Summary
    all_issues = report["all_issues"]
    console.print()
    console.print("═" * 54)
    if all_issues:
        console.print(f"[bold yellow]Summary: {len(all_issues)} issue(s) found[/bold yellow]")
        for issue in all_issues:
            console.print(f"  {WARN} {issue}")
    else:
        console.print(f"[bold green]Summary: All checks passed {CHECK}[/bold green]")
    console.print()


@with_django
def doctor_command(
    format: OutputFormat = FormatOption,
    check: bool = typer.Option(
        False, "--check", "-c", help="Exit with code 1 if issues found (for CI)"
    ),
):
    """Run diagnostic checks on project configuration and health."""
    # Collect all diagnostic data
    report = {
        "config_files": check_config_files(),
        "environment": check_environment(),
        "api_keys": check_api_keys(),
        "llm_config": check_llm_config(),
        "database": check_database(),
        "file_search": check_file_search(),
        "media": check_media(),
        "ports": check_ports(),
        "workers": check_workers(),
    }

    # Aggregate all issues
    all_issues = []
    for key, section in report.items():
        if isinstance(section, dict) and "issues" in section:
            all_issues.extend(section["issues"])
    report["all_issues"] = all_issues

    # Output report
    output_report(report, format)

    # Exit with error if --check and issues found
    if check and all_issues:
        raise typer.Exit(code=1)
