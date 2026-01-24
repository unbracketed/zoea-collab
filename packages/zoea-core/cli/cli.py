"""Zoea Studio CLI - Main entry point."""

import typer

from cli.commands.chats import chats_app
from cli.commands.doctor import doctor_command
from cli.commands.documents import documents_app
from cli.commands.events import events_app
from cli.commands.organizations import organizations_app
from cli.commands.projects import projects_app
from cli.commands.skills import skills_app
from cli.commands.users import users_app
from cli.commands.webhooks import webhooks_app
from cli.commands.workflows import workflows_app
from cli.utils.formatting import console

# Create main Typer app
app = typer.Typer(
    name="zoea",
    help="Zoea Studio CLI - Project Management",
    rich_markup_mode="rich",
    no_args_is_help=True,
)

# Register command groups
app.add_typer(projects_app, name="projects")
app.add_typer(workflows_app, name="workflows")
app.add_typer(documents_app, name="documents")
app.add_typer(chats_app, name="chats")
app.add_typer(users_app, name="users")
app.add_typer(organizations_app, name="organizations")
app.add_typer(events_app, name="events")
app.add_typer(skills_app, name="skills")
app.add_typer(webhooks_app, name="webhooks")

# Register standalone commands
app.command(name="doctor")(doctor_command)


@app.callback()
def main_callback():
    """Zoea Studio CLI for managing projects, documents, and more."""
    pass


def main():
    """Main entry point for the CLI."""
    app()


if __name__ == "__main__":
    main()
