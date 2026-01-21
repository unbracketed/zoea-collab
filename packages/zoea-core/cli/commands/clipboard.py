"""Clipboard management commands."""

import json

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

# Create clipboard command group
clipboard_app = typer.Typer(
    name="clipboard",
    help="Manage clipboards",
    rich_markup_mode="rich",
)

clipboard_items_app = typer.Typer(
    name="item",
    help="Manage clipboard items (Yoopta-agnostic)",
    rich_markup_mode="rich",
)

# Add items as a subcommand group of clipboard
clipboard_app.add_typer(clipboard_items_app, name="item")


@clipboard_app.callback(invoke_without_command=True)
def clipboard_callback(ctx: typer.Context):
    """Clipboard command group."""
    if ctx.invoked_subcommand is None:
        # Default to list command
        list_clipboards()


@clipboard_app.command(name="list")
@with_django
def list_clipboards(
    org: str | None = typer.Option(
        None, "--org", "-o", help="Filter by organization name"
    ),
    project: str | None = typer.Option(
        None, "--project", "-p", help="Filter by project name"
    ),
    workspace: str | None = typer.Option(
        None, "--workspace", "-w", help="Filter by workspace name"
    ),
    active: bool | None = typer.Option(
        None, "--active", "-a", help="Filter by active status"
    ),
    limit: int = typer.Option(20, "--limit", "-l", help="Maximum number of results"),
    format: OutputFormat = FormatOption,
):
    """List clipboards."""
    try:
        Clipboard = apps.get_model("context_clipboards", "Clipboard")
        Organization = apps.get_model("organizations", "Organization")
        Project = apps.get_model("projects", "Project")
        Workspace = apps.get_model("workspaces", "Workspace")

        # Build query with related objects
        clipboards = Clipboard.objects.all().select_related(
            "workspace", "workspace__project", "workspace__project__organization", "owner"
        )

        # Apply organization filter
        org_name = get_organization_filter(org)
        if org_name:
            try:
                organization = Organization.objects.get(name=org_name)
                clipboards = clipboards.filter(
                    workspace__project__organization=organization
                )
            except Organization.DoesNotExist:
                print_error(f"Organization not found: {org_name}")
                raise typer.Exit(code=1)

        # Apply project filter
        if project:
            try:
                project_obj = Project.objects.get(name=project)
                clipboards = clipboards.filter(workspace__project=project_obj)
            except Project.DoesNotExist:
                print_error(f"Project not found: {project}")
                raise typer.Exit(code=1)

        # Apply workspace filter
        if workspace:
            workspaces = Workspace.objects.filter(name=workspace)
            if project:
                workspaces = workspaces.filter(project__name=project)
            if not workspaces.exists():
                print_error(f"Workspace not found: {workspace}")
                raise typer.Exit(code=1)
            clipboards = clipboards.filter(workspace__in=workspaces)

        # Apply active filter
        if active is not None:
            clipboards = clipboards.filter(is_active=active)

        # Apply limit
        clipboards = clipboards[:limit]

        if not clipboards:
            if format == OutputFormat.JSON:
                print_json([])
            else:
                console.print("No clipboards found.", style="yellow")
            return

        def build_json(cb):
            return {
                "id": cb.id,
                "name": cb.name,
                "description": cb.description or None,
                "workspace": cb.workspace.name if cb.workspace else None,
                "project": cb.workspace.project.name if cb.workspace else None,
                "owner": cb.owner.username if cb.owner else None,
                "is_active": cb.is_active,
                "is_recent": cb.is_recent,
                "item_count": cb.items.count(),
                "activated_at": cb.activated_at.isoformat() if cb.activated_at else None,
                "created_at": cb.created_at.isoformat() if cb.created_at else None,
                "updated_at": cb.updated_at.isoformat() if cb.updated_at else None,
            }

        def build_row(cb):
            status = "[green]Active[/]" if cb.is_active else (
                "[yellow]Recent[/]" if cb.is_recent else "[dim]Inactive[/]"
            )
            return [
                str(cb.id),
                cb.name,
                cb.workspace.name if cb.workspace else "N/A",
                status,
                str(cb.items.count()),
                format_date(cb.updated_at),
            ]

        columns = [
            ("ID", "dim"),
            ("Name", "cyan", True),
            ("Workspace", "green"),
            ("Status", "yellow"),
            ("Items", "blue"),
            ("Updated", "magenta"),
        ]

        output_list(
            items=list(clipboards),
            format=format,
            table_title="Clipboards",
            columns=columns,
            row_builder=build_row,
            json_builder=build_json,
        )

    except typer.Exit:
        raise
    except Exception as e:
        print_error(f"Error listing clipboards: {e}")
        raise typer.Exit(code=1)


@clipboard_app.command(name="show")
@with_django
def show_clipboard(
    clipboard_id: int = typer.Argument(..., help="Clipboard ID"),
    items: bool = typer.Option(
        False, "--items", "-i", help="Show clipboard items"
    ),
    limit: int = typer.Option(
        20, "--limit", "-l", help="Maximum items to show (with --items)"
    ),
    format: OutputFormat = FormatOption,
):
    """Show detailed information about a clipboard."""
    try:
        Clipboard = apps.get_model("context_clipboards", "Clipboard")

        try:
            clipboard = Clipboard.objects.select_related(
                "workspace", "workspace__project", "workspace__project__organization", "owner"
            ).get(id=clipboard_id)
        except Clipboard.DoesNotExist:
            print_error(f"Clipboard not found: {clipboard_id}")
            raise typer.Exit(code=1)

        # Get items if requested
        cb_items = list(clipboard.items.all()[:limit]) if items else []
        total_items = clipboard.items.count()

        def build_json(cb):
            data = {
                "id": cb.id,
                "name": cb.name,
                "description": cb.description or None,
                "workspace": cb.workspace.name if cb.workspace else None,
                "project": cb.workspace.project.name if cb.workspace else None,
                "organization": cb.workspace.project.organization.name if cb.workspace else None,
                "owner": cb.owner.username if cb.owner else None,
                "is_active": cb.is_active,
                "is_recent": cb.is_recent,
                "item_count": total_items,
                "activated_at": cb.activated_at.isoformat() if cb.activated_at else None,
                "created_at": cb.created_at.isoformat() if cb.created_at else None,
                "updated_at": cb.updated_at.isoformat() if cb.updated_at else None,
                "metadata": cb.metadata,
            }
            if items:
                data["items"] = [
                    {
                        "id": item.id,
                        "position": item.position,
                        "source_channel": item.source_channel,
                        "is_pinned": item.is_pinned,
                        "content_type": str(item.content_type) if item.content_type else None,
                        "object_id": item.object_id,
                        "virtual_node_id": item.virtual_node_id,
                        "created_at": item.created_at.isoformat(),
                    }
                    for item in cb_items
                ]
            return data

        def build_panel(cb):
            status = "Active" if cb.is_active else ("Recent" if cb.is_recent else "Inactive")
            status_color = "green" if cb.is_active else ("yellow" if cb.is_recent else "dim")

            details = f"""
[bold cyan]Name:[/] {cb.name}
[bold {status_color}]Status:[/] {status}

[bold magenta]Location:[/]
  Organization: {cb.workspace.project.organization.name if cb.workspace else 'N/A'}
  Project: {cb.workspace.project.name if cb.workspace else 'N/A'}
  Workspace: {cb.workspace.name if cb.workspace else 'N/A'}

[bold blue]Statistics:[/]
  Total Items: {total_items}
  Pinned Items: {clipboard.items.filter(is_pinned=True).count()}

[bold white]Metadata:[/]
  Owner: {cb.owner.username if cb.owner else 'N/A'}
  Created: {format_timestamp(cb.created_at)}
  Updated: {format_timestamp(cb.updated_at)}
  Activated: {format_timestamp(cb.activated_at) if cb.activated_at else 'Never'}
  ID: {cb.id}
"""
            if cb.description:
                details = f"\n[bold green]Description:[/] {cb.description}" + details

            panel = Panel(details, title=f"Clipboard: {cb.name}", border_style="cyan")
            console.print(panel)

            # Show items if requested
            if items and cb_items:
                console.print(f"\n[bold]Items[/] (showing {len(cb_items)} of {total_items}):\n")
                table = create_table(
                    "Clipboard Items",
                    [
                        ("Pos", "dim"),
                        ("Source", "yellow"),
                        ("Type", "cyan"),
                        ("Reference", "green"),
                        ("Pinned", "magenta"),
                    ],
                )
                for item in cb_items:
                    ref = ""
                    if item.content_object:
                        ref = f"{item.content_type}: {item.object_id}"
                    elif item.virtual_node:
                        ref = f"Virtual: {item.virtual_node.node_type}"
                    table.add_row(
                        str(item.position),
                        item.get_source_channel_display(),
                        str(item.content_type) if item.content_type else "Virtual",
                        ref[:30] if ref else "N/A",
                        "Yes" if item.is_pinned else "No",
                    )
                console.print(table)

                if total_items > limit:
                    remaining = total_items - limit
                    console.print(
                        f"[dim]... and {remaining} more items (use --limit to see more)[/]"
                    )

        output_item(
            item=clipboard,
            format=format,
            panel_builder=build_panel,
            json_builder=build_json,
        )

    except typer.Exit:
        raise
    except Exception as e:
        print_error(f"Error showing clipboard: {e}")
        raise typer.Exit(code=1)


@clipboard_app.command(name="create")
@with_django
def create_clipboard(
    name: str = typer.Argument(..., help="Clipboard name"),
    project: str = typer.Option(
        ..., "--project", "-p", help="Project name (required)"
    ),
    workspace: str | None = typer.Option(
        None, "--workspace", "-w", help="Workspace name (uses default if not specified)"
    ),
    description: str = typer.Option(
        "", "--description", "-d", help="Clipboard description"
    ),
    activate: bool = typer.Option(
        False, "--activate", "-a", help="Activate the clipboard immediately"
    ),
    user_id: int | None = typer.Option(
        None, "--user", "-u", help="User ID to own the clipboard"
    ),
    format: OutputFormat = FormatOption,
):
    """Create a new clipboard."""
    try:
        from django.conf import settings
        from django.contrib.auth import get_user_model

        Clipboard = apps.get_model("context_clipboards", "Clipboard")
        Project = apps.get_model("projects", "Project")
        Workspace = apps.get_model("workspaces", "Workspace")
        user_model = get_user_model()

        # Get project
        try:
            project_obj = Project.objects.get(name=project)
        except Project.DoesNotExist:
            print_error(f"Project not found: {project}")
            raise typer.Exit(code=1)

        # Get workspace
        if workspace:
            try:
                workspace_obj = Workspace.objects.get(project=project_obj, name=workspace)
            except Workspace.DoesNotExist:
                print_error(f"Workspace not found: {workspace}")
                raise typer.Exit(code=1)
        else:
            # Use first workspace in project
            workspace_obj = Workspace.objects.filter(project=project_obj).first()
            if not workspace_obj:
                print_error(f"No workspaces found in project: {project}")
                raise typer.Exit(code=1)

        # Get user for CLI context
        if user_id:
            # Explicit user ID provided
            try:
                owner = user_model.objects.get(id=user_id)
            except user_model.DoesNotExist:
                print_error(f"User not found with ID: {user_id}")
                raise typer.Exit(code=1)
        elif settings.DEBUG:
            # Local/single-user mode: auto-select first user with organization membership
            from organizations.models import OrganizationUser

            org_user = OrganizationUser.objects.select_related("user").first()
            if org_user:
                owner = org_user.user
            else:
                owner = user_model.objects.filter(is_active=True).first()
            if not owner:
                print_error("No users found. Run 'python manage.py initialize_local_user' first.")
                raise typer.Exit(code=1)
        else:
            # Production: require explicit user
            print_error("--user is required. Specify the user ID to own the clipboard.")
            raise typer.Exit(code=1)

        # If activating, deactivate any existing active clipboard
        if activate:
            existing_active = Clipboard.objects.filter(
                workspace=workspace_obj, owner=owner, is_active=True
            ).first()
            if existing_active:
                existing_active.deactivate()
                existing_active.save()

        # Create the clipboard
        clipboard = Clipboard.objects.create(
            workspace=workspace_obj,
            owner=owner,
            name=name,
            description=description,
        )

        if activate:
            clipboard.activate()
            clipboard.save()

        if format == OutputFormat.JSON:
            print_json({
                "id": clipboard.id,
                "name": clipboard.name,
                "description": clipboard.description or None,
                "workspace": workspace_obj.name,
                "project": project_obj.name,
                "owner": owner.username,
                "is_active": clipboard.is_active,
                "created_at": clipboard.created_at.isoformat(),
            })
        else:
            status = "Active" if clipboard.is_active else "Inactive"
            print_success(f"Created clipboard '{clipboard.name}' (ID: {clipboard.id}) - {status}")

            details = f"""
[bold cyan]Name:[/] {clipboard.name}
[bold green]Workspace:[/] {workspace_obj.name}
[bold yellow]Project:[/] {project_obj.name}
[bold magenta]Status:[/] {status}
[bold white]ID:[/] {clipboard.id}
"""
            if description:
                details = f"[bold]Description:[/] {description}\n" + details

            panel = Panel(details, title="Clipboard Created", border_style="green")
            console.print(panel)

    except typer.Exit:
        raise
    except Exception as e:
        print_error(f"Error creating clipboard: {e}")
        raise typer.Exit(code=1)


@clipboard_app.command(name="activate")
@with_django
def activate_clipboard(
    clipboard_id: int = typer.Argument(..., help="Clipboard ID to activate"),
):
    """Activate a clipboard (deactivates any other active clipboard in the same workspace)."""
    try:
        Clipboard = apps.get_model("context_clipboards", "Clipboard")

        try:
            clipboard = Clipboard.objects.select_related("workspace", "owner").get(
                id=clipboard_id
            )
        except Clipboard.DoesNotExist:
            print_error(f"Clipboard not found: {clipboard_id}")
            raise typer.Exit(code=1)

        if clipboard.is_active:
            console.print(
                f"Clipboard '{clipboard.name}' is already active.", style="yellow"
            )
            return

        # Deactivate any existing active clipboard for this user in this workspace
        existing_active = Clipboard.objects.filter(
            workspace=clipboard.workspace, owner=clipboard.owner, is_active=True
        ).first()
        if existing_active:
            existing_active.deactivate()
            existing_active.save()
            console.print(
                f"Deactivated previous clipboard: '{existing_active.name}'", style="dim"
            )

        # Activate the new clipboard
        clipboard.activate()
        clipboard.save()

        print_success(f"Activated clipboard '{clipboard.name}' (ID: {clipboard_id})")

    except typer.Exit:
        raise
    except Exception as e:
        print_error(f"Error activating clipboard: {e}")
        raise typer.Exit(code=1)


@clipboard_app.command(name="export")
@with_django
def export_clipboard(
    clipboard_id: int = typer.Argument(..., help="Clipboard ID to export"),
    output_format: str = typer.Option(
        "json", "--output", "-o", help="Export format: json, text"
    ),
):
    """Export clipboard content."""
    try:
        Clipboard = apps.get_model("context_clipboards", "Clipboard")

        try:
            clipboard = Clipboard.objects.select_related("workspace").get(id=clipboard_id)
        except Clipboard.DoesNotExist:
            print_error(f"Clipboard not found: {clipboard_id}")
            raise typer.Exit(code=1)

        items = list(clipboard.items.all().select_related("content_type", "virtual_node"))

        if output_format == "json":
            export_data = {
                "clipboard": {
                    "id": clipboard.id,
                    "name": clipboard.name,
                    "workspace": clipboard.workspace.name if clipboard.workspace else None,
                },
                "items": [],
            }

            for item in items:
                item_data = {
                    "position": item.position,
                    "source_channel": item.source_channel,
                    "is_pinned": item.is_pinned,
                }

                if item.content_object:
                    item_data["type"] = "content"
                    item_data["content_type"] = str(item.content_type)
                    item_data["object_id"] = item.object_id
                    # Try to get content preview
                    if hasattr(item.content_object, "content"):
                        item_data["content"] = item.content_object.content[:500]
                    elif hasattr(item.content_object, "name"):
                        item_data["name"] = str(item.content_object.name)
                elif item.virtual_node:
                    item_data["type"] = "virtual"
                    item_data["node_type"] = item.virtual_node.node_type
                    item_data["payload"] = item.virtual_node.payload
                    if item.virtual_node.preview_text:
                        item_data["preview"] = item.virtual_node.preview_text[:500]

                export_data["items"].append(item_data)

            print_json(export_data)

        elif output_format == "text":
            console.print(f"[bold]Clipboard: {clipboard.name}[/]\n")
            console.print(f"Items ({len(items)}):\n")

            for i, item in enumerate(items, 1):
                console.print(f"[dim]--- Item {i} (position: {item.position}) ---[/]")
                if item.content_object:
                    if hasattr(item.content_object, "content"):
                        console.print(item.content_object.content[:500])
                    else:
                        console.print(f"[{item.content_type}] {item.object_id}")
                elif item.virtual_node:
                    if item.virtual_node.preview_text:
                        console.print(item.virtual_node.preview_text[:500])
                    else:
                        console.print(f"[Virtual: {item.virtual_node.node_type}]")
                console.print()
        else:
            print_error(f"Unsupported format: {output_format}. Use 'json' or 'text'.")
            raise typer.Exit(code=1)

    except typer.Exit:
        raise
    except Exception as e:
        print_error(f"Error exporting clipboard: {e}")
        raise typer.Exit(code=1)


@clipboard_app.command(name="save-as-document")
@with_django
def save_clipboard_as_document(
    clipboard_id: int = typer.Argument(..., help="Clipboard ID to save as a document"),
    name: str | None = typer.Option(
        None, "--name", "-n", help="Document name (defaults to '<clipboard> (Notepad)')"
    ),
    description: str = typer.Option(
        "", "--description", "-d", help="Optional document description"
    ),
    folder_id: int | None = typer.Option(
        None, "--folder-id", help="Optional folder ID in the same workspace"
    ),
    format: OutputFormat = FormatOption,
):
    """Save a clipboard notepad as a shared YooptaDocument.

    This keeps the clipboard itself user-private, but produces a shareable document
    (org-scoped) when explicitly requested.
    """
    try:
        Clipboard = apps.get_model("context_clipboards", "Clipboard")
        Folder = apps.get_model("documents", "Folder")
        YooptaDocument = apps.get_model("documents", "YooptaDocument")

        try:
            clipboard = Clipboard.objects.select_related(
                "workspace",
                "workspace__project",
                "workspace__project__organization",
                "owner",
            ).get(id=clipboard_id)
        except Clipboard.DoesNotExist:
            print_error(f"Clipboard not found: {clipboard_id}")
            raise typer.Exit(code=1)

        folder = None
        if folder_id:
            try:
                folder = Folder.objects.get(
                    id=folder_id,
                    organization=clipboard.workspace.project.organization,
                    workspace=clipboard.workspace,
                )
            except Folder.DoesNotExist:
                print_error(f"Folder not found or not in clipboard workspace: {folder_id}")
                raise typer.Exit(code=1)

        from context_clipboards.notepad import build_shareable_yoopta_content_for_clipboard

        content_dict = build_shareable_yoopta_content_for_clipboard(clipboard)
        content_json = json.dumps(content_dict)

        document = YooptaDocument.objects.create(
            organization=clipboard.workspace.project.organization,
            project=clipboard.workspace.project,
            workspace=clipboard.workspace,
            name=name or f"{clipboard.name} (Notepad)",
            description=description or "",
            content=content_json,
            yoopta_version="4.0",
            created_by=clipboard.owner,
            file_size=len(content_json.encode("utf-8")) if content_json else 0,
            folder=folder,
        )

        if format == OutputFormat.JSON:
            print_json(
                {
                    "clipboard_id": clipboard.id,
                    "document_id": document.id,
                    "document_name": document.name,
                    "document_type": "YooptaDocument",
                    "workspace": clipboard.workspace.name if clipboard.workspace else None,
                    "project": clipboard.workspace.project.name if clipboard.workspace else None,
                }
            )
            return

        print_success(
            f"Saved clipboard '{clipboard.name}' as YooptaDocument (ID: {document.id})"
        )
        details = f"""
[bold cyan]Document:[/] {document.name}
[bold green]Workspace:[/] {clipboard.workspace.name if clipboard.workspace else 'N/A'}
[bold yellow]Project:[/] {clipboard.workspace.project.name if clipboard.workspace else 'N/A'}
[bold magenta]Document ID:[/] {document.id}
"""
        panel = Panel(details, title="Notepad Saved", border_style="green")
        console.print(panel)

    except typer.Exit:
        raise
    except Exception as e:
        print_error(f"Error saving clipboard as document: {e}")
        raise typer.Exit(code=1)


# ============================================================================
# Clipboard Items Subcommands
# ============================================================================


def _validate_direction(direction: str) -> str:
    normalized = (direction or "").strip().lower()
    if normalized not in {"left", "right"}:
        raise typer.BadParameter("direction must be 'left' or 'right'")
    return normalized


@clipboard_items_app.command(name="add-document")
@with_django
def add_document_item(
    clipboard_id: int = typer.Argument(..., help="Clipboard ID"),
    document_id: int = typer.Option(..., "--document-id", help="Document ID to add"),
    direction: str = typer.Option(
        "right", "--direction", help="Insert direction (left/right)"
    ),
    format: OutputFormat = FormatOption,
):
    """Add a document reference to a clipboard."""
    try:
        Clipboard = apps.get_model("context_clipboards", "Clipboard")
        Document = apps.get_model("documents", "Document")

        from context_clipboards.services import ClipboardService

        direction = _validate_direction(direction)

        try:
            clipboard = Clipboard.objects.select_related(
                "workspace",
                "workspace__project",
                "workspace__project__organization",
                "owner",
            ).get(id=clipboard_id)
        except Clipboard.DoesNotExist:
            print_error(f"Clipboard not found: {clipboard_id}")
            raise typer.Exit(code=1)

        try:
            document = Document.objects.select_subclasses().get(id=document_id)
        except Document.DoesNotExist:
            print_error(f"Document not found: {document_id}")
            raise typer.Exit(code=1)

        if (
            document.organization_id != clipboard.workspace.project.organization_id
            or document.workspace_id != clipboard.workspace_id
        ):
            print_error("Document must be in the same organization and workspace as the clipboard.")
            raise typer.Exit(code=1)

        service = ClipboardService(actor=clipboard.owner)
        op = service.add_item(
            clipboard=clipboard,
            direction=direction,
            content_object=document,
            source_channel="document",
        )

        if format == OutputFormat.JSON:
            print_json(
                {
                    "clipboard_id": clipboard.id,
                    "item_id": op.item.id if op.item else None,
                    "document_id": document.id,
                    "document_name": document.name,
                }
            )
            return

        print_success(f"Added document '{document.name}' to clipboard (item {op.item.id})")

    except typer.Exit:
        raise
    except Exception as e:
        print_error(f"Error adding document to clipboard: {e}")
        raise typer.Exit(code=1)


@clipboard_items_app.command(name="add-text")
@with_django
def add_text_item(
    clipboard_id: int = typer.Argument(..., help="Clipboard ID"),
    text: str = typer.Option(..., "--text", help="Text content to add"),
    direction: str = typer.Option(
        "right", "--direction", help="Insert direction (left/right)"
    ),
    format: OutputFormat = FormatOption,
):
    """Add a plain text item to a clipboard."""
    try:
        Clipboard = apps.get_model("context_clipboards", "Clipboard")
        from context_clipboards.services import ClipboardService

        direction = _validate_direction(direction)

        try:
            clipboard = Clipboard.objects.select_related("workspace", "owner").get(id=clipboard_id)
        except Clipboard.DoesNotExist:
            print_error(f"Clipboard not found: {clipboard_id}")
            raise typer.Exit(code=1)

        normalized = text.strip()
        if not normalized:
            print_error("Text cannot be empty.")
            raise typer.Exit(code=1)

        preview = normalized[:180] + ("..." if len(normalized) > 180 else "")
        service = ClipboardService(actor=clipboard.owner)
        op = service.add_item(
            clipboard=clipboard,
            direction=direction,
            source_channel="message",
            source_metadata={
                "preview": preview,
                "full_text": normalized,
            },
        )

        if format == OutputFormat.JSON:
            print_json(
                {
                    "clipboard_id": clipboard.id,
                    "item_id": op.item.id if op.item else None,
                    "text_preview": preview,
                }
            )
            return

        print_success(f"Added text item to clipboard (item {op.item.id})")

    except typer.Exit:
        raise
    except Exception as e:
        print_error(f"Error adding text to clipboard: {e}")
        raise typer.Exit(code=1)


@clipboard_items_app.command(name="add-diagram")
@with_django
def add_diagram_item(
    clipboard_id: int = typer.Argument(..., help="Clipboard ID"),
    name: str = typer.Option("Diagram", "--name", help="Diagram name"),
    code: str = typer.Option(..., "--code", help="Diagram code"),
    direction: str = typer.Option(
        "right", "--direction", help="Insert direction (left/right)"
    ),
    format: OutputFormat = FormatOption,
):
    """Add a diagram (code) item to a clipboard."""
    try:
        Clipboard = apps.get_model("context_clipboards", "Clipboard")
        from context_clipboards.services import ClipboardService

        direction = _validate_direction(direction)

        try:
            clipboard = Clipboard.objects.select_related("workspace", "owner").get(id=clipboard_id)
        except Clipboard.DoesNotExist:
            print_error(f"Clipboard not found: {clipboard_id}")
            raise typer.Exit(code=1)

        diagram_code = code.strip()
        if not diagram_code:
            print_error("Diagram code cannot be empty.")
            raise typer.Exit(code=1)

        service = ClipboardService(actor=clipboard.owner)
        op = service.add_item(
            clipboard=clipboard,
            direction=direction,
            source_channel="canvas",
            source_metadata={
                "diagram_signature": diagram_code,
                "diagram_name": name.strip() or "Diagram",
                "diagram_code": diagram_code,
                "source": "canvas",
            },
        )

        if format == OutputFormat.JSON:
            print_json(
                {
                    "clipboard_id": clipboard.id,
                    "item_id": op.item.id if op.item else None,
                    "diagram_name": name.strip() or "Diagram",
                }
            )
            return

        print_success(f"Added diagram item to clipboard (item {op.item.id})")

    except typer.Exit:
        raise
    except Exception as e:
        print_error(f"Error adding diagram to clipboard: {e}")
        raise typer.Exit(code=1)


@clipboard_items_app.command(name="rm")
@with_django
def remove_item(
    clipboard_id: int = typer.Argument(..., help="Clipboard ID"),
    item_id: int = typer.Argument(..., help="ClipboardItem ID to remove"),
    format: OutputFormat = FormatOption,
):
    """Remove a ClipboardItem by ID."""
    try:
        Clipboard = apps.get_model("context_clipboards", "Clipboard")

        try:
            clipboard = Clipboard.objects.get(id=clipboard_id)
        except Clipboard.DoesNotExist:
            print_error(f"Clipboard not found: {clipboard_id}")
            raise typer.Exit(code=1)

        try:
            item = clipboard.items.get(id=item_id)
        except Exception:
            print_error(f"Clipboard item not found: {item_id}")
            raise typer.Exit(code=1)

        item.delete()

        if format == OutputFormat.JSON:
            print_json({"clipboard_id": clipboard.id, "item_id": item_id, "deleted": True})
            return

        print_success(f"Removed item {item_id} from clipboard {clipboard_id}")

    except typer.Exit:
        raise
    except Exception as e:
        print_error(f"Error removing clipboard item: {e}")
        raise typer.Exit(code=1)
