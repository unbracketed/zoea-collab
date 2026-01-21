"""Workspace management commands."""

import typer
from django.apps import apps
from rich.panel import Panel
from rich.tree import Tree

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
)

# Create workspaces command group
workspaces_app = typer.Typer(
    name="workspaces",
    help="Manage workspaces",
    rich_markup_mode="rich",
)


@workspaces_app.callback(invoke_without_command=True)
def workspaces_callback(ctx: typer.Context):
    """Workspaces command group."""
    if ctx.invoked_subcommand is None:
        # Default to list command
        list_workspaces()


@workspaces_app.command(name="list")
@with_django
def list_workspaces(
    org: str | None = typer.Option(
        None, "--org", "-o", help="Filter by organization name"
    ),
    project: str | None = typer.Option(
        None, "--project", "-p", help="Filter by project name"
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed information"),
    format: OutputFormat = FormatOption,
):
    """List all workspaces."""
    try:
        Workspace = apps.get_model("workspaces", "Workspace")
        Project = apps.get_model("projects", "Project")
        Organization = apps.get_model("organizations", "Organization")

        # Build query
        workspaces = Workspace.objects.all().select_related("project", "project__organization")

        # Apply organization filter
        org_name = get_organization_filter(org)
        if org_name:
            try:
                organization = Organization.objects.get(name=org_name)
                workspaces = workspaces.filter(project__organization=organization)
            except Organization.DoesNotExist:
                print_error(f"Organization not found: {org_name}")
                raise typer.Exit(code=1)

        # Apply project filter
        if project:
            try:
                project_obj = Project.objects.get(name=project)
                workspaces = workspaces.filter(project=project_obj)
            except Project.DoesNotExist:
                print_error(f"Project not found: {project}")
                raise typer.Exit(code=1)

        if not workspaces.exists():
            if format == OutputFormat.JSON:
                print_json([])
            else:
                console.print("No workspaces found.", style="yellow")
            return

        def build_json(ws):
            data = {
                "id": ws.id,
                "name": ws.name,
                "project": ws.project.name,
                "organization": ws.project.organization.name,
                "full_path": ws.get_full_path(),
                "created_at": ws.created_at.isoformat() if ws.created_at else None,
            }
            if verbose:
                data["description"] = ws.description
                data["parent_id"] = ws.parent_id
            return data

        def build_row(ws):
            row = [
                ws.name,
                ws.project.name,
                ws.get_full_path(),
                format_date(ws.created_at),
            ]
            if verbose:
                description = ws.description or ""
                if len(description) > 50:
                    description = description[:47] + "..."
                row.extend([description, str(ws.id)])
            return row

        columns = [
            ("Name", "cyan", True),
            ("Project", "yellow"),
            ("Path", "green"),
            ("Created", "blue"),
        ]
        if verbose:
            columns.extend([("Description", "white"), ("ID", "dim")])

        output_list(
            items=list(workspaces),
            format=format,
            table_title="Workspaces",
            columns=columns,
            row_builder=build_row,
            json_builder=build_json,
        )

    except typer.Exit:
        raise
    except Exception as e:
        print_error(f"Error listing workspaces: {e}")
        raise typer.Exit(code=1)


@workspaces_app.command(name="show")
@with_django
def show_workspace(
    workspace_id: int = typer.Argument(..., help="Workspace ID"),
    format: OutputFormat = FormatOption,
):
    """Show detailed information about a workspace."""
    try:
        Workspace = apps.get_model("workspaces", "Workspace")

        try:
            workspace = Workspace.objects.select_related(
                "project", "project__organization", "parent", "created_by"
            ).get(id=workspace_id)
        except Workspace.DoesNotExist:
            print_error(f"Workspace not found: {workspace_id}")
            raise typer.Exit(code=1)

        children = list(workspace.get_children())

        def build_json(ws):
            return {
                "id": ws.id,
                "name": ws.name,
                "project": ws.project.name,
                "organization": ws.project.organization.name,
                "full_path": ws.get_full_path(),
                "description": ws.description,
                "parent_id": ws.parent_id,
                "parent_name": ws.parent.name if ws.parent else None,
                "created_at": ws.created_at.isoformat() if ws.created_at else None,
                "updated_at": ws.updated_at.isoformat() if ws.updated_at else None,
                "created_by": ws.created_by.username if ws.created_by else None,
                "children": [
                    {"id": c.id, "name": c.name, "created_at": c.created_at.isoformat()}
                    for c in children
                ],
            }

        def build_panel(ws):
            details = f"""
[bold cyan]Name:[/] {ws.name}
[bold yellow]Project:[/] {ws.project.name}
[bold magenta]Organization:[/] {ws.project.organization.name}
[bold green]Full Path:[/] {ws.get_full_path()}

[bold white]Description:[/]
{ws.description or 'N/A'}

[bold blue]Hierarchy:[/]
  Parent: {ws.parent.name if ws.parent else 'None (Root workspace)'}

[bold white]Metadata:[/]
  Created: {format_timestamp(ws.created_at)}
  Updated: {format_timestamp(ws.updated_at)}
  Created By: {ws.created_by.username if ws.created_by else 'N/A'}
  ID: {ws.id}
"""
            panel = Panel(details, title=f"Workspace: {ws.name}", border_style="cyan")
            console.print(panel)

            if children:
                console.print(f"\n[bold]Child Workspaces:[/] {len(children)}")
                table = create_table("Children", [("Name", "cyan"), ("Created", "green")])
                for child in children:
                    table.add_row(child.name, format_date(child.created_at))
                console.print(table)

        output_item(
            item=workspace,
            format=format,
            panel_builder=build_panel,
            json_builder=build_json,
        )

    except typer.Exit:
        raise
    except Exception as e:
        print_error(f"Error showing workspace: {e}")
        raise typer.Exit(code=1)


@workspaces_app.command(name="tree")
@with_django
def show_workspace_tree(
    project_name: str = typer.Argument(..., help="Project name"),
    org: str | None = typer.Option(None, "--org", "-o", help="Organization name"),
    format: OutputFormat = FormatOption,
):
    """Show workspace hierarchy as a tree."""
    try:
        Project = apps.get_model("projects", "Project")
        Workspace = apps.get_model("workspaces", "Workspace")
        Organization = apps.get_model("organizations", "Organization")

        # Find project
        projects = Project.objects.filter(name=project_name)

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
            print_error(f"Project not found: {project_name}")
            raise typer.Exit(code=1)

        if projects.count() > 1:
            print_error(
                f"Multiple projects found with name '{project_name}'. "
                "Please specify --org."
            )
            raise typer.Exit(code=1)

        project = projects.first()

        # Get all workspaces for the project
        workspaces = Workspace.objects.filter(project=project).select_related("parent")

        if not workspaces.exists():
            if format == OutputFormat.JSON:
                print_json({"project": project.name, "workspaces": []})
            else:
                console.print(f"No workspaces found for project: {project_name}", style="yellow")
            return

        root_workspaces = workspaces.filter(parent=None)

        if format == OutputFormat.JSON:
            # Build nested JSON structure
            def build_tree_json(ws):
                return {
                    "id": ws.id,
                    "name": ws.name,
                    "description": ws.description,
                    "full_path": ws.get_full_path(),
                    "children": [build_tree_json(c) for c in ws.get_children()],
                }

            tree_data = {
                "project": project.name,
                "organization": project.organization.name,
                "total_workspaces": workspaces.count(),
                "workspaces": [build_tree_json(ws) for ws in root_workspaces],
            }
            print_json(tree_data)
        else:
            # Create tree visualization
            tree = Tree(
                f"[bold cyan]{project.name}[/] ([yellow]{project.organization.name}[/])",
                guide_style="blue",
            )

            def add_workspace_to_tree(parent_tree, workspace):
                """Recursively add workspace and children to tree."""
                workspace_label = f"[cyan]{workspace.name}[/]"
                if workspace.description:
                    desc_preview = workspace.description[:30] + (
                        "..." if len(workspace.description) > 30 else ""
                    )
                    workspace_label += f" [dim]({desc_preview})[/]"

                branch = parent_tree.add(workspace_label)

                for child in workspace.get_children():
                    add_workspace_to_tree(branch, child)

            for root_workspace in root_workspaces:
                add_workspace_to_tree(tree, root_workspace)

            console.print(tree)
            console.print(f"\n[bold]Total workspaces:[/] {workspaces.count()}")

    except typer.Exit:
        raise
    except Exception as e:
        print_error(f"Error showing workspace tree: {e}")
        raise typer.Exit(code=1)
