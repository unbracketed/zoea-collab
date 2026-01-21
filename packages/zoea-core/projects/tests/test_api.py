"""Tests for project APIs and organization scoping."""

import pytest
from asgiref.sync import sync_to_async
from django.contrib.auth import get_user_model
from django.test import AsyncClient
from organizations.models import OrganizationUser

from accounts.models import Account
from projects.models import Project

User = get_user_model()


@pytest.mark.django_db(transaction=True)
class TestProjectAPI:
    """Verify project endpoints enforce org scoping."""

    @pytest.fixture
    async def org_users(self):
        """Create two orgs and users."""
        org1 = await sync_to_async(Account.objects.create)(
            name="Org One", subscription_plan="free"
        )
        org2 = await sync_to_async(Account.objects.create)(
            name="Org Two", subscription_plan="pro"
        )

        user1 = await sync_to_async(User.objects.create_user)(
            username="user1", email="user1@example.com", password="password123"
        )
        user2 = await sync_to_async(User.objects.create_user)(
            username="user2", email="user2@example.com", password="password123"
        )

        await sync_to_async(OrganizationUser.objects.create)(
            organization=org1, user=user1, is_admin=True
        )
        await sync_to_async(OrganizationUser.objects.create)(
            organization=org2, user=user2, is_admin=True
        )

        return org1, org2, user1, user2

    @pytest.mark.asyncio
    async def test_list_projects_scoped_to_user_org(self, org_users):
        org1, org2, user1, _user2 = org_users

        # Note: OrganizationUser creation triggers signal that creates a default project
        # So org1 already has a default project from the fixture

        await sync_to_async(Project.objects.create)(
            organization=org1,
            name="Org1 Project",
            working_directory="/tmp/org1",
            created_by=user1,
        )
        await sync_to_async(Project.objects.create)(
            organization=org2,
            name="Org2 Project",
            working_directory="/tmp/org2",
            created_by=None,
        )

        client = AsyncClient()
        await client.aforce_login(user1)

        response = await client.get("/api/projects")
        assert response.status_code == 200
        data = response.json()

        # User1 should only see org1's projects (default + manually created)
        org1_project_count = await sync_to_async(
            Project.objects.filter(organization=org1).count
        )()
        assert data["total"] == org1_project_count

        # Verify all returned project IDs belong to org1's projects
        org1_project_ids = await sync_to_async(
            lambda: set(Project.objects.filter(organization=org1).values_list("id", flat=True))
        )()
        returned_project_ids = {p["id"] for p in data["projects"]}
        assert returned_project_ids == org1_project_ids

    @pytest.mark.asyncio
    async def test_get_project_denies_other_organization(self, org_users):
        org1, org2, user1, _user2 = org_users

        await sync_to_async(Project.objects.create)(
            organization=org1,
            name="Org1 Project",
            working_directory="/tmp/org1",
            created_by=user1,
        )
        other_project = await sync_to_async(Project.objects.create)(
            organization=org2,
            name="Org2 Project",
            working_directory="/tmp/org2",
            created_by=None,
        )

        client = AsyncClient()
        await client.aforce_login(user1)

        response = await client.get(f"/api/projects/{other_project.id}")
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_project_endpoints_require_organization(self):
        """Users without an org receive 403."""
        user = await sync_to_async(User.objects.create_user)(
            username="noorg", email="noorg@example.com", password="password123"
        )

        client = AsyncClient()
        await client.aforce_login(user)

        response = await client.get("/api/projects")
        assert response.status_code == 403
        assert "not associated" in response.json()["detail"]
