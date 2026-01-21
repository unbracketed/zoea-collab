"""
Tests for scoped tools used in skill execution.
"""

import json

import pytest
from django.contrib.auth import get_user_model

from accounts.models import Account
from documents.models import Document, Markdown, TextDocument
from events.harness import SkillExecutionContext, SkillExecutionHarness
from events.models import EventTrigger, EventTriggerRun, EventType
from events.scoped_tools import (
    ScopedDocumentCreateTool,
    ScopedDocumentListTool,
    ScopedDocumentReaderTool,
    ScopedProjectInfoTool,
    create_scoped_tools,
)
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
def trigger(organization, project, user):
    """Create a project-scoped trigger."""
    return EventTrigger.objects.create(
        organization=organization,
        project=project,
        name="Test Trigger",
        event_type=EventType.DOCUMENT_CREATED,
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
        source_type="document",
        source_id=1,
        inputs={"test": "data"},
    )


@pytest.fixture
def harness(trigger_run):
    """Create a harness from trigger run."""
    return SkillExecutionHarness.from_trigger_run(trigger_run)


@pytest.fixture
def test_document(organization, project, user):
    """Create a test document."""
    return Markdown.objects.create(
        organization=organization,
        project=project,
        name="Test Document",
        content="This is test content.",
        created_by=user,
    )


@pytest.mark.django_db
class TestScopedDocumentReaderTool:
    """Tests for ScopedDocumentReaderTool."""

    def test_read_document_success(self, harness, test_document):
        """Test reading a document successfully."""
        tool = ScopedDocumentReaderTool(harness)
        result = json.loads(tool.forward(test_document.id))

        assert result["id"] == test_document.id
        assert result["name"] == "Test Document"
        assert result["document_type"] == "Markdown"
        assert "content" in result

    def test_read_document_not_found(self, harness):
        """Test reading a non-existent document."""
        tool = ScopedDocumentReaderTool(harness)
        result = json.loads(tool.forward(99999))

        assert "error" in result

    def test_tool_has_correct_metadata(self, harness):
        """Test tool has correct name and description."""
        tool = ScopedDocumentReaderTool(harness)

        assert tool.name == "read_document"
        assert "document" in tool.description.lower()


@pytest.mark.django_db
class TestScopedDocumentListTool:
    """Tests for ScopedDocumentListTool."""

    def test_list_documents(self, harness, test_document):
        """Test listing documents."""
        tool = ScopedDocumentListTool(harness)
        result = json.loads(tool.forward())

        assert isinstance(result, list)
        assert len(result) >= 1
        assert any(d["id"] == test_document.id for d in result)

    def test_list_documents_with_type_filter(self, harness, test_document):
        """Test filtering by document type."""
        tool = ScopedDocumentListTool(harness)

        # Filter for existing type
        result = json.loads(tool.forward(document_type="MarkdownDocument"))
        assert isinstance(result, list)

        # Filter for non-existent type
        result = json.loads(tool.forward(document_type="NonExistent"))
        assert result == []

    def test_list_documents_with_limit(self, harness, organization, project, user):
        """Test document limit."""
        # Create multiple documents using Markdown subclass
        for i in range(5):
            Markdown.objects.create(
                organization=organization,
                project=project,
                name=f"Doc {i}",
                content=f"Content {i}",
                created_by=user,
            )

        tool = ScopedDocumentListTool(harness)
        result = json.loads(tool.forward(limit=3))

        assert len(result) == 3


@pytest.mark.django_db
class TestScopedDocumentCreateTool:
    """Tests for ScopedDocumentCreateTool."""

    def test_create_document_success(self, harness):
        """Test creating a document."""
        tool = ScopedDocumentCreateTool(harness)
        result = json.loads(
            tool.forward(
                document_type="MarkdownDocument",
                name="New Doc",
                content="New content",
            )
        )

        assert result["success"] is True
        assert result["id"] is not None
        assert result["name"] == "New Doc"

    def test_create_document_blocked_type(self, harness):
        """Test creating with blocked document type."""
        tool = ScopedDocumentCreateTool(harness)
        result = json.loads(
            tool.forward(
                document_type="ImageDocument",  # Not allowed
                name="Image",
                content="",
            )
        )

        assert result["success"] is False
        assert "error" in result


@pytest.mark.django_db
class TestScopedProjectInfoTool:
    """Tests for ScopedProjectInfoTool."""

    def test_get_context_info(self, harness, organization, project):
        """Test getting context information."""
        tool = ScopedProjectInfoTool(harness)
        result = json.loads(tool.forward())

        assert result["organization"]["id"] == organization.id
        assert result["organization"]["name"] == "Test Org"
        assert result["project"]["id"] == project.id
        assert result["project"]["name"] == "Test Project"
        assert result["scope"] == "project"
        assert "MarkdownDocument" in result["allowed_document_types"]


@pytest.mark.django_db
class TestCreateScopedTools:
    """Tests for create_scoped_tools function."""

    def test_creates_all_tools(self, harness):
        """Test that all expected tools are created."""
        tools = create_scoped_tools(harness)

        tool_names = [t.name for t in tools]

        assert "read_document" in tool_names
        assert "list_documents" in tool_names
        assert "create_document" in tool_names
        assert "get_source_entity" in tool_names
        assert "fetch_url" in tool_names
        assert "get_context_info" in tool_names

    def test_search_tool_only_for_project_scope(self, trigger_run):
        """Test that search tool is only added for project-scoped triggers."""
        # Project-scoped trigger should have search tool
        harness = SkillExecutionHarness.from_trigger_run(trigger_run)
        tools = create_scoped_tools(harness)
        tool_names = [t.name for t in tools]

        assert "search_documents" in tool_names

    def test_search_tool_not_for_org_wide(self, organization, user):
        """Test that org-wide trigger doesn't get search tool."""
        # Create org-wide trigger (no project)
        trigger = EventTrigger.objects.create(
            organization=organization,
            name="Org-Wide Trigger",
            event_type=EventType.EMAIL_RECEIVED,
            skills=["test"],
            run_async=False,
            created_by=user,
        )

        run = EventTriggerRun.objects.create(
            organization=organization,
            trigger=trigger,
            source_type="email_message",
            source_id=1,
        )

        harness = SkillExecutionHarness.from_trigger_run(run)
        tools = create_scoped_tools(harness)
        tool_names = [t.name for t in tools]

        assert "search_documents" not in tool_names
