"""Tests for project email address features."""

import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from organizations.models import OrganizationUser

from accounts.models import Account
from projects.models import Project
from projects.email_utils import (
    slugify_for_email,
    generate_project_canonical_email,
    generate_alias_email,
    validate_email_alias,
    parse_inbound_email,
    resolve_email_recipient,
    get_email_domain,
)

User = get_user_model()


@pytest.mark.django_db
class TestSlugifyForEmail:
    """Tests for slugify_for_email function."""

    def test_basic_name(self):
        """Normal name converts to lowercase with hyphens."""
        assert slugify_for_email("My Project") == "my-project"

    def test_special_characters(self):
        """Special characters are removed."""
        assert slugify_for_email("Project@#$%Name") == "projectname"

    def test_unicode_characters(self):
        """Unicode characters are converted or removed."""
        assert slugify_for_email("Café Project") == "cafe-project"
        assert slugify_for_email("Ñoño") == "nono"

    def test_multiple_spaces(self):
        """Multiple spaces become single hyphens."""
        assert slugify_for_email("My   Project") == "my-project"

    def test_leading_trailing_hyphens(self):
        """Leading and trailing hyphens are stripped."""
        assert slugify_for_email("-Project-") == "project"

    def test_empty_after_slugify(self):
        """Empty result returns 'unnamed'."""
        assert slugify_for_email("@#$%") == "unnamed"
        assert slugify_for_email("") == "unnamed"


@pytest.mark.django_db
class TestGenerateCanonicalEmail:
    """Tests for canonical email generation functions."""

    def test_project_canonical_email(self):
        """Project canonical email follows format."""
        email = generate_project_canonical_email("zoea-dev", "team-zoea")
        assert email == "zoea-dev.team-zoea@zoea.studio"

    def test_long_project_slug_truncation(self):
        """Long project slugs are truncated to fit RFC 5321."""
        # Create a very long project slug
        long_slug = "a" * 60  # 60 chars
        org_slug = "org"
        email = generate_project_canonical_email(long_slug, org_slug)
        local_part = email.split("@")[0]
        assert len(local_part) <= 64


@pytest.mark.django_db
class TestGenerateAliasEmail:
    """Tests for alias email generation."""

    def test_alias_email_format(self):
        """Alias email follows format."""
        email = generate_alias_email("bob", "team-zoea")
        assert email == "bob.team-zoea@zoea.studio"


@pytest.mark.django_db
class TestValidateEmailAlias:
    """Tests for email alias validation."""

    def test_valid_aliases(self):
        """Valid aliases pass validation."""
        assert validate_email_alias("bob") is True
        assert validate_email_alias("support-team") is True
        assert validate_email_alias("sales_dept") is True
        assert validate_email_alias("project123") is True
        assert validate_email_alias("ab") is True  # Min 2 chars

    def test_invalid_aliases(self):
        """Invalid aliases fail validation."""
        # Must start with letter
        assert validate_email_alias("123abc") is False
        assert validate_email_alias("-abc") is False
        assert validate_email_alias("_abc") is False

        # Too short
        assert validate_email_alias("a") is False
        assert validate_email_alias("") is False

        # Invalid characters
        assert validate_email_alias("bob@test") is False
        assert validate_email_alias("bob.test") is False
        assert validate_email_alias("bob test") is False

        # Uppercase (must be lowercase)
        assert validate_email_alias("Bob") is False
        assert validate_email_alias("BOB") is False


@pytest.mark.django_db
class TestParseInboundEmail:
    """Tests for parsing inbound email addresses."""

    def test_two_part_address(self):
        """Two-part address is project canonical or alias format."""
        parsed = parse_inbound_email("zoea-dev.team-zoea@zoea.studio")
        assert parsed.org_slug == "team-zoea"
        assert parsed.project_slug == "zoea-dev"
        assert parsed.domain == "zoea.studio"

    def test_single_part_address(self):
        """Single part is just org slug."""
        parsed = parse_inbound_email("team-zoea@zoea.studio")
        assert parsed.org_slug == "team-zoea"
        assert parsed.project_slug is None

    def test_invalid_address_no_at(self):
        """Invalid address without @ returns empty."""
        parsed = parse_inbound_email("invalid-email")
        assert parsed.org_slug is None
        assert parsed.local_part == ""

    def test_case_insensitive_parsing(self):
        """Email parsing is case-insensitive."""
        parsed = parse_inbound_email("ZOEA-DEV.TEAM-ZOEA@ZOEA.STUDIO")
        assert parsed.org_slug == "team-zoea"
        assert parsed.project_slug == "zoea-dev"


@pytest.mark.django_db
class TestResolveEmailRecipient:
    """Tests for resolving email recipients to projects."""

    @pytest.fixture
    def org_with_projects(self):
        """Create organization with projects."""
        org = Account.objects.create(name="Team Zoea", subscription_plan="free")
        user = User.objects.create_user(
            username="testuser", email="test@example.com", password="password123"
        )
        OrganizationUser.objects.create(organization=org, user=user, is_admin=True)

        # Create projects - one is auto-created by signal, create another
        project = Project.objects.create(
            organization=org,
            name="Test Project",
            working_directory="/tmp/test",
            created_by=user,
        )
        project.email_alias = "proj"
        project.save()

        return org, project, user

    def test_resolve_project_canonical(self, org_with_projects):
        """Resolve project by canonical email."""
        _org, project, _user = org_with_projects

        resolved = resolve_email_recipient(project.canonical_email)
        assert resolved.project == project
        assert resolved.resolved_via == "project_canonical"

    def test_resolve_project_alias(self, org_with_projects):
        """Resolve project by alias email."""
        _org, project, _user = org_with_projects

        resolved = resolve_email_recipient(project.alias_email)
        assert resolved.project == project
        assert resolved.resolved_via == "project_alias"

    def test_resolve_unknown_email(self, org_with_projects):
        """Unknown email returns not_found."""
        resolved = resolve_email_recipient("unknown.unknown@zoea.studio")
        assert resolved.project is None
        assert resolved.resolved_via == "not_found"


@pytest.mark.django_db
class TestProjectEmailFields:
    """Tests for Project model email fields."""

    @pytest.fixture
    def org_and_user(self):
        """Create organization and user."""
        org = Account.objects.create(name="Test Org", subscription_plan="free")
        user = User.objects.create_user(
            username="testuser", email="test@example.com", password="password123"
        )
        OrganizationUser.objects.create(organization=org, user=user, is_admin=True)
        return org, user

    def test_canonical_email_auto_generated(self, org_and_user):
        """Canonical email is auto-generated on save."""
        org, user = org_and_user
        project = Project.objects.create(
            organization=org,
            name="My Project",
            working_directory="/tmp/test",
            created_by=user,
        )
        assert project.canonical_email is not None
        assert "my-project" in project.canonical_email
        assert org.slug in project.canonical_email

    def test_canonical_email_based_on_slug(self, org_and_user):
        """Canonical email is based on slug, not name directly."""
        org, user = org_and_user
        project = Project.objects.create(
            organization=org,
            name="Original Name",
            working_directory="/tmp/test",
            created_by=user,
        )

        # Canonical email is based on slug which is set from name at creation
        assert "original-name" in project.canonical_email
        assert project.slug == "original-name"

        # Changing name doesn't change slug (slug is immutable once set)
        project.name = "New Name"
        project.save()
        project.refresh_from_db()

        # Slug and canonical_email remain based on original name
        assert project.slug == "original-name"
        assert "original-name" in project.canonical_email

    def test_alias_email_property(self, org_and_user):
        """alias_email property returns full email when alias set."""
        org, user = org_and_user
        project = Project.objects.create(
            organization=org,
            name="My Project",
            working_directory="/tmp/test",
            created_by=user,
        )

        # No alias initially
        assert project.alias_email is None

        # Set alias
        project.email_alias = "myalias"
        project.save()
        project.refresh_from_db()

        assert project.alias_email is not None
        assert "myalias" in project.alias_email
        assert org.slug in project.alias_email

    def test_alias_uniqueness_in_organization(self, org_and_user):
        """Alias must be unique within organization (database constraint)."""
        from django.db import IntegrityError

        org, user = org_and_user

        Project.objects.create(
            organization=org,
            name="Project One",
            working_directory="/tmp/p1",
            created_by=user,
            email_alias="shared-alias",
        )

        project2 = Project.objects.create(
            organization=org,
            name="Project Two",
            working_directory="/tmp/p2",
            created_by=user,
        )
        project2.email_alias = "shared-alias"

        # Database unique_together constraint prevents duplicate aliases
        with pytest.raises(IntegrityError):
            project2.save()


@pytest.mark.django_db
class TestGetEmailDomain:
    """Tests for email domain configuration."""

    def test_default_domain(self):
        """Default domain is zoea.studio."""
        assert get_email_domain() == "zoea.studio"
