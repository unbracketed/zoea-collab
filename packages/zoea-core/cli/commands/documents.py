"""Document management commands."""

import sys

import typer
from django.apps import apps
from rich.panel import Panel
from rich.syntax import Syntax

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
    print_success,
)

# Create documents command group
documents_app = typer.Typer(
    name="documents",
    help="Manage documents",
    rich_markup_mode="rich",
)


@documents_app.callback(invoke_without_command=True)
def documents_callback(ctx: typer.Context):
    """Documents command group."""
    if ctx.invoked_subcommand is None:
        # Default to list command
        list_documents()


@documents_app.command(name="list")
@with_django
def list_documents(
    org: str | None = typer.Option(
        None, "--org", "-o", help="Filter by organization name"
    ),
    project: str | None = typer.Option(
        None, "--project", "-p", help="Filter by project name"
    ),
    folder: str | None = typer.Option(
        None, "--folder", help="Filter by folder path"
    ),
    doc_type: str | None = typer.Option(
        None, "--type", "-t", help="Filter by document type (e.g., Markdown, PDF, Image)"
    ),
    limit: int = typer.Option(
        50, "--limit", "-l", help="Maximum number of documents to display"
    ),
    format: OutputFormat = FormatOption,
):
    """List documents with optional filters."""
    try:
        Document = apps.get_model("documents", "Document")
        Organization = apps.get_model("organizations", "Organization")
        Project = apps.get_model("projects", "Project")
        Folder = apps.get_model("documents", "Folder")

        # Build query with select_subclasses for polymorphic types
        documents = Document.objects.select_subclasses().select_related(
            "organization", "project", "folder", "created_by"
        )

        # Apply organization filter
        org_name = get_organization_filter(org)
        if org_name:
            try:
                organization = Organization.objects.get(name=org_name)
                documents = documents.filter(organization=organization)
            except Organization.DoesNotExist:
                print_error(f"Organization not found: {org_name}")
                raise typer.Exit(code=1)

        # Apply project filter
        if project:
            try:
                project_obj = Project.objects.get(name=project)
                documents = documents.filter(project=project_obj)
            except Project.DoesNotExist:
                print_error(f"Project not found: {project}")
                raise typer.Exit(code=1)

        # Apply folder filter (by path)
        if folder:
            # Find folders matching the path
            matching_folders = []
            for f in Folder.objects.all():
                if f.get_path() == folder or f.get_path().endswith(folder):
                    matching_folders.append(f.id)
            if matching_folders:
                documents = documents.filter(folder_id__in=matching_folders)
            else:
                print_error(f"Folder not found: {folder}")
                raise typer.Exit(code=1)

        # Apply type filter
        if doc_type:
            # Filter by document type name (case-insensitive partial match)
            type_lower = doc_type.lower()
            filtered_docs = []
            for doc in documents[:limit * 2]:  # Get extra to account for filtering
                if type_lower in doc.get_type_name().lower():
                    filtered_docs.append(doc)
                    if len(filtered_docs) >= limit:
                        break
            documents = filtered_docs
        else:
            documents = list(documents[:limit])

        if not documents:
            if format == OutputFormat.JSON:
                print_json([])
            else:
                console.print("No documents found.", style="yellow")
            return

        # Define how to build JSON output
        def build_json(doc):
            return {
                "id": doc.id,
                "name": doc.name,
                "type": doc.get_type_name(),
                "project": doc.project.name if doc.project else None,
                "folder": doc.folder.get_path() if doc.folder else None,
                "description": doc.description,
                "file_size": doc.file_size,
                "created_at": doc.created_at.isoformat() if doc.created_at else None,
                "created_by": doc.created_by.username if doc.created_by else None,
            }

        # Define how to build table row
        def build_row(doc):
            folder_path = doc.folder.get_path() if doc.folder else "-"
            # Truncate long folder paths
            if len(folder_path) > 20:
                folder_path = "..." + folder_path[-17:]
            return [
                doc.name[:30] + ("..." if len(doc.name) > 30 else ""),
                doc.get_type_name(),
                doc.project.name if doc.project else "-",
                folder_path,
                format_date(doc.created_at),
            ]

        # Build table columns
        columns = [
            ("Name", "cyan", True),
            ("Type", "magenta"),
            ("Project", "yellow"),
            ("Folder", "green"),
            ("Created", "blue"),
        ]

        output_list(
            items=documents,
            format=format,
            table_title=f"Documents ({len(documents)} shown)",
            columns=columns,
            row_builder=build_row,
            json_builder=build_json,
        )

    except typer.Exit:
        raise
    except Exception as e:
        print_error(f"Error listing documents: {e}")
        raise typer.Exit(code=1)


@documents_app.command(name="show")
@with_django
def show_document(
    document_id: int = typer.Argument(..., help="Document ID"),
    content: bool = typer.Option(
        False, "--content", "-c", help="Show document content (for text-based documents)"
    ),
    format: OutputFormat = FormatOption,
):
    """Show detailed information about a document."""
    try:
        Document = apps.get_model("documents", "Document")

        # Get the document with its specific subclass
        try:
            doc = Document.objects.select_subclasses().select_related(
                "organization", "project", "folder", "created_by"
            ).get(id=document_id)
        except Document.DoesNotExist:
            print_error(f"Document not found: {document_id}")
            raise typer.Exit(code=1)

        # Get document-type-specific info
        doc_type = doc.get_type_name()
        type_specific = {}

        # Check for text content
        has_content = hasattr(doc, "content")
        doc_content = getattr(doc, "content", None) if has_content else None

        # Collect type-specific fields
        if doc_type == "Image":
            type_specific = {
                "width": getattr(doc, "width", None),
                "height": getattr(doc, "height", None),
                "image_file": str(getattr(doc, "image_file", None)),
            }
        elif doc_type == "PDF":
            type_specific = {
                "page_count": getattr(doc, "page_count", None),
                "pdf_file": str(getattr(doc, "pdf_file", None)),
            }
        elif doc_type in ("D2Diagram", "ReactFlowDiagram", "MermaidDiagram"):
            type_specific = {
                "diagram_type": getattr(doc, "diagram_type", None),
            }
        elif doc_type == "CSV":
            type_specific = {
                "has_header": getattr(doc, "has_header", None),
                "delimiter": getattr(doc, "delimiter", None),
            }

        def build_json(d):
            # Check for sync errors
            sync_error = getattr(d, "gemini_sync_error", None)
            sync_attempts = getattr(d, "gemini_sync_attempts", 0)

            data = {
                "id": d.id,
                "name": d.name,
                "type": doc_type,
                "description": d.description,
                "organization": d.organization.name if d.organization else None,
                "project": d.project.name if d.project else None,
                "folder": d.folder.get_path() if d.folder else None,
                "file_size": d.file_size,
                "file_search": {
                    "indexed": d.gemini_synced_at is not None,
                    "last_synced": d.gemini_synced_at.isoformat() if d.gemini_synced_at else None,
                    "file_id": d.gemini_file_id,
                    "error": sync_error,
                    "attempts": sync_attempts,
                },
                "created_at": d.created_at.isoformat() if d.created_at else None,
                "updated_at": d.updated_at.isoformat() if d.updated_at else None,
                "created_by": d.created_by.username if d.created_by else None,
                **type_specific,
            }
            if content and doc_content:
                data["content"] = doc_content
            return data

        def build_panel(d):
            # Build type-specific section
            type_info = ""
            if type_specific:
                type_lines = [f"  {k}: {v}" for k, v in type_specific.items() if v]
                if type_lines:
                    type_info = "\n[bold white]Type Details:[/]\n" + "\n".join(type_lines)

            # Build file search status
            sync_error = getattr(d, "gemini_sync_error", None)
            if d.gemini_synced_at:
                index_status = f"[green]Indexed[/] ({format_timestamp(d.gemini_synced_at)})"
            elif sync_error:
                index_status = f"[red]Error:[/] {sync_error[:50]}..."
            else:
                index_status = "[yellow]Pending[/]"

            details = f"""
[bold cyan]Name:[/] {d.name}
[bold magenta]Type:[/] {doc_type}
[bold green]Description:[/] {d.description or 'N/A'}

[bold yellow]Location:[/]
  Organization: {d.organization.name if d.organization else 'N/A'}
  Project: {d.project.name if d.project else 'N/A'}
  Folder: {d.folder.get_path() if d.folder else 'N/A'}

[bold blue]File Search:[/]
  Status: {index_status}

[bold white]Metadata:[/]
  File Size: {d.file_size or 'N/A'} bytes
  Created: {format_timestamp(d.created_at)}
  Updated: {format_timestamp(d.updated_at)}
  Created By: {d.created_by.username if d.created_by else 'N/A'}
  ID: {d.id}{type_info}
"""
            panel = Panel(details, title=f"Document: {d.name}", border_style="cyan")
            console.print(panel)

            # Show content if requested
            if content and doc_content:
                console.print("\n[bold]Content:[/]")
                # Use syntax highlighting for known types
                if doc_type == "Markdown":
                    syntax = Syntax(doc_content, "markdown", theme="monokai", word_wrap=True)
                    console.print(syntax)
                elif doc_type in ("D2Diagram",):
                    console.print(Panel(doc_content, border_style="dim"))
                elif doc_type == "CSV":
                    console.print(Panel(doc_content[:2000], border_style="dim"))
                else:
                    console.print(Panel(doc_content[:2000], border_style="dim"))
            elif content and not has_content:
                console.print("\n[yellow]This document type does not have text content.[/]")

        output_item(
            item=doc,
            format=format,
            panel_builder=build_panel,
            json_builder=build_json,
        )

    except typer.Exit:
        raise
    except Exception as e:
        print_error(f"Error showing document: {e}")
        raise typer.Exit(code=1)


def _get_content_from_input(content: str | None, file: str | None) -> str:
    """Get content from --content flag, --file flag, or stdin."""
    if content:
        return content
    if file:
        try:
            with open(file, encoding="utf-8") as f:
                return f.read()
        except FileNotFoundError:
            print_error(f"File not found: {file}")
            raise typer.Exit(code=1)
        except Exception as e:
            print_error(f"Error reading file: {e}")
            raise typer.Exit(code=1)
    # Check if stdin has data
    if not sys.stdin.isatty():
        return sys.stdin.read()
    return ""


def _resolve_folder(project_obj, folder_path: str | None):
    """Resolve folder from path within project."""
    if not folder_path:
        return None

    Folder = apps.get_model("documents", "Folder")

    # Find folder by path
    for folder in Folder.objects.filter(project=project_obj):
        if folder.get_path() == folder_path:
            return folder

    print_error(f"Folder '{folder_path}' not found in project '{project_obj.name}'")
    raise typer.Exit(code=1)


def _build_created_doc_json(doc):
    """Build JSON output for a created document."""
    return {
        "id": doc.id,
        "name": doc.name,
        "type": doc.get_type_name(),
        "project": doc.project.name if doc.project else None,
        "folder": doc.folder.get_path() if doc.folder else None,
        "description": doc.description,
        "file_size": doc.file_size,
        "created_at": doc.created_at.isoformat() if doc.created_at else None,
    }


@documents_app.command(name="create-markdown")
@with_django
def create_markdown(
    name: str = typer.Argument(..., help="Document name"),
    project: str = typer.Option(..., "--project", "-p", help="Project name (required)"),
    folder: str | None = typer.Option(None, "--folder", help="Folder path within project"),
    description: str = typer.Option("", "--description", "-d", help="Document description"),
    content: str | None = typer.Option(None, "--content", "-c", help="Markdown content"),
    file: str | None = typer.Option(None, "--file", help="Read content from file"),
    format: OutputFormat = FormatOption,
):
    """Create a new Markdown document.

    Content can be provided via --content, --file, or stdin.

    Examples:
        zoea documents create-markdown "README" -p "MyProject" -c "# Hello"
        echo "# Title" | zoea documents create-markdown "Doc" -p "MyProject"
        zoea documents create-markdown "Doc" -p "MyProject" -f ./content.md
    """
    try:
        Markdown = apps.get_model("documents", "Markdown")
        Project = apps.get_model("projects", "Project")

        # Get project
        try:
            project_obj = Project.objects.get(name=project)
        except Project.DoesNotExist:
            print_error(f"Project not found: {project}")
            raise typer.Exit(code=1)

        # Resolve folder
        folder_obj = _resolve_folder(project_obj, folder)

        # Get content
        doc_content = _get_content_from_input(content, file)

        # Create the document
        doc = Markdown.objects.create(
            name=name,
            description=description,
            content=doc_content,
            organization=project_obj.organization,
            project=project_obj,
            folder=folder_obj,
            file_size=len(doc_content.encode("utf-8")) if doc_content else 0,
        )

        if format == OutputFormat.JSON:
            print_json(_build_created_doc_json(doc))
        else:
            print_success(f"Created Markdown document '{doc.name}' (ID: {doc.id})")
            details = f"""
[bold cyan]Name:[/] {doc.name}
[bold magenta]Type:[/] Markdown
[bold yellow]Project:[/] {doc.project.name}
[bold blue]Folder:[/] {doc.folder.get_path() if doc.folder else 'N/A'}
[bold white]Size:[/] {doc.file_size} bytes
[bold white]ID:[/] {doc.id}
"""
            console.print(Panel(details, title="Document Created", border_style="green"))

    except typer.Exit:
        raise
    except Exception as e:
        print_error(f"Error creating Markdown document: {e}")
        raise typer.Exit(code=1)


@documents_app.command(name="create-d2")
@with_django
def create_d2(
    name: str = typer.Argument(..., help="Document name"),
    project: str = typer.Option(..., "--project", "-p", help="Project name (required)"),
    folder: str | None = typer.Option(None, "--folder", help="Folder path within project"),
    description: str = typer.Option("", "--description", "-d", help="Document description"),
    content: str | None = typer.Option(None, "--content", "-c", help="D2 diagram content"),
    file: str | None = typer.Option(None, "--file", help="Read content from file"),
    format: OutputFormat = FormatOption,
):
    """Create a new D2 diagram document.

    Content can be provided via --content, --file, or stdin.

    Examples:
        zoea documents create-d2 "Architecture" -p "MyProject" -c "a -> b"
        echo "x -> y -> z" | zoea documents create-d2 "Flow" -p "MyProject"
        zoea documents create-d2 "Diagram" -p "MyProject" -f ./diagram.d2
    """
    try:
        D2Diagram = apps.get_model("documents", "D2Diagram")
        Project = apps.get_model("projects", "Project")

        # Get project
        try:
            project_obj = Project.objects.get(name=project)
        except Project.DoesNotExist:
            print_error(f"Project not found: {project}")
            raise typer.Exit(code=1)

        # Resolve folder
        folder_obj = _resolve_folder(project_obj, folder)

        # Get content
        doc_content = _get_content_from_input(content, file)

        # Create the document
        doc = D2Diagram.objects.create(
            name=name,
            description=description,
            content=doc_content,
            organization=project_obj.organization,
            project=project_obj,
            folder=folder_obj,
            file_size=len(doc_content.encode("utf-8")) if doc_content else 0,
        )

        if format == OutputFormat.JSON:
            print_json(_build_created_doc_json(doc))
        else:
            print_success(f"Created D2 diagram '{doc.name}' (ID: {doc.id})")
            details = f"""
[bold cyan]Name:[/] {doc.name}
[bold magenta]Type:[/] D2 Diagram
[bold yellow]Project:[/] {doc.project.name}
[bold blue]Folder:[/] {doc.folder.get_path() if doc.folder else 'N/A'}
[bold white]Size:[/] {doc.file_size} bytes
[bold white]ID:[/] {doc.id}
"""
            console.print(Panel(details, title="Document Created", border_style="green"))

    except typer.Exit:
        raise
    except Exception as e:
        print_error(f"Error creating D2 diagram: {e}")
        raise typer.Exit(code=1)


# ============================================================================
# Folders Subcommands
# ============================================================================

folders_app = typer.Typer(
    name="folders",
    help="Manage document folders",
    rich_markup_mode="rich",
)

# Add folders as a subcommand group of documents
documents_app.add_typer(folders_app, name="folders")


@folders_app.command(name="list")
@with_django
def list_folders(
    org: str | None = typer.Option(
        None, "--org", "-o", help="Filter by organization name"
    ),
    project: str | None = typer.Option(
        None, "--project", "-p", help="Filter by project name"
    ),
    format: OutputFormat = FormatOption,
):
    """List document folders."""
    try:
        Folder = apps.get_model("documents", "Folder")
        Organization = apps.get_model("organizations", "Organization")
        Project = apps.get_model("projects", "Project")

        folders = Folder.objects.select_related(
            "organization", "project", "parent", "created_by"
        )

        # Apply organization filter
        org_name = get_organization_filter(org)
        if org_name:
            try:
                organization = Organization.objects.get(name=org_name)
                folders = folders.filter(organization=organization)
            except Organization.DoesNotExist:
                print_error(f"Organization not found: {org_name}")
                raise typer.Exit(code=1)

        # Apply project filter
        if project:
            try:
                project_obj = Project.objects.get(name=project)
                folders = folders.filter(project=project_obj)
            except Project.DoesNotExist:
                print_error(f"Project not found: {project}")
                raise typer.Exit(code=1)

        if not folders.exists():
            if format == OutputFormat.JSON:
                print_json([])
            else:
                console.print("No folders found.", style="yellow")
            return

        def build_json(f):
            return {
                "id": f.id,
                "name": f.name,
                "path": f.get_path(),
                "project": f.project.name if f.project else None,
                "parent_id": f.parent_id,
                "document_count": f.documents.count(),
                "created_at": f.created_at.isoformat() if f.created_at else None,
            }

        def build_row(f):
            return [
                f.name,
                f.get_path(),
                f.project.name if f.project else "-",
                str(f.documents.count()),
            ]

        columns = [
            ("Name", "cyan", True),
            ("Path", "green"),
            ("Project", "yellow"),
            ("Docs", "magenta"),
        ]

        output_list(
            items=list(folders),
            format=format,
            table_title="Folders",
            columns=columns,
            row_builder=build_row,
            json_builder=build_json,
        )

    except typer.Exit:
        raise
    except Exception as e:
        print_error(f"Error listing folders: {e}")
        raise typer.Exit(code=1)


@folders_app.command(name="show")
@with_django
def show_folder(
    folder_id: int = typer.Argument(..., help="Folder ID"),
    format: OutputFormat = FormatOption,
):
    """Show detailed folder information."""
    try:
        Folder = apps.get_model("documents", "Folder")

        try:
            folder = Folder.objects.select_related(
                "organization", "project", "parent", "created_by"
            ).get(id=folder_id)
        except Folder.DoesNotExist:
            print_error(f"Folder not found: {folder_id}")
            raise typer.Exit(code=1)

        children = list(folder.get_children())
        documents = list(folder.documents.all()[:10])
        doc_count = folder.documents.count()

        def build_json(f):
            return {
                "id": f.id,
                "name": f.name,
                "path": f.get_path(),
                "description": f.description,
                "project": f.project.name if f.project else None,
                "parent_id": f.parent_id,
                "parent_name": f.parent.name if f.parent else None,
                "document_count": doc_count,
                "children": [{"id": c.id, "name": c.name} for c in children],
                "documents": [{"id": d.id, "name": d.name} for d in documents],
                "created_at": f.created_at.isoformat() if f.created_at else None,
                "updated_at": f.updated_at.isoformat() if f.updated_at else None,
                "created_by": f.created_by.username if f.created_by else None,
            }

        def build_panel(f):
            details = f"""
[bold cyan]Name:[/] {f.name}
[bold green]Path:[/] {f.get_path()}
[bold white]Description:[/] {f.description or 'N/A'}

[bold yellow]Location:[/]
  Project: {f.project.name if f.project else 'N/A'}
  Parent: {f.parent.name if f.parent else 'N/A (root)'}

[bold blue]Contents:[/]
  Documents: {doc_count}
  Subfolders: {len(children)}

[bold white]Metadata:[/]
  Created: {format_timestamp(f.created_at)}
  Updated: {format_timestamp(f.updated_at)}
  Created By: {f.created_by.username if f.created_by else 'N/A'}
  ID: {f.id}
"""
            panel = Panel(details, title=f"Folder: {f.get_path()}", border_style="cyan")
            console.print(panel)

            if children:
                console.print(f"\n[bold]Subfolders ({len(children)}):[/]")
                for child in children:
                    console.print(f"  📁 {child.name}")

            if documents:
                console.print(f"\n[bold]Documents ({doc_count}):[/]")
                for doc in documents:
                    console.print(f"  📄 {doc.name}")
                if doc_count > 10:
                    console.print(f"  [dim]... and {doc_count - 10} more[/]")

        output_item(
            item=folder,
            format=format,
            panel_builder=build_panel,
            json_builder=build_json,
        )

    except typer.Exit:
        raise
    except Exception as e:
        print_error(f"Error showing folder: {e}")
        raise typer.Exit(code=1)


@folders_app.command(name="create")
@with_django
def create_folder(
    name: str = typer.Argument(..., help="Folder name"),
    project: str = typer.Option(..., "--project", "-p", help="Project name (required)"),
    parent: str | None = typer.Option(
        None, "--parent", help="Parent folder path (for nested folders)"
    ),
    description: str = typer.Option("", "--description", "-d", help="Folder description"),
    format: OutputFormat = FormatOption,
):
    """Create a new folder."""
    try:
        Folder = apps.get_model("documents", "Folder")
        Project = apps.get_model("projects", "Project")

        # Get project
        try:
            project_obj = Project.objects.get(name=project)
        except Project.DoesNotExist:
            print_error(f"Project not found: {project}")
            raise typer.Exit(code=1)

        # Resolve parent folder
        parent_folder = None
        if parent:
            parent_folder = _resolve_folder(project_obj, parent)

        # Create the folder
        folder = Folder.objects.create(
            name=name,
            description=description,
            organization=project_obj.organization,
            project=project_obj,
            parent=parent_folder,
        )

        if format == OutputFormat.JSON:
            print_json({
                "id": folder.id,
                "name": folder.name,
                "path": folder.get_path(),
                "project": folder.project.name,
                "parent_id": folder.parent_id,
                "created_at": folder.created_at.isoformat() if folder.created_at else None,
            })
        else:
            print_success(f"Created folder '{folder.get_path()}' (ID: {folder.id})")
            details = f"""
[bold cyan]Name:[/] {folder.name}
[bold green]Path:[/] {folder.get_path()}
[bold yellow]Project:[/] {folder.project.name}
[bold white]Parent:[/] {folder.parent.name if folder.parent else 'N/A (root)'}
[bold white]ID:[/] {folder.id}
"""
            console.print(Panel(details, title="Folder Created", border_style="green"))

    except typer.Exit:
        raise
    except Exception as e:
        print_error(f"Error creating folder: {e}")
        raise typer.Exit(code=1)


@folders_app.command(name="delete")
@with_django
def delete_folder(
    folder_id: int = typer.Argument(..., help="Folder ID to delete"),
    force: bool = typer.Option(
        False, "--force", "-f", help="Delete even if folder contains documents"
    ),
):
    """Delete a folder."""
    try:
        Folder = apps.get_model("documents", "Folder")

        try:
            folder = Folder.objects.get(id=folder_id)
        except Folder.DoesNotExist:
            print_error(f"Folder not found: {folder_id}")
            raise typer.Exit(code=1)

        folder_path = folder.get_path()
        doc_count = folder.documents.count()
        child_count = folder.get_children().count()

        if (doc_count > 0 or child_count > 0) and not force:
            print_error(
                f"Folder '{folder_path}' contains {doc_count} documents and "
                f"{child_count} subfolders. Use --force to delete anyway."
            )
            raise typer.Exit(code=1)

        folder.delete()
        print_success(f"Deleted folder '{folder_path}' (ID: {folder_id})")

    except typer.Exit:
        raise
    except Exception as e:
        print_error(f"Error deleting folder: {e}")
        raise typer.Exit(code=1)
