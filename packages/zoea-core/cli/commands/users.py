"""User management commands."""

import getpass

import typer
from django.apps import apps
from django.contrib.auth import get_user_model
from django.db import transaction
from rich.panel import Panel

from cli.utils.django_context import with_django
from cli.utils.formatting import (
    FormatOption,
    OutputFormat,
    console,
    print_error,
    print_json,
    print_success,
)

# Create users command group
users_app = typer.Typer(
    name="users",
    help="Manage users",
    rich_markup_mode="rich",
)


@users_app.callback(invoke_without_command=True)
def users_callback(ctx: typer.Context):
    """Users command group."""
    if ctx.invoked_subcommand is None:
        console.print("[yellow]Use 'zoea users create' to create a new user[/]")
        raise typer.Exit(0)


@users_app.command(name="create")
@with_django
def create_user(
    username: str = typer.Option(
        None,
        "--username",
        "-u",
        help="Username for the new user (will prompt if not provided)",
    ),
    email: str = typer.Option(
        None,
        "--email",
        "-e",
        help="Email address for the new user (will prompt if not provided)",
    ),
    password: str = typer.Option(
        None,
        "--password",
        "-p",
        help="Password for the new user (will prompt securely if not provided)",
    ),
    org_name: str = typer.Option(
        None,
        "--org-name",
        "-o",
        help="Name for the user's organization (defaults to '{username}'s Organization')",
    ),
    subscription: str = typer.Option(
        "free",
        "--subscription",
        "-s",
        help="Subscription plan (free, pro, enterprise)",
    ),
    max_users: int = typer.Option(
        5,
        "--max-users",
        "-m",
        help="Maximum number of users allowed in the organization",
    ),
    skip_email_verification: bool = typer.Option(
        False,
        "--skip-email-verification",
        help="Skip email verification (mark email as verified immediately)",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        help="Skip confirmation prompts (non-interactive mode)",
    ),
    format: OutputFormat = FormatOption,
):
    """
    Create a new user with organization setup.

    This command creates:
    - A new user account
    - An organization with the user as owner
    - A default project (created automatically by signals)
    - A default workspace (created automatically by signals)
    - A default clipboard (created automatically by signals)

    Examples:
        # Interactive mode (prompts for all required fields)
        zoea users create

        # With all options specified
        zoea users create --username alice --email alice@example.com --password secret123 --org-name "Alice's Company"

        # For development (skip email verification)
        zoea users create --username dev --email dev@localhost --password dev --skip-email-verification
    """
    User = get_user_model()

    # Interactive prompts for missing values
    if not username:
        username = typer.prompt("Username")

    if not email:
        email = typer.prompt("Email")

    if not password:
        password = getpass.getpass("Password: ")
        password_confirm = getpass.getpass("Confirm password: ")
        if password != password_confirm:
            print_error("Passwords do not match")
            raise typer.Exit(code=1)

    # Validate subscription plan
    valid_plans = ["free", "pro", "enterprise"]
    if subscription not in valid_plans:
        print_error(f"Invalid subscription plan: {subscription}. Must be one of: {', '.join(valid_plans)}")
        raise typer.Exit(code=1)

    try:
        # Check if user already exists
        if User.objects.filter(username=username).exists():
            print_error(f"User with username '{username}' already exists")
            raise typer.Exit(code=1)

        if User.objects.filter(email=email).exists():
            print_error(f"User with email '{email}' already exists")
            raise typer.Exit(code=1)

        # Show confirmation unless --force is used
        if not force:
            org_display = org_name if org_name else f"{username}'s Organization"
            console.print("\n[bold]User Details:[/]")
            console.print(f"  Username: {username}")
            console.print(f"  Email: {email}")
            console.print(f"  Organization: {org_display}")
            console.print(f"  Subscription: {subscription}")
            console.print(f"  Max Users: {max_users}")
            console.print(f"  Skip Email Verification: {skip_email_verification}\n")

            confirm = typer.confirm("Create this user?")
            if not confirm:
                console.print("[yellow]Cancelled[/]")
                raise typer.Exit(0)

        # Create user and organization in a transaction
        with transaction.atomic():
            # Import here to avoid circular imports
            from accounts.utils import initialize_user_organization

            # Create the user
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password,
            )

            # Mark email as verified if requested
            if skip_email_verification:
                try:
                    from allauth.account.models import EmailAddress
                    EmailAddress.objects.create(
                        user=user,
                        email=email,
                        verified=True,
                        primary=True,
                    )
                except Exception as e:
                    # Log but don't fail if EmailAddress creation fails
                    console.print(f"[yellow]Warning: Could not mark email as verified: {e}[/]")

            # Initialize the full organization setup
            result = initialize_user_organization(
                user=user,
                org_name=org_name,
                subscription_plan=subscription,
                max_users=max_users,
            )

            organization = result["organization"]
            project = result["project"]
            workspace = result["workspace"]
            clipboard = result["clipboard"]

        # Output based on format
        if format == OutputFormat.JSON:
            print_json({
                "user": {
                    "id": user.id,
                    "username": user.username,
                    "email": user.email,
                    "email_verified": skip_email_verification,
                },
                "organization": {
                    "id": organization.id,
                    "name": organization.name,
                    "slug": organization.slug,
                    "subscription_plan": organization.subscription_plan,
                    "max_users": organization.max_users,
                },
                "project": {
                    "id": project.id,
                    "name": project.name,
                    "working_directory": project.working_directory,
                },
                "workspace": {
                    "id": workspace.id,
                    "name": workspace.name,
                },
                "clipboard": {
                    "id": clipboard.id,
                    "name": clipboard.name,
                },
            })
        else:
            print_success(f"Created user '{user.username}' successfully!")

            # Display comprehensive summary
            details = f"""
[bold cyan]User:[/]
  ID: {user.id}
  Username: {user.username}
  Email: {user.email}
  Email Verified: {'Yes' if skip_email_verification else 'No (verification email would be sent in production)'}

[bold yellow]Organization:[/]
  ID: {organization.id}
  Name: {organization.name}
  Slug: {organization.slug}
  Subscription: {organization.get_subscription_plan_display()}
  Max Users: {organization.max_users}
  Owner: {user.username}

[bold green]Project:[/]
  ID: {project.id}
  Name: {project.name}
  Working Directory: {project.working_directory}

[bold blue]Workspace:[/]
  ID: {workspace.id}
  Name: {workspace.name}
  Path: {workspace.get_full_path()}

[bold magenta]Clipboard:[/]
  ID: {clipboard.id}
  Name: {clipboard.name}
  Active: {'Yes' if clipboard.is_active else 'No'}
"""

            panel = Panel(details, title="User Created Successfully", border_style="green")
            console.print(panel)

            # Show next steps
            console.print("\n[bold]Next Steps:[/]")
            if not skip_email_verification:
                console.print("  1. User needs to verify their email before logging in")
                console.print("  2. In development, use --skip-email-verification to bypass this")
            else:
                console.print("  1. User can log in immediately with the provided credentials")
            console.print(f"  {'2' if not skip_email_verification else '2'}. Access admin: /admin/auth/user/{user.id}/change/")
            console.print(f"  {'3' if not skip_email_verification else '3'}. Organization: /admin/accounts/account/{organization.id}/change/\n")

    except typer.Exit:
        raise
    except ValueError as e:
        print_error(f"Validation error: {e}")
        raise typer.Exit(code=1)
    except Exception as e:
        print_error(f"Error creating user: {e}")
        raise typer.Exit(code=1)
