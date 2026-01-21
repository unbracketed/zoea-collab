"""Zoea Studio CLI - Main entry point."""

import typer

from cli.commands.chats import chats_app
from cli.commands.clipboard import clipboard_app
from cli.commands.doctor import doctor_command
from cli.commands.documents import documents_app
from cli.commands.projects import projects_app
from cli.commands.users import users_app
from cli.commands.workflows import workflows_app
from cli.commands.workspaces import workspaces_app
from cli.utils.formatting import console

# Create main Typer app
app = typer.Typer(
    name="zoea",
    help="Zoea Studio CLI - Project and Workspace Management",
    rich_markup_mode="rich",
    no_args_is_help=True,
)

# Register command groups
app.add_typer(projects_app, name="projects")
app.add_typer(workspaces_app, name="workspaces")
app.add_typer(workflows_app, name="workflows")
app.add_typer(documents_app, name="documents")
app.add_typer(clipboard_app, name="clipboard")
app.add_typer(chats_app, name="chats")
app.add_typer(users_app, name="users")

# Register standalone commands
app.command(name="doctor")(doctor_command)


@app.callback()
def main_callback():
    """Zoea Studio CLI for managing projects, workspaces, documents, and more."""
    pass


def main():
    """Main entry point for the CLI."""
    app()


if __name__ == "__main__":
    main()
