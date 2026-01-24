"""Tests for Markdown transformers.

This module tests the concrete transformers that convert Markdown objects
and MarkdownPayload value objects to various output formats.
"""

import pytest
from django.contrib.auth import get_user_model

from accounts.models import Account
from accounts.utils import get_user_organization
from documents.models import Folder, Markdown
from organizations.models import OrganizationUser
from projects.models import Project
from transformations import OutputFormat, transform
from transformations.value_objects import MarkdownPayload

User = get_user_model()


@pytest.fixture
def user_with_org(db):
    """Create a user with an organization."""
    user = User.objects.create_user(username="testuser", password="testpass")
    account = Account.objects.create(name="Test Org")
    OrganizationUser.objects.create(organization=account, user=user)
    return user


@pytest.fixture
def project(db, user_with_org):
    """Create a project for testing."""
    account = get_user_organization(user_with_org)
    return Project.objects.create(
        name="Test Project", description="Test", organization=account
    )


@pytest.fixture
def markdown_doc(db, project, user_with_org):
    """Create a Markdown document for testing."""
    account = project.organization
    root_folder = Folder.objects.create(
        name="Root",
        organization=account,
        project=project,
        created_by=user_with_org,
    )

    return Markdown.objects.create(
        name="Test Document",
        content="""# Introduction

This is the introduction section with some content.

## Background

More detailed background information here.

### Technical Details

Even more specific technical details.

## Methods

The methods section describes our approach.

# Results

The results section contains findings.
""",
        organization=account,
        project=project,
        folder=root_folder,
        created_by=user_with_org,
    )


@pytest.mark.django_db
class TestMarkdownToOutlineTransformer:
    """Tests for Markdown to Outline transformation."""

    def test_transform_markdown_to_outline(self, markdown_doc):
        """Test converting Markdown to hierarchical outline."""
        result = transform(markdown_doc, OutputFormat.OUTLINE)

        assert "sections" in result
        sections = result["sections"]

        # Should have 2 root sections (# Introduction and # Results)
        assert len(sections) == 2

        # Check first section
        intro = sections[0]
        assert intro["level"] == 1
        assert intro["title"] == "Introduction"
        assert "introduction section" in intro["content"].lower()
        assert intro["parent_id"] is None

        # Introduction should have 2 children (## Background and ## Methods)
        assert len(intro["children"]) == 2

        # Check nested structure
        background = intro["children"][0]
        assert background["level"] == 2
        assert background["title"] == "Background"
        assert background["parent_id"] == intro["id"]

        # Background should have 1 child (### Technical Details)
        assert len(background["children"]) == 1
        tech_details = background["children"][0]
        assert tech_details["level"] == 3
        assert tech_details["title"] == "Technical Details"

        # Methods section
        methods = intro["children"][1]
        assert methods["level"] == 2
        assert methods["title"] == "Methods"

        # Results section
        results = sections[1]
        assert results["level"] == 1
        assert results["title"] == "Results"
        assert len(results["children"]) == 0

    def test_transform_empty_markdown(self, project, user_with_org):
        """Test converting empty Markdown content."""
        account = project.organization
        root_folder = Folder.objects.create(
            name="Root",
            organization=account,
            project=project,
            created_by=user_with_org,
        )

        empty_doc = Markdown.objects.create(
            name="Empty",
            content="",
            organization=account,
            project=project,
            folder=root_folder,
            created_by=user_with_org,
        )

        result = transform(empty_doc, OutputFormat.OUTLINE)
        assert result == {"sections": []}

    def test_transform_markdown_payload(self):
        """Test converting MarkdownPayload value object."""
        payload = MarkdownPayload(
            content="""# Section One

Content for section one.

## Subsection

Nested content.

# Section Two

Content for section two.
"""
        )

        result = transform(payload, OutputFormat.OUTLINE)

        assert "sections" in result
        sections = result["sections"]
        assert len(sections) == 2
        assert sections[0]["title"] == "Section One"
        assert sections[1]["title"] == "Section Two"
        assert len(sections[0]["children"]) == 1


@pytest.mark.django_db
class TestMarkdownToJSONTransformer:
    """Tests for Markdown to JSON transformation."""

    def test_transform_markdown_to_json(self, markdown_doc):
        """Test converting Markdown model to JSON dict."""
        result = transform(markdown_doc, OutputFormat.JSON)

        assert "content" in result
        assert "title" in result
        assert "id" in result
        assert "created_at" in result
        assert "updated_at" in result

        assert result["title"] == "Test Document"
        assert "# Introduction" in result["content"]
        assert result["id"] == markdown_doc.id

    def test_transform_markdown_payload_to_json(self):
        """Test converting MarkdownPayload to JSON dict."""
        payload = MarkdownPayload(
            content="# Test", title="My Doc", metadata={"author": "Alice"}
        )

        result = transform(payload, OutputFormat.JSON)

        assert result["content"] == "# Test"
        assert result["title"] == "My Doc"
        assert result["metadata"] == {"author": "Alice"}

        # Should not have model-specific fields
        assert "id" not in result
        assert "created_at" not in result


@pytest.mark.django_db
class TestMarkdownToMarkdownTransformer:
    """Tests for Markdown to Markdown pass-through transformation."""

    def test_transform_markdown_to_markdown(self, markdown_doc):
        """Test pass-through transformation returns content as-is."""
        result = transform(markdown_doc, OutputFormat.MARKDOWN)

        assert isinstance(result, str)
        assert result == markdown_doc.content
        assert "# Introduction" in result

    def test_transform_payload_to_markdown(self):
        """Test pass-through with MarkdownPayload."""
        payload = MarkdownPayload(content="# Test Content\n\nBody text.")

        result = transform(payload, OutputFormat.MARKDOWN)

        assert result == "# Test Content\n\nBody text."
