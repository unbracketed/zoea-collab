"""
Tests for YooptaDocument model and text extraction.
"""

import json

import pytest
from django.contrib.auth import get_user_model

from documents.models import YooptaDocument
from organizations.models import Organization
from projects.models import Project


User = get_user_model()


@pytest.fixture
def organization(db):
    """Create a test organization."""
    return Organization.objects.create(name="Test Organization")


@pytest.fixture
def project(organization):
    """Create a test project."""
    return Project.objects.create(
        organization=organization,
        name="Test Project",
    )


@pytest.fixture
def sample_yoopta_content():
    """Sample Yoopta JSON content with multiple block types."""
    return {
        "block-1": {
            "id": "block-1",
            "meta": {"order": 0},
            "type": "HeadingOne",
            "value": [
                {
                    "id": "elem-1",
                    "type": "heading-one",
                    "children": [{"text": "Welcome to Yoopta"}],
                }
            ],
        },
        "block-2": {
            "id": "block-2",
            "meta": {"order": 1},
            "type": "Paragraph",
            "value": [
                {
                    "id": "elem-2",
                    "type": "paragraph",
                    "children": [
                        {"text": "This is a "},
                        {"text": "paragraph", "bold": True},
                        {"text": " with formatting."},
                    ],
                }
            ],
        },
        "block-3": {
            "id": "block-3",
            "meta": {"order": 2},
            "type": "BulletedList",
            "value": [
                {
                    "id": "elem-3",
                    "type": "bulleted-list",
                    "children": [{"text": "First item"}],
                },
                {
                    "id": "elem-4",
                    "type": "bulleted-list",
                    "children": [{"text": "Second item"}],
                },
            ],
        },
        "block-4": {
            "id": "block-4",
            "meta": {"order": 3},
            "type": "Code",
            "value": [
                {
                    "id": "elem-5",
                    "type": "code",
                    "children": [{"text": "def hello():\n    print('Hello')"}],
                }
            ],
        },
    }


class TestYooptaDocumentModel:
    """Tests for YooptaDocument model."""

    def test_create_yoopta_document(self, organization, project):
        """Test creating a YooptaDocument."""
        doc = YooptaDocument.objects.create(
            organization=organization,
            project=project,
            name="Test Document",
            content='{"block-1": {"id": "block-1", "meta": {"order": 0}, "value": []}}',
        )

        assert doc.id is not None
        assert doc.name == "Test Document"
        assert doc.yoopta_version == "4.0"
        assert doc.get_type_name() == "YooptaDocument"

    def test_get_text_content_empty(self, organization, project):
        """Test get_text_content with empty content."""
        doc = YooptaDocument.objects.create(
            organization=organization,
            project=project,
            name="Empty Document",
            content="",
        )

        assert doc.get_text_content() == ""

    def test_get_text_content_empty_object(self, organization, project):
        """Test get_text_content with empty JSON object."""
        doc = YooptaDocument.objects.create(
            organization=organization,
            project=project,
            name="Empty JSON Document",
            content="{}",
        )

        assert doc.get_text_content() == ""

    def test_get_text_content_simple(self, organization, project):
        """Test get_text_content with a simple paragraph."""
        content = {
            "block-1": {
                "id": "block-1",
                "meta": {"order": 0},
                "value": [
                    {
                        "id": "elem-1",
                        "type": "paragraph",
                        "children": [{"text": "Hello world"}],
                    }
                ],
            }
        }

        doc = YooptaDocument.objects.create(
            organization=organization,
            project=project,
            name="Simple Document",
            content=json.dumps(content),
        )

        assert doc.get_text_content() == "Hello world"

    def test_get_text_content_formatted_text(self, organization, project):
        """Test get_text_content preserves text from formatted spans."""
        content = {
            "block-1": {
                "id": "block-1",
                "meta": {"order": 0},
                "value": [
                    {
                        "id": "elem-1",
                        "type": "paragraph",
                        "children": [
                            {"text": "Hello "},
                            {"text": "bold", "bold": True},
                            {"text": " and "},
                            {"text": "italic", "italic": True},
                        ],
                    }
                ],
            }
        }

        doc = YooptaDocument.objects.create(
            organization=organization,
            project=project,
            name="Formatted Document",
            content=json.dumps(content),
        )

        assert doc.get_text_content() == "Hello bold and italic"

    def test_get_text_content_multiple_blocks(
        self, organization, project, sample_yoopta_content
    ):
        """Test get_text_content with multiple blocks ordered correctly."""
        doc = YooptaDocument.objects.create(
            organization=organization,
            project=project,
            name="Multi-block Document",
            content=json.dumps(sample_yoopta_content),
        )

        text = doc.get_text_content()

        # Check all text is present
        assert "Welcome to Yoopta" in text
        assert "This is a paragraph with formatting." in text
        assert "First item" in text
        assert "Second item" in text
        assert "def hello():" in text

        # Check order is preserved (heading should come before paragraph)
        assert text.index("Welcome to Yoopta") < text.index("This is a")

    def test_get_text_content_unordered_blocks(self, organization, project):
        """Test that blocks are sorted by meta.order regardless of dict order."""
        content = {
            "block-z": {
                "id": "block-z",
                "meta": {"order": 2},
                "value": [{"id": "e1", "children": [{"text": "Third"}]}],
            },
            "block-a": {
                "id": "block-a",
                "meta": {"order": 0},
                "value": [{"id": "e2", "children": [{"text": "First"}]}],
            },
            "block-m": {
                "id": "block-m",
                "meta": {"order": 1},
                "value": [{"id": "e3", "children": [{"text": "Second"}]}],
            },
        }

        doc = YooptaDocument.objects.create(
            organization=organization,
            project=project,
            name="Unordered Blocks Document",
            content=json.dumps(content),
        )

        text = doc.get_text_content()

        # Text should be in order by meta.order, not dict key order
        assert text.index("First") < text.index("Second") < text.index("Third")

    def test_get_text_content_invalid_json(self, organization, project):
        """Test get_text_content with invalid JSON returns raw content."""
        doc = YooptaDocument.objects.create(
            organization=organization,
            project=project,
            name="Invalid JSON Document",
            content="not valid json {",
        )

        # Should return the raw content as fallback
        assert doc.get_text_content() == "not valid json {"

    def test_get_text_content_list_items(self, organization, project):
        """Test get_text_content extracts text from list items."""
        content = {
            "block-1": {
                "id": "block-1",
                "meta": {"order": 0},
                "value": [
                    {"id": "e1", "type": "bulleted-list", "children": [{"text": "Item A"}]},
                    {"id": "e2", "type": "bulleted-list", "children": [{"text": "Item B"}]},
                    {"id": "e3", "type": "bulleted-list", "children": [{"text": "Item C"}]},
                ],
            }
        }

        doc = YooptaDocument.objects.create(
            organization=organization,
            project=project,
            name="List Document",
            content=json.dumps(content),
        )

        text = doc.get_text_content()
        assert "Item A" in text
        assert "Item B" in text
        assert "Item C" in text

    def test_get_text_content_code_block(self, organization, project):
        """Test get_text_content extracts code block content."""
        content = {
            "block-1": {
                "id": "block-1",
                "meta": {"order": 0},
                "value": [
                    {
                        "id": "e1",
                        "type": "code",
                        "children": [{"text": "const x = 42;\nconsole.log(x);"}],
                    }
                ],
            }
        }

        doc = YooptaDocument.objects.create(
            organization=organization,
            project=project,
            name="Code Document",
            content=json.dumps(content),
        )

        text = doc.get_text_content()
        assert "const x = 42;" in text
        assert "console.log(x);" in text

    def test_get_text_content_nested_elements(self, organization, project):
        """Test get_text_content handles nested element structures."""
        content = {
            "block-1": {
                "id": "block-1",
                "meta": {"order": 0},
                "value": [
                    {
                        "id": "e1",
                        "type": "paragraph",
                        "children": [
                            {
                                "type": "link",
                                "url": "https://example.com",
                                "children": [{"text": "Click here"}],
                            },
                            {"text": " to learn more."},
                        ],
                    }
                ],
            }
        }

        doc = YooptaDocument.objects.create(
            organization=organization,
            project=project,
            name="Nested Elements Document",
            content=json.dumps(content),
        )

        text = doc.get_text_content()
        assert "Click here" in text
        assert "to learn more." in text


class TestFileSearchIntegration:
    """Tests for YooptaDocument integration with file search."""

    def test_file_search_uses_text_content(self, organization, project):
        """Test that file search backend extracts text content correctly."""
        from file_search.base import FileSearchStore

        content = {
            "block-1": {
                "id": "block-1",
                "meta": {"order": 0},
                "value": [
                    {
                        "id": "e1",
                        "type": "paragraph",
                        "children": [{"text": "Searchable document content"}],
                    }
                ],
            }
        }

        doc = YooptaDocument.objects.create(
            organization=organization,
            project=project,
            name="Searchable Document",
            content=json.dumps(content),
        )

        # Create a mock store to test get_document_content
        class TestStore(FileSearchStore):
            @property
            def backend_name(self):
                return "test"

            def create_store(self, name, *, ephemeral=False):
                pass

            def get_store(self, store_id):
                pass

            def delete_store(self, store_id, *, force=True):
                pass

            def list_stores(self):
                pass

            def add_document(self, store_id, document, **options):
                pass

            def remove_document(self, store_id, backend_ref_id):
                pass

            def add_text_record(self, store_id, *, record_id, content, metadata, display_name=None, **options):
                pass

            def remove_text_record(self, store_id, record_id):
                pass

            def search(self, store_id, query, *, max_results=5, filters=None):
                pass

        store = TestStore()
        result = store.get_document_content(doc)

        assert result["type"] == "text"
        assert result["content"] == "Searchable document content"


class TestYooptaDocumentExport:
    """Tests for YooptaDocument export methods."""

    def test_get_markdown_content_empty(self, organization, project):
        """Test get_markdown_content with empty content."""
        doc = YooptaDocument.objects.create(
            organization=organization,
            project=project,
            name="Empty Document",
            content="",
        )

        assert doc.get_markdown_content() == ""

    def test_get_markdown_content_heading(self, organization, project):
        """Test get_markdown_content converts headings correctly."""
        content = {
            "block-1": {
                "id": "block-1",
                "meta": {"order": 0},
                "type": "HeadingOne",
                "value": [
                    {
                        "id": "e1",
                        "type": "heading-one",
                        "children": [{"text": "Main Title"}],
                    }
                ],
            },
            "block-2": {
                "id": "block-2",
                "meta": {"order": 1},
                "type": "HeadingTwo",
                "value": [
                    {
                        "id": "e2",
                        "type": "heading-two",
                        "children": [{"text": "Subtitle"}],
                    }
                ],
            },
        }

        doc = YooptaDocument.objects.create(
            organization=organization,
            project=project,
            name="Heading Document",
            content=json.dumps(content),
        )

        md = doc.get_markdown_content()
        assert "# Main Title" in md
        assert "## Subtitle" in md

    def test_get_markdown_content_formatted_text(self, organization, project):
        """Test get_markdown_content preserves inline formatting."""
        content = {
            "block-1": {
                "id": "block-1",
                "meta": {"order": 0},
                "value": [
                    {
                        "id": "e1",
                        "type": "paragraph",
                        "children": [
                            {"text": "Normal "},
                            {"text": "bold", "bold": True},
                            {"text": " and "},
                            {"text": "italic", "italic": True},
                            {"text": " and "},
                            {"text": "code", "code": True},
                        ],
                    }
                ],
            }
        }

        doc = YooptaDocument.objects.create(
            organization=organization,
            project=project,
            name="Formatted Document",
            content=json.dumps(content),
        )

        md = doc.get_markdown_content()
        assert "**bold**" in md
        assert "*italic*" in md
        assert "`code`" in md

    def test_get_markdown_content_lists(self, organization, project):
        """Test get_markdown_content converts lists correctly."""
        content = {
            "block-1": {
                "id": "block-1",
                "meta": {"order": 0},
                "type": "BulletedList",
                "value": [
                    {"id": "e1", "type": "bulleted-list", "children": [{"text": "First"}]},
                    {"id": "e2", "type": "bulleted-list", "children": [{"text": "Second"}]},
                ],
            },
            "block-2": {
                "id": "block-2",
                "meta": {"order": 1},
                "type": "NumberedList",
                "value": [
                    {"id": "e3", "type": "numbered-list", "children": [{"text": "One"}]},
                    {"id": "e4", "type": "numbered-list", "children": [{"text": "Two"}]},
                ],
            },
        }

        doc = YooptaDocument.objects.create(
            organization=organization,
            project=project,
            name="List Document",
            content=json.dumps(content),
        )

        md = doc.get_markdown_content()
        assert "- First" in md
        assert "- Second" in md
        assert "1. One" in md
        assert "2. Two" in md

    def test_get_markdown_content_code_block(self, organization, project):
        """Test get_markdown_content converts code blocks correctly."""
        content = {
            "block-1": {
                "id": "block-1",
                "meta": {"order": 0},
                "type": "Code",
                "value": [
                    {
                        "id": "e1",
                        "type": "code",
                        "props": {"language": "python"},
                        "children": [{"text": "print('hello')"}],
                    }
                ],
            }
        }

        doc = YooptaDocument.objects.create(
            organization=organization,
            project=project,
            name="Code Document",
            content=json.dumps(content),
        )

        md = doc.get_markdown_content()
        assert "```python" in md
        assert "print('hello')" in md
        assert "```" in md

    def test_get_markdown_content_blockquote(self, organization, project):
        """Test get_markdown_content converts blockquotes correctly."""
        content = {
            "block-1": {
                "id": "block-1",
                "meta": {"order": 0},
                "type": "Blockquote",
                "value": [
                    {
                        "id": "e1",
                        "type": "blockquote",
                        "children": [{"text": "A wise quote"}],
                    }
                ],
            }
        }

        doc = YooptaDocument.objects.create(
            organization=organization,
            project=project,
            name="Quote Document",
            content=json.dumps(content),
        )

        md = doc.get_markdown_content()
        assert "> A wise quote" in md

    def test_get_markdown_content_link(self, organization, project):
        """Test get_markdown_content converts links correctly."""
        content = {
            "block-1": {
                "id": "block-1",
                "meta": {"order": 0},
                "value": [
                    {
                        "id": "e1",
                        "type": "paragraph",
                        "children": [
                            {"text": "Check out "},
                            {
                                "type": "link",
                                "props": {"url": "https://example.com"},
                                "children": [{"text": "this site"}],
                            },
                        ],
                    }
                ],
            }
        }

        doc = YooptaDocument.objects.create(
            organization=organization,
            project=project,
            name="Link Document",
            content=json.dumps(content),
        )

        md = doc.get_markdown_content()
        assert "[this site](https://example.com)" in md

    def test_get_html_content_empty(self, organization, project):
        """Test get_html_content with empty content."""
        doc = YooptaDocument.objects.create(
            organization=organization,
            project=project,
            name="Empty Document",
            content="",
        )

        assert doc.get_html_content() == ""

    def test_get_html_content_heading(self, organization, project):
        """Test get_html_content converts headings correctly."""
        content = {
            "block-1": {
                "id": "block-1",
                "meta": {"order": 0},
                "type": "HeadingOne",
                "value": [
                    {
                        "id": "e1",
                        "type": "heading-one",
                        "children": [{"text": "Main Title"}],
                    }
                ],
            },
        }

        doc = YooptaDocument.objects.create(
            organization=organization,
            project=project,
            name="Heading Document",
            content=json.dumps(content),
        )

        html = doc.get_html_content()
        assert "<h1>Main Title</h1>" in html

    def test_get_html_content_formatted_text(self, organization, project):
        """Test get_html_content preserves inline formatting."""
        content = {
            "block-1": {
                "id": "block-1",
                "meta": {"order": 0},
                "value": [
                    {
                        "id": "e1",
                        "type": "paragraph",
                        "children": [
                            {"text": "bold", "bold": True},
                            {"text": " and "},
                            {"text": "italic", "italic": True},
                        ],
                    }
                ],
            }
        }

        doc = YooptaDocument.objects.create(
            organization=organization,
            project=project,
            name="Formatted Document",
            content=json.dumps(content),
        )

        html = doc.get_html_content()
        assert "<strong>bold</strong>" in html
        assert "<em>italic</em>" in html

    def test_get_html_content_lists(self, organization, project):
        """Test get_html_content converts lists correctly."""
        content = {
            "block-1": {
                "id": "block-1",
                "meta": {"order": 0},
                "type": "BulletedList",
                "value": [
                    {"id": "e1", "type": "bulleted-list", "children": [{"text": "Item"}]},
                ],
            },
        }

        doc = YooptaDocument.objects.create(
            organization=organization,
            project=project,
            name="List Document",
            content=json.dumps(content),
        )

        html = doc.get_html_content()
        assert "<ul>" in html
        assert "<li>Item</li>" in html
        assert "</ul>" in html

    def test_get_html_content_escapes_special_chars(self, organization, project):
        """Test get_html_content properly escapes HTML special characters."""
        content = {
            "block-1": {
                "id": "block-1",
                "meta": {"order": 0},
                "value": [
                    {
                        "id": "e1",
                        "type": "paragraph",
                        "children": [{"text": "<script>alert('xss')</script>"}],
                    }
                ],
            }
        }

        doc = YooptaDocument.objects.create(
            organization=organization,
            project=project,
            name="XSS Test Document",
            content=json.dumps(content),
        )

        html = doc.get_html_content()
        assert "<script>" not in html
        assert "&lt;script&gt;" in html

    def test_get_html_content_link(self, organization, project):
        """Test get_html_content converts links correctly."""
        content = {
            "block-1": {
                "id": "block-1",
                "meta": {"order": 0},
                "value": [
                    {
                        "id": "e1",
                        "type": "paragraph",
                        "children": [
                            {
                                "type": "link",
                                "props": {"url": "https://example.com"},
                                "children": [{"text": "Click me"}],
                            },
                        ],
                    }
                ],
            }
        }

        doc = YooptaDocument.objects.create(
            organization=organization,
            project=project,
            name="Link Document",
            content=json.dumps(content),
        )

        html = doc.get_html_content()
        assert '<a href="https://example.com">Click me</a>' in html


# API Test Fixtures


@pytest.fixture
def api_client():
    """Create a Django test client for API requests."""
    from django.test import Client

    return Client()


@pytest.fixture
def test_user(db):
    """Create a test user."""
    return User.objects.create_user(
        username="testuser",
        email="test@example.com",
        password="testpass123",
    )


@pytest.fixture
def test_organization(db, test_user):
    """Create a test organization with the test user as a member."""
    from organizations.models import OrganizationUser

    org = Organization.objects.create(
        name="Test Organization",
        slug="test-org",
    )
    OrganizationUser.objects.create(
        user=test_user,
        organization=org,
        is_admin=True,
    )
    return org


@pytest.fixture
def test_project(db, test_organization, test_user):
    """Create a test project in the test organization."""
    return Project.objects.create(
        organization=test_organization,
        name="Test Project",
        working_directory="/tmp/test-project",
        created_by=test_user,
    )


@pytest.fixture
def authenticated_client(api_client, test_user):
    """Create an authenticated Django test client."""
    api_client.force_login(test_user)
    return api_client


@pytest.fixture
def sample_yoopta_json():
    """Sample valid Yoopta JSON content for API tests."""
    return json.dumps(
        {
            "block-1": {
                "id": "block-1",
                "meta": {"order": 0},
                "type": "Paragraph",
                "value": [
                    {
                        "id": "elem-1",
                        "type": "paragraph",
                        "children": [{"text": "Hello from API test"}],
                    }
                ],
            }
        }
    )


class TestYooptaDocumentCreateAPI:
    """Tests for POST /api/documents/yoopta/create endpoint."""

    def test_create_yoopta_document_success(
        self,
        authenticated_client,
        test_organization,
        test_project,
        sample_yoopta_json,
    ):
        """Test successful creation of a Yoopta document."""
        response = authenticated_client.post(
            "/api/documents/yoopta/create",
            data=json.dumps(
                {
                    "name": "API Test Document",
                    "description": "Created via API",
                    "content": sample_yoopta_json,
                    "project_id": test_project.id,
                }
            ),
            content_type="application/json",
        )

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "API Test Document"
        assert data["description"] == "Created via API"
        assert data["document_type"] == "YooptaDocument"
        assert data["organization_id"] == test_organization.id
        assert data["project_id"] == test_project.id

    def test_create_yoopta_document_unauthenticated(
        self,
        api_client,
        test_project,
        sample_yoopta_json,
    ):
        """Test that unauthenticated requests are rejected."""
        response = api_client.post(
            "/api/documents/yoopta/create",
            data=json.dumps(
                {
                    "name": "Test Document",
                    "content": sample_yoopta_json,
                    "project_id": test_project.id,
                }
            ),
            content_type="application/json",
        )

        # django-ninja returns 401 or 403 for unauthenticated
        assert response.status_code in [401, 403]

    def test_create_yoopta_document_project_not_found(
        self,
        authenticated_client,
        test_organization,
        sample_yoopta_json,
    ):
        """Test error when project_id doesn't exist."""
        response = authenticated_client.post(
            "/api/documents/yoopta/create",
            data=json.dumps(
                {
                    "name": "Test Document",
                    "content": sample_yoopta_json,
                    "project_id": 99999,
                }
            ),
            content_type="application/json",
        )

        assert response.status_code == 404
        assert "Project not found" in response.json().get("detail", "")

    def test_create_yoopta_document_with_custom_version(
        self,
        authenticated_client,
        test_organization,
        test_project,
        sample_yoopta_json,
    ):
        """Test creation with custom yoopta_version."""
        response = authenticated_client.post(
            "/api/documents/yoopta/create",
            data=json.dumps(
                {
                    "name": "Versioned Document",
                    "content": sample_yoopta_json,
                    "project_id": test_project.id,
                    "yoopta_version": "5.0",
                }
            ),
            content_type="application/json",
        )

        assert response.status_code == 200
        data = response.json()
        assert data["yoopta_version"] == "5.0"


class TestYooptaDocumentUpdateAPI:
    """Tests for PATCH /api/documents/yoopta/{id} endpoint."""

    def test_update_yoopta_document_success(
        self,
        authenticated_client,
        test_organization,
        test_project,
        sample_yoopta_json,
    ):
        """Test successful update of a Yoopta document."""
        # First create a document
        doc = YooptaDocument.objects.create(
            organization=test_organization,
            project=test_project,
                        name="Original Name",
            content=sample_yoopta_json,
        )

        # Then update it
        new_content = json.dumps(
            {
                "block-1": {
                    "id": "block-1",
                    "meta": {"order": 0},
                    "value": [{"id": "e1", "children": [{"text": "Updated content"}]}],
                }
            }
        )

        response = authenticated_client.patch(
            f"/api/documents/yoopta/{doc.id}",
            data=json.dumps(
                {
                    "name": "Updated Name",
                    "content": new_content,
                }
            ),
            content_type="application/json",
        )

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated Name"

        # Verify in database
        doc.refresh_from_db()
        assert doc.name == "Updated Name"
        assert "Updated content" in doc.content

    def test_update_yoopta_document_partial(
        self,
        authenticated_client,
        test_organization,
        test_project,
        sample_yoopta_json,
    ):
        """Test partial update (only name, content unchanged)."""
        doc = YooptaDocument.objects.create(
            organization=test_organization,
            project=test_project,
                        name="Original Name",
            description="Original Description",
            content=sample_yoopta_json,
        )

        response = authenticated_client.patch(
            f"/api/documents/yoopta/{doc.id}",
            data=json.dumps({"description": "New Description"}),
            content_type="application/json",
        )

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Original Name"  # Unchanged
        assert data["description"] == "New Description"  # Updated

    def test_update_yoopta_document_not_found(
        self,
        authenticated_client,
        test_organization,
    ):
        """Test error when document doesn't exist."""
        response = authenticated_client.patch(
            "/api/documents/yoopta/99999",
            data=json.dumps({"name": "New Name"}),
            content_type="application/json",
        )

        assert response.status_code == 404
        assert "not found" in response.json().get("detail", "").lower()

    def test_update_yoopta_document_organization_scoping(
        self,
        authenticated_client,
        test_organization,  # Ensure user has an org
        sample_yoopta_json,
    ):
        """Test that users can't update documents from other organizations."""
        # Create another organization with its own document
        other_org = Organization.objects.create(name="Other Org", slug="other-org")
        other_project = Project.objects.create(
            organization=other_org,
            name="Other Project",
            working_directory="/tmp/other",
        )
        other_doc = YooptaDocument.objects.create(
            organization=other_org,
            project=other_project,
            name="Other Org Doc",
            content=sample_yoopta_json,
        )

        # Try to update it as authenticated user (different org)
        response = authenticated_client.patch(
            f"/api/documents/yoopta/{other_doc.id}",
            data=json.dumps({"name": "Hacked Name"}),
            content_type="application/json",
        )

        # Should not find the document (org scoping)
        assert response.status_code == 404


class TestYooptaDocumentExportAPI:
    """Tests for GET /api/documents/yoopta/{id}/export endpoint."""

    def test_export_to_markdown(
        self,
        authenticated_client,
        test_organization,
        test_project,
    ):
        """Test exporting a document to Markdown format."""
        content = {
            "block-1": {
                "id": "block-1",
                "meta": {"order": 0},
                "type": "HeadingOne",
                "value": [
                    {"id": "e1", "type": "heading-one", "children": [{"text": "Test Heading"}]}
                ],
            }
        }
        doc = YooptaDocument.objects.create(
            organization=test_organization,
            project=test_project,
                        name="Export Test",
            content=json.dumps(content),
        )

        response = authenticated_client.get(
            f"/api/documents/yoopta/{doc.id}/export?format=markdown"
        )

        assert response.status_code == 200
        data = response.json()
        assert data["format"] == "markdown"
        assert data["document_id"] == doc.id
        assert data["document_name"] == "Export Test"
        assert "# Test Heading" in data["content"]

    def test_export_to_html(
        self,
        authenticated_client,
        test_organization,
        test_project,
    ):
        """Test exporting a document to HTML format."""
        content = {
            "block-1": {
                "id": "block-1",
                "meta": {"order": 0},
                "type": "HeadingOne",
                "value": [
                    {"id": "e1", "type": "heading-one", "children": [{"text": "Test Heading"}]}
                ],
            }
        }
        doc = YooptaDocument.objects.create(
            organization=test_organization,
            project=test_project,
                        name="Export Test",
            content=json.dumps(content),
        )

        response = authenticated_client.get(f"/api/documents/yoopta/{doc.id}/export?format=html")

        assert response.status_code == 200
        data = response.json()
        assert data["format"] == "html"
        assert "<h1>Test Heading</h1>" in data["content"]

    def test_export_default_format(
        self,
        authenticated_client,
        test_organization,
        test_project,
    ):
        """Test export defaults to markdown when format not specified."""
        content = {
            "block-1": {
                "id": "block-1",
                "meta": {"order": 0},
                "value": [{"id": "e1", "children": [{"text": "Test"}]}],
            }
        }
        doc = YooptaDocument.objects.create(
            organization=test_organization,
            project=test_project,
                        name="Default Export",
            content=json.dumps(content),
        )

        response = authenticated_client.get(f"/api/documents/yoopta/{doc.id}/export")

        assert response.status_code == 200
        data = response.json()
        assert data["format"] == "markdown"

    def test_export_invalid_format(
        self,
        authenticated_client,
        test_organization,
        test_project,
    ):
        """Test error when invalid export format is specified."""
        doc = YooptaDocument.objects.create(
            organization=test_organization,
            project=test_project,
                        name="Test Doc",
            content="{}",
        )

        response = authenticated_client.get(f"/api/documents/yoopta/{doc.id}/export?format=pdf")

        assert response.status_code == 400
        assert "Invalid format" in response.json().get("detail", "")

    def test_export_document_not_found(
        self,
        authenticated_client,
        test_organization,
    ):
        """Test error when document doesn't exist."""
        response = authenticated_client.get("/api/documents/yoopta/99999/export")

        assert response.status_code == 404

    def test_export_organization_scoping(
        self,
        authenticated_client,
        test_organization,  # Ensure user has an org
    ):
        """Test that users can't export documents from other organizations."""
        # Create document in another organization
        other_org = Organization.objects.create(name="Other Org", slug="other-org-2")
        other_project = Project.objects.create(
            organization=other_org,
            name="Other Project",
            working_directory="/tmp/other2",
        )
        other_doc = YooptaDocument.objects.create(
            organization=other_org,
            project=other_project,
            name="Other Doc",
            content="{}",
        )

        response = authenticated_client.get(f"/api/documents/yoopta/{other_doc.id}/export")

        assert response.status_code == 404


class TestYooptaDocumentListAPI:
    """Tests for GET /api/documents with yooptadocument filter."""

    def test_list_documents_includes_yoopta(
        self,
        authenticated_client,
        test_organization,
        test_project,
        sample_yoopta_json,
    ):
        """Test that Yoopta documents appear in the document list."""
        doc = YooptaDocument.objects.create(
            organization=test_organization,
            project=test_project,
                        name="Yoopta in List",
            content=sample_yoopta_json,
        )

        response = authenticated_client.get("/api/documents")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 1

        # Find our document
        doc_data = next((d for d in data["documents"] if d["id"] == doc.id), None)
        assert doc_data is not None
        assert doc_data["document_type"] == "YooptaDocument"
        assert doc_data["name"] == "Yoopta in List"

    def test_list_documents_filter_by_yooptadocument(
        self,
        authenticated_client,
        test_organization,
        test_project,
        sample_yoopta_json,
    ):
        """Test filtering documents by yooptadocument type."""
        # Create a Yoopta document
        YooptaDocument.objects.create(
            organization=test_organization,
            project=test_project,
                        name="Yoopta Doc",
            content=sample_yoopta_json,
        )

        # Create a Markdown document for comparison
        from documents.models import Markdown

        Markdown.objects.create(
            organization=test_organization,
            project=test_project,
                        name="Markdown Doc",
            content="# Test",
        )

        response = authenticated_client.get("/api/documents?document_type=yooptadocument")

        assert response.status_code == 200
        data = response.json()

        # All returned documents should be YooptaDocument type
        for doc in data["documents"]:
            assert doc["document_type"] == "YooptaDocument"
