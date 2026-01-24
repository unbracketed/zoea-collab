"""Agent skills commands."""

import json

import typer
from rich.panel import Panel

from cli.utils.django_context import with_django
from cli.utils.formatting import (
    FormatOption,
    OutputFormat,
    console,
    output_item,
    output_list,
    print_error,
    print_json,
)

# Create skills command group
skills_app = typer.Typer(
    name="skills",
    help="List registered agent skills",
    rich_markup_mode="rich",
)


@skills_app.callback(invoke_without_command=True)
def skills_callback(ctx: typer.Context):
    """Skills command group."""
    if ctx.invoked_subcommand is None:
        list_skills()


@skills_app.command(name="list")
@with_django
def list_skills(
    context: str | None = typer.Option(
        None, "--context", "-c", help="Filter by supported context"
    ),
    refresh: bool = typer.Option(
        False, "--refresh", help="Rescan skill directories before listing"
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed information"),
    format: OutputFormat = FormatOption,
):
    """List registered agent skills."""
    from agents.skills import SkillRegistry

    registry = SkillRegistry.get_instance()
    skills = registry.list_skills(context=context, refresh=refresh)

    if not skills:
        if format == OutputFormat.JSON:
            print_json([])
        else:
            console.print("No skills found.", style="yellow")
        return

    def build_json(skill):
        data = {
            "name": skill.name,
            "description": skill.description,
            "license": skill.license,
            "compatibility": skill.compatibility,
            "allowed_tools": skill.allowed_tools,
            "supported_contexts": skill.supported_contexts,
            "metadata": skill.metadata,
        }
        if verbose:
            data["root"] = str(skill.root)
            data["skill_path"] = str(skill.skill_path)
        return data

    def build_row(skill):
        description = skill.description or ""
        description = (
            f"{description[:60]}..." if len(description) > 60 else description
        )
        contexts = ", ".join(skill.supported_contexts) or "*"
        row = [skill.name, description, contexts]
        if verbose:
            allowed_tools = ", ".join(skill.allowed_tools) if skill.allowed_tools else "-"
            license_value = skill.license or "-"
            row.extend([allowed_tools, license_value])
        return row

    columns = [
        ("Name", "cyan", True),
        ("Description", "white"),
        ("Contexts", "green"),
    ]
    if verbose:
        columns.extend([("Allowed Tools", "yellow"), ("License", "magenta")])

    output_list(
        items=list(skills),
        format=format,
        table_title="Registered Skills",
        columns=columns,
        row_builder=build_row,
        json_builder=build_json,
    )


@skills_app.command(name="show")
@with_django
def show_skill(
    name: str = typer.Argument(..., help="Skill name"),
    refresh: bool = typer.Option(
        False, "--refresh", help="Rescan skill directories before lookup"
    ),
    show_paths: bool = typer.Option(
        False, "--show-paths", help="Include skill file locations"
    ),
    format: OutputFormat = FormatOption,
):
    """Show details for a specific skill."""
    from agents.skills import SkillRegistry

    registry = SkillRegistry.get_instance()
    if refresh:
        registry.list_skills(refresh=True)
    skill = registry.get_skill(name)

    if not skill:
        print_error(f"Skill not found: {name}")
        raise typer.Exit(code=1)

    def build_json(item):
        data = {
            "name": item.name,
            "description": item.description,
            "license": item.license,
            "compatibility": item.compatibility,
            "allowed_tools": item.allowed_tools,
            "supported_contexts": item.supported_contexts,
            "metadata": item.metadata,
        }
        if show_paths:
            data["root"] = str(item.root)
            data["skill_path"] = str(item.skill_path)
        return data

    def build_panel(item):
        metadata_text = json.dumps(item.metadata or {}, indent=2)
        allowed_tools = ", ".join(item.allowed_tools) if item.allowed_tools else "N/A"
        contexts = ", ".join(item.supported_contexts) or "*"
        details = f"""
[bold cyan]Name:[/] {item.name}
[bold yellow]Description:[/] {item.description}
[bold green]Contexts:[/] {contexts}
[bold magenta]Allowed Tools:[/] {allowed_tools}
[bold white]License:[/] {item.license or "N/A"}
[bold white]Compatibility:[/] {item.compatibility or "N/A"}

[bold white]Metadata:[/]
{metadata_text}
"""
        if show_paths:
            details += f"""
[bold white]Locations:[/]
  Root: {item.root}
  SKILL.md: {item.skill_path}
"""
        console.print(Panel(details, title="Skill"))

    output_item(skill, format=format, panel_builder=build_panel, json_builder=build_json)
