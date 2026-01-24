"""Chat/conversation management commands."""

import typer
from django.apps import apps
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
    print_success,
)

# Create chats command group
chats_app = typer.Typer(
    name="chats",
    help="Manage conversations and chats",
    rich_markup_mode="rich",
)


@chats_app.callback(invoke_without_command=True)
def chats_callback(ctx: typer.Context):
    """Chats command group."""
    if ctx.invoked_subcommand is None:
        # Default to list command
        list_chats()


@chats_app.command(name="list")
@with_django
def list_chats(
    org: str | None = typer.Option(
        None, "--org", "-o", help="Filter by organization name"
    ),
    project: str | None = typer.Option(
        None, "--project", "-p", help="Filter by project name"
    ),
    agent: str | None = typer.Option(None, "--agent", "-a", help="Filter by agent name"),
    limit: int = typer.Option(20, "--limit", "-l", help="Maximum number of results"),
    format: OutputFormat = FormatOption,
):
    """List conversations."""
    try:
        Conversation = apps.get_model("chat", "Conversation")
        Organization = apps.get_model("organizations", "Organization")
        Project = apps.get_model("projects", "Project")

        # Build query with related objects
        conversations = Conversation.objects.all().select_related(
            "organization", "project", "created_by"
        )

        # Apply organization filter
        org_name = get_organization_filter(org)
        if org_name:
            try:
                organization = Organization.objects.get(name=org_name)
                conversations = conversations.filter(organization=organization)
            except Organization.DoesNotExist:
                print_error(f"Organization not found: {org_name}")
                raise typer.Exit(code=1)

        # Apply project filter
        if project:
            try:
                project_obj = Project.objects.get(name=project)
                conversations = conversations.filter(project=project_obj)
            except Project.DoesNotExist:
                print_error(f"Project not found: {project}")
                raise typer.Exit(code=1)

        # Apply agent filter
        if agent:
            conversations = conversations.filter(agent_name__icontains=agent)

        # Apply limit
        conversations = conversations[:limit]

        if not conversations:
            if format == OutputFormat.JSON:
                print_json([])
            else:
                console.print("No conversations found.", style="yellow")
            return

        def build_json(conv):
            return {
                "id": conv.id,
                "title": conv.get_title(),
                "agent_name": conv.agent_name,
                "organization": conv.organization.name if conv.organization else None,
                "project": conv.project.name if conv.project else None,
                "created_by": conv.created_by.username if conv.created_by else None,
                "message_count": conv.message_count(),
                "created_at": conv.created_at.isoformat() if conv.created_at else None,
                "updated_at": conv.updated_at.isoformat() if conv.updated_at else None,
            }

        def build_row(conv):
            title = conv.get_title()
            if len(title) > 40:
                title = title[:37] + "..."
            return [
                str(conv.id),
                title,
                conv.agent_name,
                conv.project.name if conv.project else "N/A",
                str(conv.message_count()),
                format_date(conv.updated_at),
            ]

        columns = [
            ("ID", "dim"),
            ("Title", "cyan", True),
            ("Agent", "yellow"),
            ("Project", "green"),
            ("Msgs", "blue"),
            ("Updated", "magenta"),
        ]

        output_list(
            items=list(conversations),
            format=format,
            table_title="Conversations",
            columns=columns,
            row_builder=build_row,
            json_builder=build_json,
        )

    except typer.Exit:
        raise
    except Exception as e:
        print_error(f"Error listing conversations: {e}")
        raise typer.Exit(code=1)


@chats_app.command(name="show")
@with_django
def show_chat(
    conversation_id: int = typer.Argument(..., help="Conversation ID"),
    messages: bool = typer.Option(
        False, "--messages", "-m", help="Show conversation messages"
    ),
    limit: int = typer.Option(
        20, "--limit", "-l", help="Maximum messages to show (with --messages)"
    ),
    format: OutputFormat = FormatOption,
):
    """Show detailed information about a conversation."""
    try:
        Conversation = apps.get_model("chat", "Conversation")

        try:
            conversation = Conversation.objects.select_related(
                "organization", "project", "created_by"
            ).get(id=conversation_id)
        except Conversation.DoesNotExist:
            print_error(f"Conversation not found: {conversation_id}")
            raise typer.Exit(code=1)

        # Get messages if requested
        conv_messages = list(conversation.messages.all()[:limit]) if messages else []

        def build_json(conv):
            data = {
                "id": conv.id,
                "title": conv.get_title(),
                "agent_name": conv.agent_name,
                "organization": conv.organization.name if conv.organization else None,
                "project": conv.project.name if conv.project else None,
                "created_by": conv.created_by.username if conv.created_by else None,
                "message_count": conv.message_count(),
                "user_message_count": conv.user_message_count(),
                "created_at": conv.created_at.isoformat() if conv.created_at else None,
                "updated_at": conv.updated_at.isoformat() if conv.updated_at else None,
            }
            if messages:
                data["messages"] = [
                    {
                        "id": msg.id,
                        "role": msg.role,
                        "content": msg.content,
                        "model_used": msg.model_used or None,
                        "token_count": msg.token_count,
                        "created_at": msg.created_at.isoformat(),
                    }
                    for msg in conv_messages
                ]
            return data

        def build_panel(conv):
            details = f"""
[bold cyan]Title:[/] {conv.get_title()}
[bold yellow]Agent:[/] {conv.agent_name}

[bold magenta]Location:[/]
  Organization: {conv.organization.name if conv.organization else 'N/A'}
  Project: {conv.project.name if conv.project else 'N/A'}

[bold blue]Statistics:[/]
  Total Messages: {conv.message_count()}
  User Messages: {conv.user_message_count()}

[bold white]Metadata:[/]
  Created: {format_timestamp(conv.created_at)}
  Updated: {format_timestamp(conv.updated_at)}
  Created By: {conv.created_by.username if conv.created_by else 'N/A'}
  ID: {conv.id}
"""
            panel = Panel(
                details, title=f"Conversation: {conv.get_title()}", border_style="cyan"
            )
            console.print(panel)

            # Show messages if requested
            if messages and conv_messages:
                console.print(f"\n[bold]Messages[/] (showing {len(conv_messages)}):\n")
                for msg in conv_messages:
                    role_style = {
                        "user": "green",
                        "assistant": "cyan",
                        "system": "yellow",
                    }.get(msg.role, "white")

                    role_label = f"[bold {role_style}]{msg.get_role_display()}[/]"
                    timestamp = format_timestamp(msg.created_at)

                    console.print(f"{role_label} [{timestamp}]")

                    # Truncate long messages in table mode
                    content = msg.content
                    if len(content) > 500:
                        content = content[:497] + "..."
                    console.print(f"  {content}\n")

                if conv.message_count() > limit:
                    remaining = conv.message_count() - limit
                    console.print(
                        f"[dim]... and {remaining} more messages (use --limit to see more)[/]"
                    )

        output_item(
            item=conversation,
            format=format,
            panel_builder=build_panel,
            json_builder=build_json,
        )

    except typer.Exit:
        raise
    except Exception as e:
        print_error(f"Error showing conversation: {e}")
        raise typer.Exit(code=1)


@chats_app.command(name="delete")
@with_django
def delete_chat(
    conversation_id: int = typer.Argument(..., help="Conversation ID to delete"),
    force: bool = typer.Option(
        False, "--force", "-f", help="Skip confirmation prompt"
    ),
):
    """Delete a conversation and all its messages."""
    try:
        Conversation = apps.get_model("chat", "Conversation")

        try:
            conversation = Conversation.objects.select_related(
                "project"
            ).get(id=conversation_id)
        except Conversation.DoesNotExist:
            print_error(f"Conversation not found: {conversation_id}")
            raise typer.Exit(code=1)

        title = conversation.get_title()
        msg_count = conversation.message_count()

        # Confirm deletion unless --force is used
        if not force:
            console.print(
                f"About to delete conversation: [cyan]{title}[/] "
                f"(ID: {conversation_id}, {msg_count} messages)"
            )
            confirm = typer.confirm("Are you sure you want to delete this conversation?")
            if not confirm:
                console.print("Cancelled.", style="yellow")
                raise typer.Exit(code=0)

        # Delete the conversation (messages cascade)
        conversation.delete()
        print_success(f"Deleted conversation '{title}' (ID: {conversation_id})")

    except typer.Exit:
        raise
    except Exception as e:
        print_error(f"Error deleting conversation: {e}")
        raise typer.Exit(code=1)
