"""
Tests for the from-artifact API endpoint (Issue #108).

Tests the creation of documents from tool-generated artifacts,
including security validation for file paths.
"""

import tempfile
from pathlib import Path

import pytest
from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import Client
from organizations.models import OrganizationUser

from accounts.models import Account
from projects.models import Project

User = get_user_model()


@pytest.fixture
def organization():
    """Create a test organization."""
    return Account.objects.create(name="Test Organization")


@pytest.fixture
def user(organization):
    """Create a test user in the organization."""
    user = User.objects.create_user(
        username="testuser", email="test@example.com", password="testpass123"
    )
    OrganizationUser.objects.create(organization=organization, user=user)
    return user


@pytest.fixture
def project(organization, user):
    """Create a test project."""
    return Project.objects.create(
        organization=organization,
        name="Test Project",
        description="Test Project",
        created_by=user,
    )


@pytest.fixture
def authenticated_client(user):
    """Create an authenticated test client."""
    client = Client()
    client.force_login(user)
    return client


@pytest.fixture
def temp_image_in_media(settings):
    """Create a temporary image file in MEDIA_ROOT for testing."""
    media_root = Path(settings.MEDIA_ROOT)
    generated_images = media_root / "generated_images"
    generated_images.mkdir(parents=True, exist_ok=True)

    # Create a minimal PNG file (1x1 red pixel)
    png_data = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
        b"\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00"
        b"\x00\x0cIDATx\x9cc\xf8\xcf\xc0\x00\x00\x00\x03\x00\x01"
        b"\x00\x05\xfe\xd4\x00\x00\x00\x00IEND\xaeB`\x82"
    )

    test_file = generated_images / "test_artifact.png"
    test_file.write_bytes(png_data)

    yield str(test_file)

    # Cleanup
    if test_file.exists():
        test_file.unlink()


@pytest.mark.django_db
class TestFromArtifactEndpoint:
    """Tests for POST /api/documents/from-artifact endpoint."""

    def test_create_image_from_artifact_success(
        self, authenticated_client, project, temp_image_in_media
    ):
        """Successfully create an Image document from a tool artifact."""
        response = authenticated_client.post(
            "/api/documents/from-artifact",
            data={
                "artifact_type": "image",
                "file_path": temp_image_in_media,
                "project_id": project.id,
                "title": "Generated Test Image",
                "mime_type": "image/png",
            },
            content_type="application/json",
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["document_id"] is not None
        assert data["document_type"] == "Image"
        assert data["message"] == "Document created successfully"
        assert data["document"]["name"] == "Generated Test Image"

    def test_create_document_without_title_uses_filename(
        self, authenticated_client, project, temp_image_in_media
    ):
        """Without a title, should use the file name."""
        response = authenticated_client.post(
            "/api/documents/from-artifact",
            data={
                "artifact_type": "image",
                "file_path": temp_image_in_media,
                "project_id": project.id,
            },
            content_type="application/json",
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        # Name comes from file stem (test_artifact)
        assert "test_artifact" in data["document"]["name"]

    def test_unauthenticated_request_fails(self, project, temp_image_in_media):
        """Unauthenticated requests should be rejected."""
        client = Client()
        response = client.post(
            "/api/documents/from-artifact",
            data={
                "artifact_type": "image",
                "file_path": temp_image_in_media,
                "project_id": project.id,
            },
            content_type="application/json",
        )

        # Should be 401 or 403
        assert response.status_code in (401, 403)


@pytest.mark.django_db
class TestFromArtifactSecurityValidation:
    """Tests for security validation in the from-artifact endpoint."""

    def test_rejects_file_outside_media_root(
        self, authenticated_client, project
    ):
        """Should reject file paths outside MEDIA_ROOT."""
        response = authenticated_client.post(
            "/api/documents/from-artifact",
            data={
                "artifact_type": "image",
                "file_path": "/etc/passwd",
                "project_id": project.id,
            },
            content_type="application/json",
        )

        assert response.status_code == 403
        data = response.json()
        assert "must be within media directory" in data["detail"]

    def test_rejects_directory_traversal(
        self, authenticated_client, project, settings
    ):
        """Should reject directory traversal attempts."""
        media_root = Path(settings.MEDIA_ROOT)
        traversal_path = str(media_root / ".." / ".." / "etc" / "passwd")

        response = authenticated_client.post(
            "/api/documents/from-artifact",
            data={
                "artifact_type": "image",
                "file_path": traversal_path,
                "project_id": project.id,
            },
            content_type="application/json",
        )

        assert response.status_code == 403
        data = response.json()
        assert "must be within media directory" in data["detail"]

    def test_rejects_nonexistent_file(
        self, authenticated_client, project, settings
    ):
        """Should reject paths to files that don't exist."""
        media_root = Path(settings.MEDIA_ROOT)
        nonexistent = str(media_root / "generated_images" / "does_not_exist.png")

        response = authenticated_client.post(
            "/api/documents/from-artifact",
            data={
                "artifact_type": "image",
                "file_path": nonexistent,
                "project_id": project.id,
            },
            content_type="application/json",
        )

        assert response.status_code == 404
        data = response.json()
        assert "File not found" in data["detail"]

    def test_rejects_unsupported_artifact_type(
        self, authenticated_client, project, temp_image_in_media
    ):
        """Should return failure for unsupported artifact types."""
        response = authenticated_client.post(
            "/api/documents/from-artifact",
            data={
                "artifact_type": "unknown_type",
                "file_path": temp_image_in_media,
                "project_id": project.id,
            },
            content_type="application/json",
        )

        # Should return 200 with success=False, not 400
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert "unknown_type" in data["message"]

    def test_rejects_project_from_other_organization(
        self, authenticated_client, temp_image_in_media
    ):
        """Should reject project IDs from other organizations."""
        # Create another org and project
        other_org = Account.objects.create(name="Other Organization")
        other_user = User.objects.create_user(
            username="otheruser", email="other@example.com", password="pass123"
        )
        OrganizationUser.objects.create(organization=other_org, user=other_user)
        other_project = Project.objects.create(
            organization=other_org,
            name="Other Project",
            created_by=other_user,
        )

        response = authenticated_client.post(
            "/api/documents/from-artifact",
            data={
                "artifact_type": "image",
                "file_path": temp_image_in_media,
                "project_id": other_project.id,
            },
            content_type="application/json",
        )

        assert response.status_code == 404
        data = response.json()
        assert "Project not found" in data["detail"]
