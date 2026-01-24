"""Tests for the users CLI command."""

import pytest
from django.contrib.auth import get_user_model
from typer.testing import CliRunner

from cli.cli import app

User = get_user_model()


@pytest.fixture
def runner():
    """Create a CLI test runner."""
    return CliRunner()


@pytest.mark.django_db
class TestUsersCreate:
    """Tests for the 'zoea users create' command."""

    def test_create_user_with_all_options(self, runner):
        """Test creating a user with all options specified."""
        result = runner.invoke(
            app,
            [
                "users",
                "create",
                "--username",
                "testuser",
                "--email",
                "testuser@example.com",
                "--password",
                "testpass123",
                "--org-name",
                "Test Organization",
                "--subscription",
                "pro",
                "--max-users",
                "10",
                "--skip-email-verification",
                "--force",
                "--format",
                "json",
            ],
        )

        assert result.exit_code == 0
        assert "testuser" in result.stdout

        # Verify user was created
        user = User.objects.get(username="testuser")
        assert user.email == "testuser@example.com"

        # Verify organization was created
        from organizations.models import Organization, OrganizationUser

        org = Organization.objects.get(name="Test Organization")
        assert org.account.subscription_plan == "pro"
        assert org.account.max_users == 10

        # Verify user is member and owner
        org_user = OrganizationUser.objects.get(user=user, organization=org)
        assert org_user.is_admin is True

    def test_create_user_with_defaults(self, runner):
        """Test creating a user with default organization settings."""
        result = runner.invoke(
            app,
            [
                "users",
                "create",
                "--username",
                "defaultuser",
                "--email",
                "defaultuser@example.com",
                "--password",
                "testpass123",
                "--skip-email-verification",
                "--force",
            ],
        )

        assert result.exit_code == 0

        # Verify user was created
        user = User.objects.get(username="defaultuser")
        assert user.email == "defaultuser@example.com"

        # Verify default organization was created
        from organizations.models import Organization

        org = Organization.objects.get(organization_users__user=user)
        assert org.name == "defaultuser's Organization"
        assert org.account.subscription_plan == "free"
        assert org.account.max_users == 5

    def test_create_user_skips_email_verification(self, runner):
        """Test that --skip-email-verification marks email as verified."""
        result = runner.invoke(
            app,
            [
                "users",
                "create",
                "--username",
                "verifieduser",
                "--email",
                "verified@example.com",
                "--password",
                "testpass123",
                "--skip-email-verification",
                "--force",
            ],
        )

        assert result.exit_code == 0

        # Verify email is marked as verified
        from allauth.account.models import EmailAddress

        user = User.objects.get(username="verifieduser")
        email_address = EmailAddress.objects.get(user=user, email="verified@example.com")
        assert email_address.verified is True
        assert email_address.primary is True

    def test_create_user_duplicate_username(self, runner):
        """Test that creating a user with duplicate username fails."""
        # Create first user
        User.objects.create_user(
            username="duplicate",
            email="user1@example.com",
            password="testpass123",
        )

        # Try to create second user with same username
        result = runner.invoke(
            app,
            [
                "users",
                "create",
                "--username",
                "duplicate",
                "--email",
                "user2@example.com",
                "--password",
                "testpass123",
                "--force",
            ],
        )

        assert result.exit_code == 1
        assert "already exists" in result.stdout

    def test_create_user_duplicate_email(self, runner):
        """Test that creating a user with duplicate email fails."""
        # Create first user
        User.objects.create_user(
            username="user1",
            email="duplicate@example.com",
            password="testpass123",
        )

        # Try to create second user with same email
        result = runner.invoke(
            app,
            [
                "users",
                "create",
                "--username",
                "user2",
                "--email",
                "duplicate@example.com",
                "--password",
                "testpass123",
                "--force",
            ],
        )

        assert result.exit_code == 1
        assert "already exists" in result.stdout

    def test_create_user_invalid_subscription(self, runner):
        """Test that invalid subscription plan is rejected."""
        result = runner.invoke(
            app,
            [
                "users",
                "create",
                "--username",
                "testuser",
                "--email",
                "testuser@example.com",
                "--password",
                "testpass123",
                "--subscription",
                "invalid",
                "--force",
            ],
        )

        assert result.exit_code == 1
        assert "Invalid subscription plan" in result.stdout

    def test_create_user_creates_full_setup(self, runner):
        """Test that creating a user creates organization and project."""
        result = runner.invoke(
            app,
            [
                "users",
                "create",
                "--username",
                "fullsetup",
                "--email",
                "fullsetup@example.com",
                "--password",
                "testpass123",
                "--skip-email-verification",
                "--force",
                "--format",
                "json",
            ],
        )

        assert result.exit_code == 0

        # Parse JSON output
        import json

        output = json.loads(result.stdout)

        # Verify all components were created
        assert "user" in output
        assert "organization" in output
        assert "project" in output

        # Verify IDs are present
        assert output["user"]["id"] is not None
        assert output["organization"]["id"] is not None
        assert output["project"]["id"] is not None

    def test_create_user_json_format(self, runner):
        """Test that JSON format output is valid."""
        result = runner.invoke(
            app,
            [
                "users",
                "create",
                "--username",
                "jsontest",
                "--email",
                "jsontest@example.com",
                "--password",
                "testpass123",
                "--skip-email-verification",
                "--force",
                "--format",
                "json",
            ],
        )

        assert result.exit_code == 0

        # Verify JSON is valid
        import json

        output = json.loads(result.stdout)
        assert output["user"]["username"] == "jsontest"
        assert output["user"]["email"] == "jsontest@example.com"
        assert output["user"]["email_verified"] is True

    def test_create_user_table_format(self, runner):
        """Test that table format (default) produces readable output."""
        result = runner.invoke(
            app,
            [
                "users",
                "create",
                "--username",
                "tabletest",
                "--email",
                "tabletest@example.com",
                "--password",
                "testpass123",
                "--skip-email-verification",
                "--force",
            ],
        )

        assert result.exit_code == 0
        assert "Created user 'tabletest' successfully!" in result.stdout
        assert "User:" in result.stdout
        assert "Organization:" in result.stdout
        assert "Project:" in result.stdout
        assert "Next Steps:" in result.stdout
