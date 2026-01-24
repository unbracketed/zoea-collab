"""Project management commands."""


import typer
from django.apps import apps
from rich.panel import Panel

from cli.utils.config import get_organization_filter
from cli.utils.django_context import with_django
from cli.utils.formatting import (
    FormatOption,
    OutputFormat,
    console,
    create_table,
    format_date,
    format_timestamp,
    output_item,
    output_list,
    print_error,
    print_json,
    print_success,
)

# Create projects command group
projects_app = typer.Typer(
    name="projects",
    help="Manage projects",
    rich_markup_mode="rich",
)


@projects_app.callback(invoke_without_command=True)
def projects_callback(ctx: typer.Context):
    """Projects command group."""
    if ctx.invoked_subcommand is None:
        # Default to list command
        list_projects()


@projects_app.command(name="list")
@with_django
def list_projects(
    org: str | None = typer.Option(
        None, "--org", "-o", help="Filter by organization name"
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed information"),
    format: OutputFormat = FormatOption,
):
    """List all projects."""
    try:
        Project = apps.get_model("projects", "Project")
        Organization = apps.get_model("organizations", "Organization")

        # Build query
        projects = Project.objects.all()

        # Apply organization filter
        org_name = get_organization_filter(org)
        if org_name:
            try:
                organization = Organization.objects.get(name=org_name)
                projects = projects.filter(organization=organization)
            except Organization.DoesNotExist:
                print_error(f"Organization not found: {org_name}")
                raise typer.Exit(code=1)

        if not projects.exists():
            if format == OutputFormat.JSON:
                print_json([])
            else:
                console.print("No projects found.", style="yellow")
            return

        # Define how to build JSON output
        def build_json(project):
            data = {
                "id": project.id,
                "name": project.name,
                "organization": project.organization.name,
                "created_at": project.created_at.isoformat() if project.created_at else None,
            }
            if verbose:
                data["description"] = project.description
                data["working_directory"] = project.working_directory
            return data

        # Define how to build table row
        def build_row(project):
            row = [
                project.name,
                project.organization.name,
                format_date(project.created_at),
            ]
            if verbose:
                row.append(str(project.id))
            return row

        # Build table columns
        columns = [
            ("Name", "cyan", True),
            ("Organization", "yellow"),
            ("Created", "green"),
        ]
        if verbose:
            columns.append(("ID", "dim"))

        output_list(
            items=list(projects),
            format=format,
            table_title="Projects",
            columns=columns,
            row_builder=build_row,
            json_builder=build_json,
        )

    except Exception as e:
        print_error(f"Error listing projects: {e}")
        raise typer.Exit(code=1)


@projects_app.command(name="show")
@with_django
def show_project(
    name: str = typer.Argument(..., help="Project name or ID"),
    org: str | None = typer.Option(None, "--org", "-o", help="Organization name"),
    format: OutputFormat = FormatOption,
):
    """Show detailed information about a project."""
    try:
        Project = apps.get_model("projects", "Project")
        Organization = apps.get_model("organizations", "Organization")

        # Try to find project by ID first, then by name
        try:
            project_id = int(name)
            project = Project.objects.get(id=project_id)
        except (ValueError, Project.DoesNotExist):
            # Search by name
            projects = Project.objects.filter(name=name)

            # Apply org filter if provided
            org_name = get_organization_filter(org)
            if org_name:
                try:
                    organization = Organization.objects.get(name=org_name)
                    projects = projects.filter(organization=organization)
                except Organization.DoesNotExist:
                    print_error(f"Organization not found: {org_name}")
                    raise typer.Exit(code=1)

            if not projects.exists():
                print_error(f"Project not found: {name}")
                raise typer.Exit(code=1)

            if projects.count() > 1:
                print_error(
                    f"Multiple projects found with name '{name}'. "
                    "Please specify --org or use project ID."
                )
                raise typer.Exit(code=1)

            project = projects.first()

        def build_json(p):
            return {
                "id": p.id,
                "name": p.name,
                "organization": p.organization.name,
                "description": p.description,
                "working_directory": p.working_directory,
                "worktree_directory": p.worktree_directory,
                "gemini_store_id": p.gemini_store_id,
                "gemini_store_name": p.gemini_store_name,
                "gemini_synced_at": p.gemini_synced_at.isoformat() if p.gemini_synced_at else None,
                "created_at": p.created_at.isoformat() if p.created_at else None,
                "updated_at": p.updated_at.isoformat() if p.updated_at else None,
                "created_by": p.created_by.username if p.created_by else None,
            }

        def build_panel(p):
            details = f"""
[bold cyan]Name:[/] {p.name}
[bold yellow]Organization:[/] {p.organization.name}
[bold green]Description:[/] {p.description or 'N/A'}

[bold magenta]Directories:[/]
  Working Directory: {p.working_directory or 'N/A'}
  Worktree Directory: {p.worktree_directory or 'N/A'}

[bold blue]Gemini Integration:[/]
  Store ID: {p.gemini_store_id or 'N/A'}
  Store Name: {p.gemini_store_name or 'N/A'}
  Last Synced: {format_timestamp(p.gemini_synced_at) if p.gemini_synced_at else 'Never'}

[bold white]Metadata:[/]
  Created: {format_timestamp(p.created_at)}
  Updated: {format_timestamp(p.updated_at)}
  Created By: {p.created_by.username if p.created_by else 'N/A'}
  ID: {p.id}
"""

            panel = Panel(details, title=f"Project: {p.name}", border_style="cyan")
            console.print(panel)

        output_item(
            item=project,
            format=format,
            panel_builder=build_panel,
            json_builder=build_json,
        )

    except Exception as e:
        print_error(f"Error showing project: {e}")
        raise typer.Exit(code=1)


@projects_app.command(name="create")
@with_django
def create_project(
    name: str = typer.Argument(..., help="Project name"),
    working_directory: str = typer.Argument(..., help="Path to the project's working directory"),
    org: str = typer.Option(
        ..., "--org", "-o", help="Organization name (required)"
    ),
    description: str = typer.Option(
        "", "--description", "-d", help="Project description"
    ),
    worktree: str = typer.Option(
        None, "--worktree", "-w", help="Path to worktree directory (if using git worktrees)"
    ),
    format: OutputFormat = FormatOption,
):
    """Create a new project."""
    try:
        Project = apps.get_model("projects", "Project")
        Organization = apps.get_model("organizations", "Organization")

        # Get organization
        org_name = get_organization_filter(org)
        if not org_name:
            print_error("Organization required. Use --org or set default_organization in config.")
            raise typer.Exit(code=1)

        try:
            organization = Organization.objects.get(name=org_name)
        except Organization.DoesNotExist:
            print_error(f"Organization not found: {org_name}")
            raise typer.Exit(code=1)

        # Check if project already exists
        if Project.objects.filter(organization=organization, name=name).exists():
            print_error(f"Project '{name}' already exists in organization '{org_name}'")
            raise typer.Exit(code=1)

        # Create the project
        project = Project.objects.create(
            organization=organization,
            name=name,
            working_directory=working_directory,
            worktree_directory=worktree,
            description=description,
        )

        if format == OutputFormat.JSON:
            print_json({
                "id": project.id,
                "name": project.name,
                "organization": project.organization.name,
                "description": project.description,
                "working_directory": project.working_directory,
                "worktree_directory": project.worktree_directory,
                "created_at": project.created_at.isoformat() if project.created_at else None,
            })
        else:
            print_success(f"Created project '{project.name}' in organization '{organization.name}'")

            # Display project details
            details = f"""
[bold cyan]Name:[/] {project.name}
[bold yellow]Organization:[/] {project.organization.name}
[bold green]Description:[/] {project.description or 'N/A'}
[bold magenta]Working Directory:[/] {project.working_directory}
[bold magenta]Worktree Directory:[/] {project.worktree_directory or 'N/A'}
[bold white]ID:[/] {project.id}
"""
            panel = Panel(details, title="New Project Created", border_style="green")
            console.print(panel)

    except typer.Exit:
        raise
    except Exception as e:
        print_error(f"Error creating project: {e}")
        raise typer.Exit(code=1)
