"""
Security tests for document API endpoints.

Tests multi-tenant isolation and project-level access control.
Related to bug fix: ZoeaStudio-5kn (Switching projects can show document from another project)
"""

import pytest
from django.contrib.auth import get_user_model
from django.test import Client
from organizations.models import OrganizationUser

from accounts.models import Account
from documents.models import Markdown
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
def project_a(organization, user):
    """Create project A."""
    return Project.objects.create(
        organization=organization, name="Project A", description="Project A", created_by=user
    )


@pytest.fixture
def project_b(organization, user):
    """Create project B."""
    return Project.objects.create(
        organization=organization, name="Project B", description="Project B", created_by=user
    )


@pytest.fixture
def document_in_project_a(organization, project_a, user):
    """Create a document in project A."""
    return Markdown.objects.create(
        organization=organization,
        project=project_a,
        name="Document in Project A",
        content="This belongs to Project A",
        created_by=user,
    )


@pytest.fixture
def document_in_project_b(organization, project_b, user):
    """Create a document in project B."""
    return Markdown.objects.create(
        organization=organization,
        project=project_b,
        name="Document in Project B",
        content="This belongs to Project B",
        created_by=user,
    )


@pytest.fixture
def authenticated_client(user):
    """Create an authenticated test client."""
    client = Client()
    client.force_login(user)
    return client


@pytest.mark.django_db
class TestDocumentProjectIsolation:
    """
    Test that documents are properly isolated by project.

    Security bug ZoeaStudio-5kn: Users could see documents from other projects
    when switching projects if the frontend had a stale document ID cached.
    """

    def test_get_document_without_project_filter_succeeds(
        self, authenticated_client, document_in_project_a
    ):
        """
        Without project_id filter, users can access any document in their organization.
        This is the legacy behavior - not a bug, but not ideal for project isolation.
        """
        response = authenticated_client.get(f"/api/documents/{document_in_project_a.id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == document_in_project_a.id
        assert data["name"] == "Document in Project A"

    def test_get_document_with_correct_project_filter_succeeds(
        self, authenticated_client, document_in_project_a, project_a
    ):
        """
        When project_id matches the document's project, request succeeds.
        """
        response = authenticated_client.get(
            f"/api/documents/{document_in_project_a.id}?project_id={project_a.id}"
        )
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == document_in_project_a.id
        assert data["project_id"] == project_a.id

    def test_get_document_with_wrong_project_filter_fails(
        self, authenticated_client, document_in_project_a, project_b
    ):
        """
        When project_id doesn't match the document's project, request fails with 404.
        This is the security fix for ZoeaStudio-5kn.
        """
        response = authenticated_client.get(
            f"/api/documents/{document_in_project_a.id}?project_id={project_b.id}"
        )
        assert response.status_code == 404
        data = response.json()
        assert "does not belong to the specified project" in data["detail"]

    def test_cross_project_access_blocked_with_project_filter(
        self, authenticated_client, document_in_project_a, document_in_project_b, project_a, project_b
    ):
        """
        Verify that project_id filter prevents cross-project document access.

        Scenario:
        1. User has document from Project A cached in frontend
        2. User switches to Project B
        3. If frontend tries to load the Project A document with project_id=B, it should fail
        """
        # Try to access Project A document while claiming to be in Project B
        response = authenticated_client.get(
            f"/api/documents/{document_in_project_a.id}?project_id={project_b.id}"
        )
        assert response.status_code == 404

        # Verify the correct project filter works
        response = authenticated_client.get(
            f"/api/documents/{document_in_project_a.id}?project_id={project_a.id}"
        )
        assert response.status_code == 200

    def test_nonexistent_document_with_project_filter(
        self, authenticated_client, project_a
    ):
        """
        When document doesn't exist at all, should return 404 regardless of project filter.
        """
        response = authenticated_client.get(f"/api/documents/99999?project_id={project_a.id}")
        assert response.status_code == 404

    def test_project_filter_is_optional(
        self, authenticated_client, document_in_project_a
    ):
        """
        project_id parameter is optional and defaults to None (no project filtering).
        When omitted, any document in the user's organization can be accessed.
        """
        response = authenticated_client.get(f"/api/documents/{document_in_project_a.id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == document_in_project_a.id


@pytest.mark.django_db
class TestDocumentOrganizationIsolation:
    """
    Test that documents are always isolated by organization.
    This is existing security - users should never see documents from other organizations.
    """

    def test_cannot_access_document_from_other_organization(self):
        """
        Users cannot access documents from organizations they don't belong to.
        """
        # Create two separate organizations
        org1 = Account.objects.create(name="Organization 1")
        org2 = Account.objects.create(name="Organization 2")

        # Create user in org1
        user1 = User.objects.create_user(
            username="user1", email="user1@example.com", password="pass123"
        )
        OrganizationUser.objects.create(organization=org1, user=user1)

        # Create project in org1
        project1 = Project.objects.create(
            organization=org1, name="Project 1", created_by=user1
        )

        # Create document in org1
        doc1 = Markdown.objects.create(
            organization=org1,
            project=project1,
            name="Org 1 Document",
            created_by=user1,
        )

        # Create user in org2
        user2 = User.objects.create_user(
            username="user2", email="user2@example.com", password="pass123"
        )
        OrganizationUser.objects.create(organization=org2, user=user2)

        # User2 tries to access doc1 from org1
        client = Client()
        client.force_login(user2)
        response = client.get(f"/api/documents/{doc1.id}")

        # Should be 404 (not found) because organization filter blocks it
        assert response.status_code == 404
