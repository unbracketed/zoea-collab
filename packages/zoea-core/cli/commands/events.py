"""Event trigger management commands."""

import json

import typer
from rich.panel import Panel

from cli.utils.config import get_organization_filter
from cli.utils.django_context import with_django
from cli.utils.formatting import (
    FormatOption,
    OutputFormat,
    console,
    format_date,
    format_timestamp,
    output_item,
    output_list,
    print_error,
    print_json,
)

# Create events command group
events_app = typer.Typer(
    name="events",
    help="Manage event triggers",
    rich_markup_mode="rich",
)


def _resolve_organization(org_flag: str | None):
    from django.apps import apps

    Organization = apps.get_model("organizations", "Organization")
    org_name = get_organization_filter(org_flag)
    if not org_name:
        return None
    try:
        return Organization.objects.get(name=org_name)
    except Organization.DoesNotExist:
        print_error(f"Organization not found: {org_name}")
        raise typer.Exit(code=1)


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


@events_app.callback(invoke_without_command=True)
def events_callback(ctx: typer.Context):
    """Events command group."""
    if ctx.invoked_subcommand is None:
        list_event_triggers()


@events_app.command(name="list")
@with_django
def list_event_triggers(
    org: str | None = typer.Option(
        None, "--org", "-o", help="Filter by organization name"
    ),
    project: str | None = typer.Option(
        None, "--project", "-p", help="Filter by project name or ID"
    ),
    event_type: str | None = typer.Option(
        None, "--event-type", "-t", help="Filter by event type"
    ),
    enabled: bool | None = typer.Option(
        None, "--enabled/--disabled", help="Filter by enabled status"
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed information"),
    format: OutputFormat = FormatOption,
):
    """List event triggers."""
    from events.models import EventTrigger, EventType

    organization = _resolve_organization(org)
    project_obj = _resolve_project(project, organization)

    triggers = EventTrigger.objects.select_related("project", "organization", "created_by")

    if organization:
        triggers = triggers.filter(organization=organization)

    if project_obj:
        triggers = triggers.filter(project=project_obj)

    if event_type:
        valid_types = [event.value for event in EventType]
        if event_type not in valid_types:
            print_error(f"Invalid event type: {event_type}")
            console.print(f"Valid event types: {', '.join(valid_types)}", style="dim")
            raise typer.Exit(code=1)
        triggers = triggers.filter(event_type=event_type)

    if enabled is not None:
        triggers = triggers.filter(is_enabled=enabled)

    if not triggers.exists():
        if format == OutputFormat.JSON:
            print_json([])
        else:
            console.print("No event triggers found.", style="yellow")
        return

    def build_json(trigger):
        data = {
            "id": trigger.id,
            "name": trigger.name,
            "description": trigger.description,
            "event_type": trigger.event_type,
            "project_id": trigger.project_id,
            "project_name": trigger.project.name if trigger.project else None,
            "is_enabled": trigger.is_enabled,
            "run_async": trigger.run_async,
            "skills": trigger.skills or [],
            "skill_count": trigger.skill_count,
            "created_at": trigger.created_at.isoformat() if trigger.created_at else None,
            "updated_at": trigger.updated_at.isoformat() if trigger.updated_at else None,
            "created_by": trigger.created_by.username if trigger.created_by else None,
            "created_by_id": trigger.created_by_id,
        }
        if verbose:
            data["filters"] = trigger.filters or {}
            data["agent_config"] = trigger.agent_config or {}
        return data

    def build_row(trigger):
        project_name = trigger.project.name if trigger.project else "org-wide"
        skills_display = (
            ", ".join(trigger.skills) if verbose else str(trigger.skill_count)
        )
        enabled_display = "[green]yes[/green]" if trigger.is_enabled else "[red]no[/red]"
        row = [
            trigger.name,
            trigger.event_type,
            project_name,
            skills_display or "-",
            enabled_display,
        ]
        if verbose:
            row.extend(
                [
                    "async" if trigger.run_async else "sync",
                    format_date(trigger.created_at),
                    str(trigger.id),
                ]
            )
        return row

    columns = [
        ("Name", "cyan", True),
        ("Event Type", "yellow"),
        ("Project", "green"),
        ("Skills", "magenta"),
        ("Enabled", "white"),
    ]
    if verbose:
        columns.extend(
            [
                ("Mode", "blue"),
                ("Created", "dim"),
                ("ID", "dim"),
            ]
        )

    output_list(
        items=list(triggers),
        format=format,
        table_title="Event Triggers",
        columns=columns,
        row_builder=build_row,
        json_builder=build_json,
    )


@events_app.command(name="show")
@with_django
def show_event_trigger(
    trigger: str = typer.Argument(..., help="Event trigger name or ID"),
    org: str | None = typer.Option(None, "--org", "-o", help="Organization name"),
    project: str | None = typer.Option(
        None, "--project", "-p", help="Project name or ID"
    ),
    format: OutputFormat = FormatOption,
):
    """Show details for an event trigger."""
    from events.models import EventTrigger

    organization = _resolve_organization(org)
    project_obj = _resolve_project(project, organization)

    triggers = EventTrigger.objects.select_related("project", "organization", "created_by")

    if organization:
        triggers = triggers.filter(organization=organization)

    if project_obj:
        triggers = triggers.filter(project=project_obj)

    try:
        trigger_id = int(trigger)
        found = triggers.get(id=trigger_id)
    except (ValueError, EventTrigger.DoesNotExist):
        matches = triggers.filter(name=trigger)
        if not matches.exists():
            print_error(f"Event trigger not found: {trigger}")
            raise typer.Exit(code=1)
        if matches.count() > 1:
            print_error(
                f"Multiple triggers found with name '{trigger}'. "
                "Please specify --org/--project or use trigger ID."
            )
            raise typer.Exit(code=1)
        found = matches.first()

    def build_json(item):
        return {
            "id": item.id,
            "name": item.name,
            "description": item.description,
            "event_type": item.event_type,
            "project_id": item.project_id,
            "project_name": item.project.name if item.project else None,
            "is_enabled": item.is_enabled,
            "run_async": item.run_async,
            "skills": item.skills or [],
            "skill_count": item.skill_count,
            "filters": item.filters or {},
            "agent_config": item.agent_config or {},
            "created_at": item.created_at.isoformat() if item.created_at else None,
            "updated_at": item.updated_at.isoformat() if item.updated_at else None,
            "created_by": item.created_by.username if item.created_by else None,
            "created_by_id": item.created_by_id,
        }

    def build_panel(item):
        project_name = item.project.name if item.project else "org-wide"
        skills = item.skills or []
        skills_text = "\n".join(f"  - {name}" for name in skills) if skills else "  - none"
        filters_text = json.dumps(item.filters or {}, indent=2)
        agent_config_text = json.dumps(item.agent_config or {}, indent=2)

        details = f"""
[bold cyan]Name:[/] {item.name}
[bold yellow]Event Type:[/] {item.event_type}
[bold green]Project:[/] {project_name}
[bold magenta]Enabled:[/] {"yes" if item.is_enabled else "no"}
[bold blue]Run Mode:[/] {"async" if item.run_async else "sync"}

[bold white]Description:[/]
{item.description or "N/A"}

[bold white]Skills:[/]
{skills_text}

[bold white]Filters:[/]
{filters_text}

[bold white]Agent Config:[/]
{agent_config_text}

[bold white]Metadata:[/]
  Created: {format_timestamp(item.created_at)}
  Updated: {format_timestamp(item.updated_at)}
  Created By: {item.created_by.username if item.created_by else "N/A"}
  ID: {item.id}
"""
        console.print(Panel(details, title="Event Trigger"))

    output_item(found, format=format, panel_builder=build_panel, json_builder=build_json)
