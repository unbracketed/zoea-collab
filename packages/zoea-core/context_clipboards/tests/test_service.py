"""Initial smoke tests for the clipboard app."""

import json

import pytest
from django.contrib.auth import get_user_model
from django.test import Client
from organizations.models import Organization, OrganizationUser

from accounts.models import Account
from accounts.utils import initialize_user_organization
from documents.models import Document, YooptaDocument
from projects.models import Project
from workspaces.models import Workspace

from context_clipboards.models import Clipboard, ClipboardDirection
from context_clipboards.services import ClipboardService


@pytest.mark.django_db
def test_clipboard_service_creates_active_clipboard():
    User = get_user_model()
    user = User.objects.create_user("clip@example.com", "clip@example.com", "password123")
    organization = Organization.objects.create(name="Sample Org", slug="sample-org")
    project = Project.objects.create(
        organization=organization,
        name="Sample Project",
        working_directory="/tmp/sample",
        created_by=user,
    )
    workspace = Workspace.objects.create(project=project, name="Workspace A", created_by=user)

    service = ClipboardService(actor=user)
    clipboard = service.get_or_create_active(workspace)

    assert clipboard.is_active
    assert clipboard.owner == user

    result = service.add_item(
        clipboard=clipboard,
        direction=ClipboardDirection.RIGHT,
        source_metadata={"sample": True},
    )

    assert result.item.clipboard == clipboard
    assert clipboard.items.count() == 1


@pytest.mark.django_db
def test_clipboard_api_list_and_item_flow():
    User = get_user_model()
    user = User.objects.create_user("api@example.com", "api@example.com", "password123")
    organization = Organization.objects.create(name="API Org", slug="api-org")
    OrganizationUser.objects.create(organization=organization, user=user, is_admin=True)
    project = Project.objects.create(
        organization=organization,
        name="API Project",
        working_directory="/tmp/api",
        created_by=user,
    )
    workspace = Workspace.objects.create(project=project, name="Workspace API", created_by=user)

    service = ClipboardService(actor=user)
    service.get_or_create_active(workspace)

    client = Client()
    client.force_login(user)

    response = client.get("/api/clipboards/", {"workspace_id": workspace.id})
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 1

    create_payload = {
        "workspace_id": workspace.id,
        "name": "API Clipboard",
    }
    response = client.post(
        "/api/clipboards/",
        data=json.dumps(create_payload),
        content_type="application/json",
    )
    assert response.status_code == 201
    created_clipboard = response.json()["clipboard"]
    clipboard_id = created_clipboard["id"]
    assert created_clipboard["name"] == "API Clipboard"

    item_payload = {
        "direction": "right",
        "source_metadata": {"foo": "bar"},
    }
    response = client.post(
        f"/api/clipboards/{clipboard_id}/items",
        data=json.dumps(item_payload),
        content_type="application/json",
    )
    assert response.status_code == 200
    item_response = response.json()
    assert item_response["item"]["clipboard_id"] == clipboard_id

    response = client.get(f"/api/clipboards/{clipboard_id}", {"include_items": "true"})
    assert response.status_code == 200
    detail = response.json()
    assert isinstance(detail["items"], list)
    assert len(detail["items"]) == 1

    response = client.get(f"/api/clipboards/{clipboard_id}/items")
    assert response.status_code == 200
    items = response.json()
    assert items["total"] == 1


@pytest.mark.django_db
def test_clipboard_api_add_document_reference():
    User = get_user_model()
    user = User.objects.create_user("doc@example.com", "doc@example.com", "password123")
    organization = Organization.objects.create(name="Doc Org", slug="doc-org")
    OrganizationUser.objects.create(organization=organization, user=user, is_admin=True)

    project = Project.objects.create(
        organization=organization,
        name="Doc Project",
        working_directory="/tmp/doc",
        created_by=user,
    )
    workspace = Workspace.objects.create(project=project, name="Workspace D", created_by=user)

    document = Document.objects.create(
        organization=organization,
        project=project,
        workspace=workspace,
        name="Spec",
        description="Test document",
        created_by=user,
    )

    service = ClipboardService(actor=user)
    clipboard = service.get_or_create_active(workspace)

    client = Client()
    client.force_login(user)

    response = client.post(
        f"/api/clipboards/{clipboard.id}/items",
        data=json.dumps(
            {
                "direction": "right",
                "content_type": "documents.document",
                "object_id": document.id,
                "source_channel": "document",
            }
        ),
        content_type="application/json",
    )

    assert response.status_code == 200
    data = response.json()
    assert data["item"]["content_type"] == "documents.document"
    assert data["item"]["object_id"] == str(document.id)


@pytest.mark.django_db
def test_clipboard_export_to_markdown():
    """Test exporting clipboard to markdown format."""
    User = get_user_model()
    user = User.objects.create_user("export@example.com", "export@example.com", "password123")
    organization = Organization.objects.create(name="Export Org", slug="export-org")
    OrganizationUser.objects.create(organization=organization, user=user, is_admin=True)

    project = Project.objects.create(
        organization=organization,
        name="Export Project",
        working_directory="/tmp/export",
        created_by=user,
    )
    workspace = Workspace.objects.create(project=project, name="Export Workspace", created_by=user)

    service = ClipboardService(actor=user)
    clipboard = service.get_or_create_active(workspace)

    # Add items with source metadata
    service.add_item(
        clipboard=clipboard,
        direction=ClipboardDirection.RIGHT,
        source_metadata={
            "preview": "First item preview",
            "full_text": "This is the full text of the first item",
        },
    )
    service.add_item(
        clipboard=clipboard,
        direction=ClipboardDirection.RIGHT,
        source_metadata={
            "preview": "Second item preview",
            "full_text": "This is the full text of the second item",
        },
    )

    client = Client()
    client.force_login(user)

    response = client.get(f"/api/clipboards/{clipboard.id}/export?format=markdown")
    assert response.status_code == 200
    data = response.json()

    assert data["format"] == "markdown"
    assert data["item_count"] == 2
    assert data["content"]
    assert "first item" in data["content"].lower()
    assert "second item" in data["content"].lower()


@pytest.mark.django_db
def test_clipboard_export_unauthorized():
    """Test that export endpoint requires proper authorization."""
    User = get_user_model()
    user1 = User.objects.create_user("user1@example.com", "user1@example.com", "password123")
    user2 = User.objects.create_user("user2@example.com", "user2@example.com", "password123")

    org1 = Organization.objects.create(name="Org1", slug="org1")
    OrganizationUser.objects.create(organization=org1, user=user1, is_admin=True)

    org2 = Organization.objects.create(name="Org2", slug="org2")
    OrganizationUser.objects.create(organization=org2, user=user2, is_admin=True)

    project = Project.objects.create(
        organization=org1,
        name="Project1",
        working_directory="/tmp/proj1",
        created_by=user1,
    )
    workspace = Workspace.objects.create(project=project, name="Workspace1", created_by=user1)

    service = ClipboardService(actor=user1)
    clipboard = service.get_or_create_active(workspace)

    # Try to export as user2 (different org)
    client = Client()
    client.force_login(user2)

    response = client.get(f"/api/clipboards/{clipboard.id}/export?format=markdown")
    assert response.status_code == 404  # Should not find clipboard


@pytest.mark.django_db
def test_clipboard_export_empty():
    """Test exporting an empty clipboard."""
    User = get_user_model()
    user = User.objects.create_user("empty@example.com", "empty@example.com", "password123")
    organization = Organization.objects.create(name="Empty Org", slug="empty-org")
    OrganizationUser.objects.create(organization=organization, user=user, is_admin=True)

    project = Project.objects.create(
        organization=organization,
        name="Empty Project",
        working_directory="/tmp/empty",
        created_by=user,
    )
    workspace = Workspace.objects.create(project=project, name="Empty Workspace", created_by=user)

    service = ClipboardService(actor=user)
    clipboard = service.get_or_create_active(workspace)

    client = Client()
    client.force_login(user)

    response = client.get(f"/api/clipboards/{clipboard.id}/export?format=markdown")
    assert response.status_code == 200
    data = response.json()

    assert data["format"] == "markdown"
    assert data["item_count"] == 0
    assert data["content"]  # Should still have header/metadata


@pytest.mark.django_db
def test_clipboard_export_unsupported_format():
    """Test that unsupported export formats are rejected."""
    User = get_user_model()
    user = User.objects.create_user("format@example.com", "format@example.com", "password123")
    organization = Organization.objects.create(name="Format Org", slug="format-org")
    OrganizationUser.objects.create(organization=organization, user=user, is_admin=True)

    project = Project.objects.create(
        organization=organization,
        name="Format Project",
        working_directory="/tmp/format",
        created_by=user,
    )
    workspace = Workspace.objects.create(project=project, name="Format Workspace", created_by=user)

    service = ClipboardService(actor=user)
    clipboard = service.get_or_create_active(workspace)

    client = Client()
    client.force_login(user)

    response = client.get(f"/api/clipboards/{clipboard.id}/export?format=json")
    assert response.status_code == 400
    data = response.json()
    assert "Unsupported export format" in data["detail"]


@pytest.mark.django_db
def test_clipboard_save_as_document_creates_yoopta_document():
    """Saving a notepad explicitly creates a shareable YooptaDocument."""

    User = get_user_model()
    user = User.objects.create_user("save@example.com", "save@example.com", "password123")
    organization = Organization.objects.create(name="Save Org", slug="save-org")
    OrganizationUser.objects.create(organization=organization, user=user, is_admin=True)

    project = Project.objects.create(
        organization=organization,
        name="Save Project",
        working_directory="/tmp/save",
        created_by=user,
    )
    workspace = Workspace.objects.create(project=project, name="Save Workspace", created_by=user)

    document = Document.objects.create(
        organization=organization,
        project=project,
        workspace=workspace,
        name="Spec Doc",
        description="Test document",
        created_by=user,
    )

    service = ClipboardService(actor=user)
    clipboard = service.get_or_create_active(workspace)

    # Add a document reference, a message, and a diagram.
    service.add_item(
        clipboard=clipboard,
        direction=ClipboardDirection.RIGHT,
        content_object=document,
        source_channel="document",
    )
    service.add_item(
        clipboard=clipboard,
        direction=ClipboardDirection.RIGHT,
        source_channel="message",
        source_metadata={"full_text": "Remember to follow up on the spec."},
    )
    service.add_item(
        clipboard=clipboard,
        direction=ClipboardDirection.RIGHT,
        source_channel="canvas",
        source_metadata={
            "diagram_name": "Example Diagram",
            "diagram_code": "def hello():\n    print('hi')",
        },
    )

    client = Client()
    client.force_login(user)

    response = client.post(
        f"/api/clipboards/{clipboard.id}/save_as_document",
        data=json.dumps({"name": "Shared Notepad Doc"}),
        content_type="application/json",
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["document_name"] == "Shared Notepad Doc"

    saved = YooptaDocument.objects.get(id=payload["document_id"])
    assert saved.organization_id == organization.id
    assert saved.project_id == project.id
    assert saved.workspace_id == workspace.id
    assert saved.created_by_id == user.id
    assert saved.file_size and saved.file_size > 0

    text = saved.get_text_content()
    assert "Shared Notepad Doc" not in text  # title is clipboard name, not doc name
    assert "Spec Doc" in text
    assert "Remember to follow up on the spec." in text
    assert "def hello():" in text


@pytest.mark.django_db
def test_clipboard_save_as_document_unauthorized():
    """Saving another user's clipboard should not be allowed (404)."""

    User = get_user_model()
    owner = User.objects.create_user("owner@example.com", "owner@example.com", "password123")
    attacker = User.objects.create_user(
        "attacker@example.com", "attacker@example.com", "password123"
    )

    org1 = Organization.objects.create(name="Owner Org", slug="owner-org")
    OrganizationUser.objects.create(organization=org1, user=owner, is_admin=True)

    org2 = Organization.objects.create(name="Attacker Org", slug="attacker-org")
    OrganizationUser.objects.create(organization=org2, user=attacker, is_admin=True)

    project = Project.objects.create(
        organization=org1,
        name="Owner Project",
        working_directory="/tmp/owner",
        created_by=owner,
    )
    workspace = Workspace.objects.create(project=project, name="Owner Workspace", created_by=owner)
    clipboard = ClipboardService(actor=owner).get_or_create_active(workspace)

    client = Client()
    client.force_login(attacker)

    response = client.post(
        f"/api/clipboards/{clipboard.id}/save_as_document",
        data=json.dumps({"name": "Should Fail"}),
        content_type="application/json",
    )
    assert response.status_code == 404


@pytest.mark.django_db
def test_clipboard_save_as_document_uses_notepad_draft_content():
    """If notepad draft content exists on the clipboard, export uses it."""

    User = get_user_model()
    user = User.objects.create_user("draft@example.com", "draft@example.com", "password123")
    organization = Organization.objects.create(name="Draft Org", slug="draft-org")
    OrganizationUser.objects.create(organization=organization, user=user, is_admin=True)

    project = Project.objects.create(
        organization=organization,
        name="Draft Project",
        working_directory="/tmp/draft",
        created_by=user,
    )
    workspace = Workspace.objects.create(project=project, name="Draft Workspace", created_by=user)
    clipboard = ClipboardService(actor=user).get_or_create_active(workspace)

    clipboard.metadata = {
        "notepad": {
            "content": {
                "block-1": {
                    "id": "block-1",
                    "meta": {"order": 0},
                    "type": "Paragraph",
                    "value": [
                        {
                            "id": "elem-1",
                            "type": "paragraph",
                            "children": [{"text": "Draft note content"}],
                        }
                    ],
                }
            }
        }
    }
    clipboard.save(update_fields=["metadata"])

    client = Client()
    client.force_login(user)

    response = client.post(
        f"/api/clipboards/{clipboard.id}/save_as_document",
        data=json.dumps({"name": "Draft Export"}),
        content_type="application/json",
    )
    assert response.status_code == 201

    saved = YooptaDocument.objects.get(id=response.json()["document_id"])
    assert saved.get_text_content() == "Draft note content"


@pytest.mark.django_db
def test_clipboard_save_as_document_sanitizes_clipboard_item_blocks():
    """Embedded ClipboardItem blocks are replaced with shareable content on export."""

    User = get_user_model()
    user = User.objects.create_user("sanitize@example.com", "sanitize@example.com", "password123")
    organization = Organization.objects.create(name="Sanitize Org", slug="sanitize-org")
    OrganizationUser.objects.create(organization=organization, user=user, is_admin=True)

    project = Project.objects.create(
        organization=organization,
        name="Sanitize Project",
        working_directory="/tmp/sanitize",
        created_by=user,
    )
    workspace = Workspace.objects.create(project=project, name="Sanitize Workspace", created_by=user)

    document = Document.objects.create(
        organization=organization,
        project=project,
        workspace=workspace,
        name="Sanitize Doc",
        description="Test document",
        created_by=user,
    )

    service = ClipboardService(actor=user)
    clipboard = service.get_or_create_active(workspace)

    op = service.add_item(
        clipboard=clipboard,
        direction=ClipboardDirection.RIGHT,
        content_object=document,
        source_channel="document",
    )

    clipboard.metadata = {
        "notepad": {
            "content": {
                "block-1": {
                    "id": "block-1",
                    "meta": {"order": 0},
                    "type": "Paragraph",
                    "value": [
                        {
                            "id": "elem-1",
                            "type": "paragraph",
                            "children": [{"text": "Keep this note"}],
                        }
                    ],
                },
                "block-2": {
                    "id": "block-2",
                    "meta": {"order": 1},
                    "type": "ClipboardItem",
                    "value": [
                        {
                            "id": "elem-2",
                            "type": "clipboard_item",
                            "props": {
                                "nodeType": "void",
                                "clipboard_item_id": op.item.id,
                            },
                            "children": [{"text": ""}],
                        }
                    ],
                },
            }
        }
    }
    clipboard.save(update_fields=["metadata"])

    client = Client()
    client.force_login(user)

    response = client.post(
        f"/api/clipboards/{clipboard.id}/save_as_document",
        data=json.dumps({"name": "Sanitized Export"}),
        content_type="application/json",
    )
    assert response.status_code == 201

    saved = YooptaDocument.objects.get(id=response.json()["document_id"])
    text = saved.get_text_content()
    assert "Keep this note" in text
    assert "Sanitize Doc" in text


@pytest.mark.django_db
def test_clipboard_notepad_draft_round_trip():
    """Notepad draft Yoopta JSON can be stored and retrieved."""

    User = get_user_model()
    user = User.objects.create_user("draftapi@example.com", "draftapi@example.com", "password123")
    organization = Organization.objects.create(name="Draft API Org", slug="draft-api-org")
    OrganizationUser.objects.create(organization=organization, user=user, is_admin=True)

    project = Project.objects.create(
        organization=organization,
        name="Draft API Project",
        working_directory="/tmp/draft-api",
        created_by=user,
    )
    workspace = Workspace.objects.create(project=project, name="Draft API Workspace", created_by=user)
    clipboard = ClipboardService(actor=user).get_or_create_active(workspace)

    content = {
        "block-1": {
            "id": "block-1",
            "meta": {"order": 0},
            "type": "Paragraph",
            "value": [
                {
                    "id": "elem-1",
                    "type": "paragraph",
                    "children": [{"text": "Hello notepad draft"}],
                }
            ],
        }
    }

    client = Client()
    client.force_login(user)

    response = client.put(
        f"/api/clipboards/{clipboard.id}/notepad_draft",
        data=json.dumps({"content": content}),
        content_type="application/json",
    )
    assert response.status_code == 200
    assert response.json()["content"] == content

    response = client.get(f"/api/clipboards/{clipboard.id}/notepad_draft")
    assert response.status_code == 200
    assert response.json()["content"] == content


@pytest.mark.django_db
def test_clipboard_notepad_draft_can_be_cleared():
    User = get_user_model()
    user = User.objects.create_user("clear@example.com", "clear@example.com", "password123")
    organization = Organization.objects.create(name="Clear Org", slug="clear-org")
    OrganizationUser.objects.create(organization=organization, user=user, is_admin=True)

    project = Project.objects.create(
        organization=organization,
        name="Clear Project",
        working_directory="/tmp/clear",
        created_by=user,
    )
    workspace = Workspace.objects.create(project=project, name="Clear Workspace", created_by=user)
    clipboard = ClipboardService(actor=user).get_or_create_active(workspace)

    client = Client()
    client.force_login(user)

    response = client.put(
        f"/api/clipboards/{clipboard.id}/notepad_draft",
        data=json.dumps({"content": {"block-1": {"id": "block-1", "meta": {"order": 0}, "type": "Paragraph", "value": []}}}),
        content_type="application/json",
    )
    assert response.status_code == 200

    response = client.delete(f"/api/clipboards/{clipboard.id}/notepad_draft")
    assert response.status_code == 200
    assert response.json()["success"] is True

    response = client.get(f"/api/clipboards/{clipboard.id}/notepad_draft")
    assert response.status_code == 200
    assert response.json()["content"] is None


@pytest.mark.django_db
def test_clipboard_notepad_draft_unauthorized():
    User = get_user_model()
    owner = User.objects.create_user("owner2@example.com", "owner2@example.com", "password123")
    attacker = User.objects.create_user(
        "attacker2@example.com", "attacker2@example.com", "password123"
    )

    org1 = Organization.objects.create(name="Org One", slug="org-one")
    OrganizationUser.objects.create(organization=org1, user=owner, is_admin=True)

    org2 = Organization.objects.create(name="Org Two", slug="org-two")
    OrganizationUser.objects.create(organization=org2, user=attacker, is_admin=True)

    project = Project.objects.create(
        organization=org1,
        name="Owner Project",
        working_directory="/tmp/owner2",
        created_by=owner,
    )
    workspace = Workspace.objects.create(project=project, name="Owner Workspace", created_by=owner)
    clipboard = ClipboardService(actor=owner).get_or_create_active(workspace)

    client = Client()
    client.force_login(attacker)

    response = client.get(f"/api/clipboards/{clipboard.id}/notepad_draft")
    assert response.status_code == 404

    response = client.put(
        f"/api/clipboards/{clipboard.id}/notepad_draft",
        data=json.dumps({"content": {"block-1": {"id": "block-1"}}}),
        content_type="application/json",
    )
    assert response.status_code == 404


@pytest.mark.django_db
def test_clipboard_notepad_draft_rejects_non_object_content():
    User = get_user_model()
    user = User.objects.create_user("bad@example.com", "bad@example.com", "password123")
    organization = Organization.objects.create(name="Bad Org", slug="bad-org")
    OrganizationUser.objects.create(organization=organization, user=user, is_admin=True)

    project = Project.objects.create(
        organization=organization,
        name="Bad Project",
        working_directory="/tmp/bad",
        created_by=user,
    )
    workspace = Workspace.objects.create(project=project, name="Bad Workspace", created_by=user)
    clipboard = ClipboardService(actor=user).get_or_create_active(workspace)

    client = Client()
    client.force_login(user)

    response = client.put(
        f"/api/clipboards/{clipboard.id}/notepad_draft",
        data=json.dumps({"content": ["not", "a", "dict"]}),
        content_type="application/json",
    )
    assert response.status_code == 422


@pytest.mark.django_db
def test_default_clipboard_created_when_workspace_created():
    """Test that a default clipboard is automatically created when a workspace is created."""
    User = get_user_model()
    user = User.objects.create_user("workspace@example.com", "workspace@example.com", "password123")
    organization = Organization.objects.create(name="Workspace Org", slug="workspace-org")
    OrganizationUser.objects.create(organization=organization, user=user, is_admin=True)

    project = Project.objects.create(
        organization=organization,
        name="Workspace Project",
        working_directory="/tmp/workspace",
        created_by=user,
    )

    # Create a workspace - signal should auto-create clipboard
    workspace = Workspace.objects.create(
        project=project,
        name="Test Workspace",
        created_by=user,
    )

    # Verify clipboard was created
    clipboard = Clipboard.objects.filter(workspace=workspace, owner=user).first()
    assert clipboard is not None
    assert clipboard.is_active is True
    assert clipboard.name == f"{workspace.name} Clipboard"
    assert clipboard.activated_at is not None


@pytest.mark.django_db
def test_default_clipboard_created_when_project_created():
    """Test that a default clipboard is created through the signal cascade when a project is created."""
    User = get_user_model()
    user = User.objects.create_user("project@example.com", "project@example.com", "password123")
    organization = Organization.objects.create(name="Project Org", slug="project-org")
    OrganizationUser.objects.create(organization=organization, user=user, is_admin=True)

    # Create a project - signal should create workspace, which should create clipboard
    project = Project.objects.create(
        organization=organization,
        name="Test Project",
        working_directory="/tmp/project",
        created_by=user,
    )

    # Verify workspace was created
    workspace = Workspace.objects.filter(project=project, parent=None).first()
    assert workspace is not None

    # Verify clipboard was created for that workspace
    clipboard = Clipboard.objects.filter(workspace=workspace, owner=user).first()
    assert clipboard is not None
    assert clipboard.is_active is True
    assert clipboard.owner == user


@pytest.mark.django_db
def test_no_clipboard_created_when_workspace_has_no_creator():
    """Test that no clipboard is created if workspace.created_by is None."""
    User = get_user_model()
    user = User.objects.create_user("none@example.com", "none@example.com", "password123")
    organization = Organization.objects.create(name="None Org", slug="none-org")
    OrganizationUser.objects.create(organization=organization, user=user, is_admin=True)

    project = Project.objects.create(
        organization=organization,
        name="None Project",
        working_directory="/tmp/none",
        created_by=user,
    )

    # Create workspace without a creator
    workspace = Workspace.objects.create(
        project=project,
        name="No Creator Workspace",
        created_by=None,
    )

    # Verify no clipboard was created
    clipboard_count = Clipboard.objects.filter(workspace=workspace).count()
    assert clipboard_count == 0


@pytest.mark.django_db
def test_initialize_user_organization_creates_clipboard():
    """Test that initialize_user_organization creates a complete setup including clipboard."""
    User = get_user_model()
    user = User.objects.create_user(
        username="alice",
        email="alice@example.com",
        password="password123",
    )

    result = initialize_user_organization(user)

    # Verify all components were created
    assert result['organization'] is not None
    assert result['project'] is not None
    assert result['workspace'] is not None
    assert result['clipboard'] is not None

    # Verify clipboard properties
    clipboard = result['clipboard']
    assert clipboard.workspace == result['workspace']
    assert clipboard.owner == user
    assert clipboard.is_active is True
    assert clipboard.activated_at is not None

    # Verify clipboard name
    assert result['workspace'].name in clipboard.name


@pytest.mark.django_db
def test_multiple_workspaces_each_get_default_clipboard():
    """Test that each workspace gets its own default clipboard."""
    User = get_user_model()
    user = User.objects.create_user("multi@example.com", "multi@example.com", "password123")
    organization = Organization.objects.create(name="Multi Org", slug="multi-org")
    OrganizationUser.objects.create(organization=organization, user=user, is_admin=True)

    project = Project.objects.create(
        organization=organization,
        name="Multi Project",
        working_directory="/tmp/multi",
        created_by=user,
    )

    # Create multiple workspaces
    workspace1 = Workspace.objects.create(
        project=project,
        name="Workspace 1",
        created_by=user,
    )
    workspace2 = Workspace.objects.create(
        project=project,
        name="Workspace 2",
        created_by=user,
    )

    # Verify each workspace has its own clipboard
    clipboard1 = Clipboard.objects.filter(workspace=workspace1, owner=user).first()
    clipboard2 = Clipboard.objects.filter(workspace=workspace2, owner=user).first()

    assert clipboard1 is not None
    assert clipboard2 is not None
    assert clipboard1.id != clipboard2.id
    assert clipboard1.name == "Workspace 1 Clipboard"
    assert clipboard2.name == "Workspace 2 Clipboard"
