"""
Tests for Skill Execution Harness.
"""

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from accounts.models import Account
from documents.models import Document, Markdown, TextDocument
from events.harness import (
    ExternalCallHandler,
    OperationAuditLog,
    OperationType,
    ScopedProjectAPI,
    ScopedProjectAPIError,
    SkillExecutionContext,
    SkillExecutionHarness,
)
from events.models import EventTrigger, EventTriggerRun, EventType
from projects.models import Project

User = get_user_model()


@pytest.fixture
def organization():
    """Create a test organization."""
    return Account.objects.create(name="Test Org", slug="test-org")


@pytest.fixture
def user(organization):
    """Create a test user."""
    user = User.objects.create_user(
        username="testuser",
        email="test@example.com",
        password="testpass123",
    )
    organization.add_user(user)
    return user


@pytest.fixture
def project(organization, user):
    """Create a test project."""
    return Project.objects.create(
        organization=organization,
        name="Test Project",
        working_directory="/tmp/test",
        created_by=user,
    )


@pytest.fixture
def other_organization():
    """Create another organization for isolation tests."""
    return Account.objects.create(name="Other Org", slug="other-org")


@pytest.fixture
def other_project(other_organization, user):
    """Create a project in another org."""
    return Project.objects.create(
        organization=other_organization,
        name="Other Project",
        working_directory="/tmp/other",
        created_by=user,
    )


@pytest.fixture
def trigger(organization, user):
    """Create a test trigger."""
    return EventTrigger.objects.create(
        organization=organization,
        name="Test Trigger",
        event_type=EventType.EMAIL_RECEIVED,
        skills=["test-skill"],
        run_async=False,
        created_by=user,
    )


@pytest.fixture
def trigger_run(organization, trigger):
    """Create a test trigger run."""
    return EventTriggerRun.objects.create(
        organization=organization,
        trigger=trigger,
        source_type="email_message",
        source_id=1,
        inputs={"test": "data"},
    )


@pytest.fixture
def project_trigger(organization, project, user):
    """Create a project-scoped trigger."""
    return EventTrigger.objects.create(
        organization=organization,
        project=project,
        name="Project Trigger",
        event_type=EventType.DOCUMENT_CREATED,
        skills=["test-skill"],
        run_async=False,
        created_by=user,
    )


@pytest.fixture
def project_trigger_run(organization, project_trigger):
    """Create a trigger run for project-scoped trigger."""
    return EventTriggerRun.objects.create(
        organization=organization,
        trigger=project_trigger,
        source_type="document",
        source_id=1,
        inputs={"document_type": "MarkdownDocument"},
    )


@pytest.mark.django_db
class TestSkillExecutionContext:
    """Tests for SkillExecutionContext."""

    def test_create_context_directly(self):
        """Test creating context directly."""
        context = SkillExecutionContext(
            organization_id=1,
            project_id=2,
            trigger_run_id=3,
            source_type="email_message",
            source_id=4,
        )

        assert context.organization_id == 1
        assert context.project_id == 2
        assert context.trigger_run_id == 3
        assert context.source_type == "email_message"
        assert context.source_id == 4
        assert context.started_at is not None

    def test_context_is_immutable(self):
        """Test that context is frozen (immutable)."""
        context = SkillExecutionContext(
            organization_id=1,
            trigger_run_id=2,
            source_type="test",
            source_id=3,
        )

        with pytest.raises(AttributeError):
            context.organization_id = 999

    def test_context_validation(self):
        """Test context validates required fields."""
        with pytest.raises(ValueError, match="organization_id must be positive"):
            SkillExecutionContext(
                organization_id=0,
                trigger_run_id=1,
                source_type="test",
                source_id=1,
            )

        with pytest.raises(ValueError, match="trigger_run_id must be positive"):
            SkillExecutionContext(
                organization_id=1,
                trigger_run_id=0,
                source_type="test",
                source_id=1,
            )

    def test_from_trigger_run(self, trigger_run):
        """Test creating context from trigger run."""
        context = SkillExecutionContext.from_trigger_run(trigger_run)

        assert context.organization_id == trigger_run.organization_id
        assert context.project_id is None  # org-wide trigger
        assert context.trigger_run_id == trigger_run.id
        assert context.source_type == "email_message"
        assert context.source_id == 1

    def test_from_project_trigger_run(self, project_trigger_run, project):
        """Test creating context from project-scoped trigger run."""
        context = SkillExecutionContext.from_trigger_run(project_trigger_run)

        assert context.organization_id == project_trigger_run.organization_id
        assert context.project_id == project.id
        assert context.trigger_run_id == project_trigger_run.id

    def test_default_allowed_document_types(self, trigger_run):
        """Test default allowed document types."""
        context = SkillExecutionContext.from_trigger_run(trigger_run)

        assert "MarkdownDocument" in context.allowed_document_types
        assert "YooptaDocument" in context.allowed_document_types
        assert "TextDocument" in context.allowed_document_types


@pytest.mark.django_db
class TestScopedProjectAPI:
    """Tests for ScopedProjectAPI."""

    def test_get_organization(self, organization, trigger_run):
        """Test getting the scoped organization."""
        context = SkillExecutionContext.from_trigger_run(trigger_run)
        api = ScopedProjectAPI(context)

        org = api.organization
        assert org.id == organization.id
        assert org.name == "Test Org"

    def test_get_project_when_scoped(self, project, project_trigger_run):
        """Test getting project when scoped."""
        context = SkillExecutionContext.from_trigger_run(project_trigger_run)
        api = ScopedProjectAPI(context)

        proj = api.project
        assert proj.id == project.id
        assert proj.name == "Test Project"

    def test_get_project_when_org_wide(self, trigger_run):
        """Test project is None for org-wide triggers."""
        context = SkillExecutionContext.from_trigger_run(trigger_run)
        api = ScopedProjectAPI(context)

        assert api.project is None

    def test_get_document_in_scope(self, organization, project, trigger_run, user):
        """Test getting a document within scope."""
        # Create a document in the same org using Markdown subclass
        doc = Markdown.objects.create(
            organization=organization,
            name="Test Doc",
            content="Test content",
            created_by=user,
        )

        context = SkillExecutionContext.from_trigger_run(trigger_run)
        api = ScopedProjectAPI(context)

        result = api.get_document(doc.id)
        assert result.id == doc.id

    def test_get_document_wrong_org(
        self, organization, other_organization, trigger_run, user
    ):
        """Test that documents from other orgs are blocked."""
        # Create document in different org using Markdown subclass
        doc = Markdown.objects.create(
            organization=other_organization,
            name="Other Org Doc",
            content="Content",
            created_by=user,
        )

        context = SkillExecutionContext.from_trigger_run(trigger_run)
        api = ScopedProjectAPI(context)

        with pytest.raises(ScopedProjectAPIError, match="not in scope"):
            api.get_document(doc.id)

    def test_get_document_wrong_project(
        self, organization, project, project_trigger_run, user
    ):
        """Test that documents from other projects are blocked."""
        # Create another project in same org
        other_project = Project.objects.create(
            organization=organization,
            name="Other Project Same Org",
            working_directory="/tmp/other2",
            created_by=user,
        )

        # Create document in other project using Markdown subclass
        doc = Markdown.objects.create(
            organization=organization,
            project=other_project,
            name="Other Project Doc",
            content="Content",
            created_by=user,
        )

        context = SkillExecutionContext.from_trigger_run(project_trigger_run)
        api = ScopedProjectAPI(context)

        with pytest.raises(ScopedProjectAPIError, match="not in project"):
            api.get_document(doc.id)

    def test_create_document(self, organization, trigger_run, user):
        """Test creating a document."""
        context = SkillExecutionContext.from_trigger_run(trigger_run)
        api = ScopedProjectAPI(context)

        doc = api.create_document(
            document_type="MarkdownDocument",
            name="Created Doc",
            content="Test content",
        )

        assert doc.id is not None
        assert doc.name == "Created Doc"
        assert doc.organization_id == organization.id

    def test_create_document_blocked_type(self, trigger_run):
        """Test that non-allowed document types are blocked."""
        context = SkillExecutionContext.from_trigger_run(trigger_run)
        api = ScopedProjectAPI(context)

        with pytest.raises(ScopedProjectAPIError, match="not allowed"):
            api.create_document(
                document_type="ImageDocument",  # Not in allowlist
                name="Image Doc",
                content="",
            )

    def test_create_document_limit(self, trigger_run):
        """Test document creation limit."""
        context = SkillExecutionContext.from_trigger_run(
            trigger_run, max_documents_per_run=2
        )
        api = ScopedProjectAPI(context)

        # Create 2 documents (should succeed)
        api.create_document("MarkdownDocument", "Doc 1", "Content 1")
        api.create_document("MarkdownDocument", "Doc 2", "Content 2")

        # Third should fail
        with pytest.raises(ScopedProjectAPIError, match="limit"):
            api.create_document("MarkdownDocument", "Doc 3", "Content 3")

    def test_delete_always_blocked(self, organization, trigger_run, user):
        """Test that deletion is always blocked."""
        doc = Markdown.objects.create(
            organization=organization,
            name="Test Doc",
            content="Content",
            created_by=user,
        )

        context = SkillExecutionContext.from_trigger_run(trigger_run)
        api = ScopedProjectAPI(context)

        with pytest.raises(ScopedProjectAPIError, match="Deletion not allowed"):
            api.delete_document(doc.id)


@pytest.mark.django_db
class TestExternalCallHandler:
    """Tests for ExternalCallHandler."""

    def test_default_domains_allowed(self, trigger_run):
        """Test that default domains are allowed."""
        context = SkillExecutionContext.from_trigger_run(trigger_run)
        audit_log = OperationAuditLog(context)
        handler = ExternalCallHandler(context, audit_log)

        # Test default allowed domains
        assert handler.is_allowed("https://wikipedia.org/wiki/Test")[0] is True
        assert handler.is_allowed("https://en.wikipedia.org/wiki/Test")[0] is True
        assert handler.is_allowed("https://api.github.com/repos")[0] is True
        assert handler.is_allowed("https://duckduckgo.com/search")[0] is True

    def test_custom_domain_allowed(self, trigger_run):
        """Test adding custom allowed domains."""
        context = SkillExecutionContext.from_trigger_run(
            trigger_run,
            allowed_external_domains=frozenset({"api.example.com"}),
        )
        audit_log = OperationAuditLog(context)
        handler = ExternalCallHandler(context, audit_log)

        assert handler.is_allowed("https://api.example.com/data")[0] is True

    def test_unknown_domain_blocked(self, trigger_run):
        """Test that unknown domains are blocked."""
        context = SkillExecutionContext.from_trigger_run(trigger_run)
        audit_log = OperationAuditLog(context)
        handler = ExternalCallHandler(context, audit_log)

        allowed, reason = handler.is_allowed("https://malicious-site.com/data")
        assert allowed is False
        assert "not in allowlist" in reason

    def test_rate_limiting(self, trigger_run):
        """Test rate limiting per domain."""
        context = SkillExecutionContext.from_trigger_run(
            trigger_run, rate_limit_per_domain=2
        )
        audit_log = OperationAuditLog(context)
        handler = ExternalCallHandler(context, audit_log)

        # First two calls should succeed
        handler.check_and_record("https://wikipedia.org/page1")
        handler.check_and_record("https://wikipedia.org/page2")

        # Third should fail
        with pytest.raises(ScopedProjectAPIError, match="Rate limit exceeded"):
            handler.check_and_record("https://wikipedia.org/page3")


@pytest.mark.django_db
class TestOperationAuditLog:
    """Tests for OperationAuditLog."""

    def test_log_operation(self, trigger_run):
        """Test logging operations."""
        context = SkillExecutionContext.from_trigger_run(trigger_run)
        log = OperationAuditLog(context)

        log.log(OperationType.READ, "Document", 1, {"field": "title"})

        assert len(log.entries) == 1
        assert log.entries[0]["operation"] == "read"
        assert log.entries[0]["model"] == "Document"
        assert log.entries[0]["object_id"] == 1

    def test_log_blocked_operation(self, trigger_run):
        """Test logging blocked operations."""
        context = SkillExecutionContext.from_trigger_run(trigger_run)
        log = OperationAuditLog(context)

        log.log(
            OperationType.DELETE,
            "Document",
            1,
            {},
            allowed=False,
            reason="Deletion not allowed",
        )

        assert len(log.entries) == 1
        assert log.entries[0]["allowed"] is False
        assert log.entries[0]["reason"] == "Deletion not allowed"

    def test_to_dict(self, trigger_run):
        """Test exporting log to dict."""
        context = SkillExecutionContext.from_trigger_run(trigger_run)
        log = OperationAuditLog(context)

        log.log(OperationType.READ, "Document", 1)
        log.log(OperationType.CREATE, "Document", 2)

        result = log.to_dict()

        assert result["trigger_run_id"] == trigger_run.id
        assert result["entry_count"] == 2
        assert result["blocked_operations"] == 0


@pytest.mark.django_db
class TestSkillExecutionHarness:
    """Tests for the main harness class."""

    def test_create_from_trigger_run(self, trigger_run):
        """Test creating harness from trigger run."""
        harness = SkillExecutionHarness.from_trigger_run(trigger_run)

        assert harness.context.trigger_run_id == trigger_run.id
        assert harness.api is not None
        assert harness.external is not None

    def test_harness_provides_api_access(self, organization, trigger_run):
        """Test that harness provides API access."""
        harness = SkillExecutionHarness.from_trigger_run(trigger_run)

        org = harness.organization
        assert org.id == organization.id

    def test_harness_tracks_operations(self, organization, trigger_run, user):
        """Test that harness tracks all operations."""
        harness = SkillExecutionHarness.from_trigger_run(trigger_run)

        # Create a document
        doc = harness.api.create_document(
            document_type="MarkdownDocument",
            name="Test",
            content="Content",
        )

        # Check audit log
        audit = harness.get_audit_log()
        assert audit["documents_created"] == 1
        assert any(
            e["operation"] == "create" and e["model"] == "Document"
            for e in audit["entries"]
        )

    def test_harness_with_custom_config(self, trigger_run):
        """Test harness with custom configuration."""
        harness = SkillExecutionHarness.from_trigger_run(
            trigger_run,
            max_documents_per_run=5,
            rate_limit_per_domain=3,
            allowed_external_domains=frozenset({"custom.api.com"}),
        )

        assert harness.context.max_documents_per_run == 5
        assert harness.context.rate_limit_per_domain == 3
        assert "custom.api.com" in harness.context.allowed_external_domains
