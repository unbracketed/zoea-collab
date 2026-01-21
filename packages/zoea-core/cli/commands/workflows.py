"""Workflow management and run commands."""

import asyncio
from pathlib import Path
from typing import List, Optional

import typer
from rich.panel import Panel

from cli.utils.config import get_organization_filter
from cli.utils.django_context import with_django
from cli.utils.formatting import (
    console,
    create_table,
    print_error,
    print_info,
    print_success,
)

# Create workflows command group
workflows_app = typer.Typer(
    name="workflows",
    help="Manage and run workflows",
    rich_markup_mode="rich",
)


@workflows_app.callback(invoke_without_command=True)
def workflows_callback(ctx: typer.Context):
    """Workflows command group."""
    if ctx.invoked_subcommand is None:
        list_workflows()


@workflows_app.command(name="list")
@with_django
def list_workflows():
    """List available workflows."""
    from workflows.config import discover_builtin_workflows, load_workflow_config

    # Discover built-in workflows
    workflows_base = Path(__file__).parent.parent.parent / "workflows"
    workflows = discover_builtin_workflows(workflows_base)

    if not workflows:
        console.print("No workflows found.", style="yellow")
        return

    table = create_table(
        "Available Workflows",
        [("Slug", "cyan", True), ("Name", "yellow"), ("Inputs", "green"), ("Description", "white")],
    )

    for slug, config_path in workflows.items():
        try:
            spec = load_workflow_config(config_path)
            inputs_str = ", ".join(inp.name for inp in spec.inputs)
            table.add_row(
                slug,
                spec.name or slug,
                inputs_str or "-",
                (spec.description[:40] + "...") if len(spec.description) > 40 else spec.description,
            )
        except Exception as e:
            table.add_row(slug, "[red]Error[/red]", "-", str(e)[:40])

    console.print(table)


@workflows_app.command(name="show")
@with_django
def show_workflow(
    workflow: str = typer.Argument(..., help="Workflow slug"),
):
    """Show details of a workflow."""
    from workflows.config import discover_builtin_workflows, load_workflow_config

    # Find workflow config
    workflows_base = Path(__file__).parent.parent.parent / "workflows"
    workflows = discover_builtin_workflows(workflows_base)

    # Try exact match first, then with underscores
    config_path = workflows.get(workflow) or workflows.get(workflow.replace("-", "_"))

    if not config_path:
        print_error(f"Workflow not found: {workflow}")
        console.print(f"Available workflows: {', '.join(workflows.keys())}", style="dim")
        raise typer.Exit(code=1)

    try:
        spec = load_workflow_config(config_path)
    except Exception as e:
        print_error(f"Failed to load workflow config: {e}")
        raise typer.Exit(code=1)

    # Build details panel
    details = f"""
[bold cyan]Slug:[/] {spec.slug}
[bold yellow]Name:[/] {spec.name or spec.slug}
[bold white]Description:[/] {spec.description or 'N/A'}

[bold green]Inputs:[/]
"""
    for inp in spec.inputs:
        req_str = " [red](required)[/red]" if inp.required else " [dim](optional)[/dim]"
        details += f"  - [cyan]{inp.name}[/cyan]: {inp.type}{req_str}\n"
        if inp.description:
            details += f"    [dim]{inp.description}[/dim]\n"

    details += "\n[bold blue]Outputs:[/]\n"
    for out in spec.outputs:
        details += f"  - [cyan]{out.name}[/cyan]: {out.type}\n"
        if out.target:
            details += f"    [dim]Target: {out.target}[/dim]\n"

    details += "\n[bold magenta]Services:[/]\n"
    for svc in spec.services:
        config_str = ""
        if svc.config:
            config_str = f" [dim]({', '.join(f'{k}={v}' for k, v in svc.config.items())})[/dim]"
        details += f"  - [cyan]{svc.name}[/cyan] as '{svc.ctxref}'{config_str}\n"

    console.print(Panel(details, title=f"Workflow: {workflow}"))


@workflows_app.command(name="run")
@with_django
def run_workflow(
    workflow: str = typer.Argument(..., help="Workflow slug to run"),
    inputs: Optional[List[str]] = typer.Argument(
        None, help="Input values as key=value pairs (e.g., issue_number=7)"
    ),
    project: Optional[str] = typer.Option(None, "--project", "-p", help="Project name"),
    workspace: Optional[str] = typer.Option(None, "--workspace", "-w", help="Workspace name"),
    org: Optional[str] = typer.Option(None, "--org", "-o", help="Organization name"),
    user_id: Optional[int] = typer.Option(None, "--user", "-u", help="User ID to run workflow as"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what would run without running"),
):
    """
    Run a workflow.

    Example:
        zoea workflows run plan_github_issue issue_number=7
        zoea workflows run summarize_content --user 1
    """
    from django.apps import apps

    from accounts.utils import get_user_organization
    from workflows.config import discover_builtin_workflows
    from workflows.runner import WorkflowRunner

    Project = apps.get_model("projects", "Project")
    Workspace = apps.get_model("workspaces", "Workspace")
    User = apps.get_model("auth", "User")

    # Get user for CLI context
    from django.conf import settings

    if user_id:
        # Explicit user ID provided
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            print_error(f"User not found with ID: {user_id}")
            raise typer.Exit(code=1)
    elif settings.DEBUG:
        # Local/single-user mode: auto-select first user with organization membership
        from organizations.models import OrganizationUser

        org_user = OrganizationUser.objects.select_related("user").first()
        if org_user:
            user = org_user.user
        else:
            user = User.objects.filter(is_active=True).first()
        if not user:
            print_error("No user found. Run 'python manage.py initialize_local_user' first.")
            raise typer.Exit(code=1)
    else:
        # Production: require explicit user
        print_error("--user is required. Specify the user ID to run the workflow as.")
        raise typer.Exit(code=1)

    # Get organization
    org_name = get_organization_filter(org)
    if org_name:
        Organization = apps.get_model("organizations", "Organization")
        try:
            organization = Organization.objects.get(name=org_name)
        except Organization.DoesNotExist:
            print_error(f"Organization not found: {org_name}")
            raise typer.Exit(code=1)
    else:
        organization = get_user_organization(user)
        if not organization:
            print_error("User has no organization. Specify --org or run initialize_local_user.")
            raise typer.Exit(code=1)

    # Get project
    try:
        if project:
            proj = Project.objects.get(name=project, organization=organization)
        else:
            proj = Project.objects.filter(organization=organization).first()
            if not proj:
                print_error("No projects found. Create a project first or specify --project.")
                raise typer.Exit(code=1)
    except Project.DoesNotExist:
        print_error(f"Project not found: {project}")
        raise typer.Exit(code=1)

    # Get workspace
    try:
        if workspace:
            ws = Workspace.objects.get(name=workspace, project=proj)
        else:
            ws = Workspace.objects.filter(project=proj).first()
            if not ws:
                print_error("No workspaces found. Create a workspace first or specify --workspace.")
                raise typer.Exit(code=1)
    except Workspace.DoesNotExist:
        print_error(f"Workspace not found: {workspace}")
        raise typer.Exit(code=1)

    # Parse inputs
    input_dict = {}
    if inputs:
        for inp in inputs:
            if "=" in inp:
                key, value = inp.split("=", 1)
                # Try to convert to int
                try:
                    value = int(value)
                except ValueError:
                    pass
                input_dict[key] = value
            else:
                print_error(f"Invalid input format: {inp}. Use key=value format.")
                raise typer.Exit(code=1)

    # Find workflow config
    workflows_base = Path(__file__).parent.parent.parent / "workflows"
    workflows = discover_builtin_workflows(workflows_base)
    config_path = workflows.get(workflow) or workflows.get(workflow.replace("-", "_"))

    if not config_path:
        print_error(f"Workflow not found: {workflow}")
        raise typer.Exit(code=1)

    if dry_run:
        console.print(
            Panel(
                f"""
[bold cyan]Workflow:[/] {workflow}
[bold magenta]User:[/] {user.username} (id={user.id})
[bold yellow]Organization:[/] {organization.name}
[bold yellow]Project:[/] {proj.name}
[bold yellow]Workspace:[/] {ws.name}
[bold green]Inputs:[/] {input_dict or '(none)'}
[bold blue]Config:[/] {config_path}
        """,
                title="Dry Run",
            )
        )
        return

    print_info(f"Running workflow: {workflow}")
    console.print(f"  Project: {proj.name}", style="dim")
    console.print(f"  Workspace: {ws.name}", style="dim")
    console.print(f"  Inputs: {input_dict}", style="dim")

    runner = WorkflowRunner(
        organization=organization,
        project=proj,
        workspace=ws,
        user=user,
    )

    try:
        result = asyncio.run(runner.run(workflow, input_dict, config_path))
        print_success(f"Workflow completed! Run ID: {result['run_id']}")

        if result.get("outputs"):
            console.print("\n[bold]Outputs:[/bold]")
            for key, value in result["outputs"].items():
                if isinstance(value, dict):
                    console.print(f"  {key}:")
                    for k, v in value.items():
                        console.print(f"    {k}: {v}", style="dim")
                else:
                    console.print(f"  {key}: {value}")

    except Exception as e:
        print_error(f"Workflow failed: {e}")
        raise typer.Exit(code=1)
