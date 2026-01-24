"""Webhook connection management commands."""

import json
import uuid

import typer
from rich.panel import Panel

from cli.utils.config import get_organization_filter
from cli.utils.django_context import with_django
from cli.utils.formatting import (
    FormatOption,
    OutputFormat,
    console,
    format_timestamp,
    get_status_color,
    output_item,
    output_list,
    print_error,
    print_json,
    print_success,
)

# Create webhooks command group
webhooks_app = typer.Typer(
    name="webhooks",
    help="Manage webhook connections",
    rich_markup_mode="rich",
)


def _resolve_organization(org_flag: str | None, *, required: bool):
    from django.apps import apps

    Organization = apps.get_model("organizations", "Organization")
    org_name = get_organization_filter(org_flag)
    if org_name:
        try:
            return Organization.objects.get(name=org_name)
        except Organization.DoesNotExist:
            print_error(f"Organization not found: {org_name}")
            raise typer.Exit(code=1)

    if not required:
        return None

    organizations = Organization.objects.all()
    if not organizations.exists():
        print_error("No organizations found. Run initialize_local_user first.")
        raise typer.Exit(code=1)
    if organizations.count() > 1:
        print_error("Multiple organizations found. Specify --org.")
        raise typer.Exit(code=1)
    return organizations.first()


def _resolve_project(project_value: str | None, organization):
    if not project_value:
        return None

    from django.apps import apps

    Project = apps.get_model("projects", "Project")
    projects = Project.objects.all()
    if organization:
        projects = projects.filter(organization=organization)

    try:
        project_id = int(project_value)
        return projects.get(id=project_id)
    except (ValueError, Project.DoesNotExist):
        matches = projects.filter(name=project_value)
        if not matches.exists():
            print_error(f"Project not found: {project_value}")
            raise typer.Exit(code=1)
        if matches.count() > 1:
            print_error(
                f"Multiple projects found with name '{project_value}'. Please specify --org."
            )
            raise typer.Exit(code=1)
        return matches.first()


def _find_webhook_connection(identifier: str, organization, project):
    from platform_adapters.models import PlatformConnection, PlatformType

    queryset = PlatformConnection.objects.filter(platform_type=PlatformType.WEBHOOK)
    if organization:
        queryset = queryset.filter(organization=organization)
    if project:
        queryset = queryset.filter(project=project)

    try:
        connection_id = int(identifier)
        return queryset.get(id=connection_id)
    except (ValueError, PlatformConnection.DoesNotExist):
        pass

    try:
        uuid.UUID(identifier)
        return queryset.get(connection_id=identifier)
    except (ValueError, PlatformConnection.DoesNotExist):
        pass

    matches = queryset.filter(name=identifier)
    if not matches.exists():
        print_error(f"Webhook connection not found: {identifier}")
        raise typer.Exit(code=1)
    if matches.count() > 1:
        print_error(
            f"Multiple webhook connections found with name '{identifier}'. "
            "Specify --org/--project or use ID."
        )
        raise typer.Exit(code=1)
    return matches.first()


@webhooks_app.callback(invoke_without_command=True)
def webhooks_callback(ctx: typer.Context):
    """Webhooks command group."""
    if ctx.invoked_subcommand is None:
        list_webhooks()


@webhooks_app.command(name="list")
@with_django
def list_webhooks(
    org: str | None = typer.Option(
        None, "--org", "-o", help="Filter by organization name"
    ),
    project: str | None = typer.Option(
        None, "--project", "-p", help="Filter by project name or ID"
    ),
    status: str | None = typer.Option(None, "--status", "-s", help="Filter by status"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed information"),
    format: OutputFormat = FormatOption,
):
    """List webhook connections."""
    from platform_adapters.models import PlatformConnection, PlatformType, ConnectionStatus

    organization = _resolve_organization(org, required=False)
    project_obj = _resolve_project(project, organization)

    queryset = PlatformConnection.objects.filter(platform_type=PlatformType.WEBHOOK)
    if organization:
        queryset = queryset.filter(organization=organization)
    if project_obj:
        queryset = queryset.filter(project=project_obj)
    if status:
        if status not in ConnectionStatus.values:
            print_error(f"Invalid status: {status}")
            console.print(
                f"Valid statuses: {', '.join(ConnectionStatus.values)}",
                style="dim",
            )
            raise typer.Exit(code=1)
        queryset = queryset.filter(status=status)

    if not queryset.exists():
        if format == OutputFormat.JSON:
            print_json([])
        else:
            console.print("No webhook connections found.", style="yellow")
        return

    def build_json(connection):
        data = {
            "id": connection.id,
            "connection_id": str(connection.connection_id),
            "name": connection.name,
            "description": connection.description,
            "status": connection.status,
            "status_message": connection.status_message,
            "webhook_url": connection.get_webhook_url(),
            "project_id": connection.project_id,
            "project_name": connection.project.name if connection.project else None,
            "message_count": connection.message_count,
            "last_message_at": (
                connection.last_message_at.isoformat()
                if connection.last_message_at
                else None
            ),
            "created_at": connection.created_at.isoformat(),
            "updated_at": connection.updated_at.isoformat(),
        }
        if verbose:
            data["config"] = connection.config or {}
        return data

    def build_row(connection):
        project_name = connection.project.name if connection.project else "org-wide"
        status_style = get_status_color(connection.status)
        status_text = f"[{status_style}]{connection.status}[/{status_style}]"
        row = [
            connection.name,
            status_text,
            project_name,
            str(connection.message_count),
            format_timestamp(connection.last_message_at),
            connection.get_webhook_url(),
        ]
        if verbose:
            row.extend([str(connection.id), str(connection.connection_id)])
        return row

    columns = [
        ("Name", "cyan", True),
        ("Status", "yellow"),
        ("Project", "green"),
        ("Messages", "magenta"),
        ("Last Message", "white"),
        ("Webhook URL", "blue"),
    ]
    if verbose:
        columns.extend([("ID", "dim"), ("Connection ID", "dim")])

    output_list(
        items=list(queryset),
        format=format,
        table_title="Webhook Connections",
        columns=columns,
        row_builder=build_row,
        json_builder=build_json,
    )


@webhooks_app.command(name="show")
@with_django
def show_webhook(
    connection: str = typer.Argument(..., help="Webhook connection name, ID, or UUID"),
    org: str | None = typer.Option(None, "--org", "-o", help="Organization name"),
    project: str | None = typer.Option(
        None, "--project", "-p", help="Project name or ID"
    ),
    show_secret: bool = typer.Option(
        False, "--show-secret", help="Include webhook secret in output"
    ),
    format: OutputFormat = FormatOption,
):
    """Show details for a webhook connection."""
    organization = _resolve_organization(org, required=False)
    project_obj = _resolve_project(project, organization)
    found = _find_webhook_connection(connection, organization, project_obj)

    def build_json(item):
        data = {
            "id": item.id,
            "connection_id": str(item.connection_id),
            "name": item.name,
            "description": item.description,
            "status": item.status,
            "status_message": item.status_message,
            "webhook_url": item.get_webhook_url(),
            "project_id": item.project_id,
            "project_name": item.project.name if item.project else None,
            "message_count": item.message_count,
            "last_message_at": (
                item.last_message_at.isoformat() if item.last_message_at else None
            ),
            "created_at": item.created_at.isoformat(),
            "updated_at": item.updated_at.isoformat(),
            "config": item.config or {},
        }
        if show_secret:
            data["webhook_secret"] = item.webhook_secret
        return data

    def build_panel(item):
        project_name = item.project.name if item.project else "org-wide"
        config_text = json.dumps(item.config or {}, indent=2)
        details = f"""
[bold cyan]Name:[/] {item.name}
[bold yellow]Status:[/] {item.status}
[bold green]Project:[/] {project_name}
[bold magenta]Webhook URL:[/] {item.get_webhook_url()}
[bold white]Connection ID:[/] {item.connection_id}
[bold white]Messages:[/] {item.message_count}
[bold white]Last Message:[/] {format_timestamp(item.last_message_at)}

[bold white]Description:[/]
{item.description or "N/A"}

[bold white]Status Message:[/]
{item.status_message or "N/A"}

[bold white]Config:[/]
{config_text}
"""
        if show_secret:
            details += f"""

[bold red]Webhook Secret:[/]
{item.webhook_secret}
"""
        console.print(Panel(details, title="Webhook Connection"))

    output_item(found, format=format, panel_builder=build_panel, json_builder=build_json)


@webhooks_app.command(name="create")
@with_django
def create_webhook(
    name: str = typer.Argument(..., help="Webhook connection name"),
    description: str = typer.Option("", "--description", "-d", help="Description"),
    org: str | None = typer.Option(None, "--org", "-o", help="Organization name"),
    project: str | None = typer.Option(
        None, "--project", "-p", help="Project name or ID"
    ),
    status: str = typer.Option("active", "--status", help="Connection status"),
    require_signature: bool = typer.Option(
        True,
        "--require-signature/--no-require-signature",
        help="Require HMAC signature validation",
    ),
    signature_header: str | None = typer.Option(
        None, "--signature-header", help="Signature header name"
    ),
    signature_algorithm: str | None = typer.Option(
        None, "--signature-algorithm", help="Signature algorithm (e.g. sha256)"
    ),
    field_mappings: str | None = typer.Option(
        None, "--field-mappings", help="JSON mapping of payload fields"
    ),
    config: str | None = typer.Option(
        None, "--config", help="Additional JSON config to merge"
    ),
    show_secret: bool = typer.Option(
        True, "--show-secret/--hide-secret", help="Display webhook secret"
    ),
    format: OutputFormat = FormatOption,
):
    """Create a webhook connection."""
    from platform_adapters.models import PlatformConnection, PlatformType, ConnectionStatus

    organization = _resolve_organization(org, required=True)
    project_obj = _resolve_project(project, organization)

    if status not in ConnectionStatus.values:
        print_error(f"Invalid status: {status}")
        console.print(
            f"Valid statuses: {', '.join(ConnectionStatus.values)}",
            style="dim",
        )
        raise typer.Exit(code=1)

    config_data: dict = {}
    if config:
        try:
            parsed = json.loads(config)
            if not isinstance(parsed, dict):
                raise ValueError("Config must be a JSON object")
            config_data.update(parsed)
        except (json.JSONDecodeError, ValueError) as exc:
            print_error(f"Invalid --config JSON: {exc}")
            raise typer.Exit(code=1)

    if field_mappings:
        try:
            mappings = json.loads(field_mappings)
            if not isinstance(mappings, dict):
                raise ValueError("Field mappings must be a JSON object")
            config_data["field_mappings"] = mappings
        except (json.JSONDecodeError, ValueError) as exc:
            print_error(f"Invalid --field-mappings JSON: {exc}")
            raise typer.Exit(code=1)

    if not require_signature:
        config_data["require_signature"] = False
    if signature_header:
        config_data["signature_header"] = signature_header
    if signature_algorithm:
        config_data["signature_algorithm"] = signature_algorithm

    connection = PlatformConnection.objects.create(
        organization=organization,
        project=project_obj,
        platform_type=PlatformType.WEBHOOK,
        name=name,
        description=description,
        status=status,
        config=config_data,
    )

    if format == OutputFormat.JSON:
        payload = {
            "id": connection.id,
            "connection_id": str(connection.connection_id),
            "name": connection.name,
            "description": connection.description,
            "status": connection.status,
            "webhook_url": connection.get_webhook_url(),
            "project_id": connection.project_id,
            "created_at": connection.created_at.isoformat(),
            "updated_at": connection.updated_at.isoformat(),
            "config": connection.config or {},
        }
        if show_secret:
            payload["webhook_secret"] = connection.webhook_secret
        print_json(payload)
        return

    print_success(f"Created webhook connection '{connection.name}'")
    details = f"""
[bold cyan]Name:[/] {connection.name}
[bold yellow]Status:[/] {connection.status}
[bold green]Project:[/] {connection.project.name if connection.project else "org-wide"}
[bold magenta]Webhook URL:[/] {connection.get_webhook_url()}
[bold white]Connection ID:[/] {connection.connection_id}
"""
    if show_secret:
        details += f"""
[bold red]Webhook Secret:[/]
{connection.webhook_secret}
"""
    console.print(Panel(details, title="Webhook Connection"))
