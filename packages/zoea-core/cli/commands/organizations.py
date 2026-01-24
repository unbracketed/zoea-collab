"""Organization management commands."""

import json

import typer
from rich.panel import Panel

from cli.utils.django_context import with_django
from cli.utils.formatting import (
    FormatOption,
    OutputFormat,
    console,
    format_timestamp,
    output_item,
    output_list,
    print_error,
    print_json,
)

# Create organizations command group
organizations_app = typer.Typer(
    name="organizations",
    help="Manage organizations",
    rich_markup_mode="rich",
)


@organizations_app.callback(invoke_without_command=True)
def organizations_callback(ctx: typer.Context):
    """Organizations command group."""
    if ctx.invoked_subcommand is None:
        list_organizations()


@organizations_app.command(name="list")
@with_django
def list_organizations(
    active: bool | None = typer.Option(
        None, "--active/--inactive", help="Filter by active status"
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed information"),
    format: OutputFormat = FormatOption,
):
    """List organizations."""
    from accounts.models import Account

    queryset = Account.objects.all().prefetch_related("users")
    if active is not None:
        queryset = queryset.filter(is_active=active)

    if not queryset.exists():
        if format == OutputFormat.JSON:
            print_json([])
        else:
            console.print("No organizations found.", style="yellow")
        return

    def build_json(org):
        created_at = getattr(org, "created", None)
        updated_at = getattr(org, "modified", None)
        data = {
            "id": org.id,
            "name": org.name,
            "slug": getattr(org, "slug", None),
            "is_active": getattr(org, "is_active", None),
            "subscription_plan": getattr(org, "subscription_plan", None),
            "billing_email": getattr(org, "billing_email", None),
            "max_users": getattr(org, "max_users", None),
            "user_count": org.users.count() if hasattr(org, "users") else None,
            "created_at": created_at.isoformat() if created_at else None,
            "updated_at": updated_at.isoformat() if updated_at else None,
        }
        if verbose:
            data["settings"] = getattr(org, "settings", {}) or {}
        return data

    def build_row(org):
        user_count = org.users.count() if hasattr(org, "users") else 0
        status = "active" if getattr(org, "is_active", True) else "inactive"
        row = [
            org.name,
            getattr(org, "slug", "-"),
            getattr(org, "subscription_plan", "-") or "-",
            f"{user_count}/{getattr(org, 'max_users', '-')}",
            status,
        ]
        if verbose:
            row.append(format_timestamp(getattr(org, "created", None)))
            row.append(str(org.id))
        return row

    columns = [
        ("Name", "cyan", True),
        ("Slug", "yellow"),
        ("Plan", "green"),
        ("Users", "magenta"),
        ("Status", "white"),
    ]
    if verbose:
        columns.extend([("Created", "dim"), ("ID", "dim")])

    output_list(
        items=list(queryset),
        format=format,
        table_title="Organizations",
        columns=columns,
        row_builder=build_row,
        json_builder=build_json,
    )


@organizations_app.command(name="show")
@with_django
def show_organization(
    organization: str = typer.Argument(..., help="Organization name, slug, or ID"),
    format: OutputFormat = FormatOption,
):
    """Show details for an organization."""
    from accounts.models import Account

    queryset = Account.objects.all().prefetch_related("users")

    found = None
    try:
        org_id = int(organization)
        found = queryset.get(id=org_id)
    except (ValueError, Account.DoesNotExist):
        pass

    if not found:
        matches = queryset.filter(slug=organization)
        if not matches.exists():
            matches = queryset.filter(name=organization)
        if not matches.exists():
            print_error(f"Organization not found: {organization}")
            raise typer.Exit(code=1)
        if matches.count() > 1:
            print_error(
                f"Multiple organizations found with name '{organization}'. Use ID."
            )
            raise typer.Exit(code=1)
        found = matches.first()

    def build_json(org):
        created_at = getattr(org, "created", None)
        updated_at = getattr(org, "modified", None)
        return {
            "id": org.id,
            "name": org.name,
            "slug": getattr(org, "slug", None),
            "is_active": getattr(org, "is_active", None),
            "subscription_plan": getattr(org, "subscription_plan", None),
            "billing_email": getattr(org, "billing_email", None),
            "max_users": getattr(org, "max_users", None),
            "user_count": org.users.count() if hasattr(org, "users") else None,
            "settings": getattr(org, "settings", {}) or {},
            "created_at": created_at.isoformat() if created_at else None,
            "updated_at": updated_at.isoformat() if updated_at else None,
        }

    def build_panel(org):
        created_at = getattr(org, "created", None)
        updated_at = getattr(org, "modified", None)
        settings_text = json.dumps(getattr(org, "settings", {}) or {}, indent=2)
        details = f"""
[bold cyan]Name:[/] {org.name}
[bold yellow]Slug:[/] {getattr(org, "slug", "N/A")}
[bold green]Status:[/] {"active" if getattr(org, "is_active", True) else "inactive"}
[bold magenta]Plan:[/] {getattr(org, "subscription_plan", "N/A")}
[bold white]Billing Email:[/] {getattr(org, "billing_email", "N/A") or "N/A"}
[bold white]Users:[/] {org.users.count() if hasattr(org, "users") else "N/A"} / {getattr(org, "max_users", "N/A")}

[bold white]Settings:[/]
{settings_text}

[bold white]Metadata:[/]
  Created: {format_timestamp(created_at)}
  Updated: {format_timestamp(updated_at)}
  ID: {org.id}
"""
        console.print(Panel(details, title="Organization"))

    output_item(found, format=format, panel_builder=build_panel, json_builder=build_json)
