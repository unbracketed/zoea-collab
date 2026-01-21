"""Tests for workspace APIs and organization scoping."""

import pytest
from asgiref.sync import sync_to_async
from django.contrib.auth import get_user_model
from django.test import AsyncClient
from organizations.models import OrganizationUser

from accounts.models import Account
from projects.models import Project
from workspaces.models import Workspace

User = get_user_model()


@pytest.mark.django_db(transaction=True)
class TestWorkspaceAPI:
    """Verify workspace endpoints enforce project/org access rules."""

    @pytest.fixture
    async def org_setup(self):
        """Create orgs, users, and projects."""
        org1 = await sync_to_async(Account.objects.create)(name="Org One")
        org2 = await sync_to_async(Account.objects.create)(name="Org Two")

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

        project1 = await sync_to_async(Project.objects.create)(
            organization=org1,
            name="Org1 Project",
            working_directory="/tmp/org1",
            created_by=user1,
        )
        project2 = await sync_to_async(Project.objects.create)(
            organization=org2,
            name="Org2 Project",
            working_directory="/tmp/org2",
            created_by=user2,
        )

        ws1 = await sync_to_async(Workspace.objects.create)(
            project=project1, name="Root Workspace", created_by=user1
        )
        await sync_to_async(Workspace.objects.create)(
            project=project2, name="Other Workspace", created_by=user2
        )

        return org1, org2, user1, user2, project1, project2, ws1

    @pytest.mark.asyncio
    async def test_list_workspaces_scoped_to_org(self, org_setup):
        org1, _org2, user1, _user2, project1, _project2, _ws1 = org_setup

        client = AsyncClient()
        await client.aforce_login(user1)

        response = await client.get("/api/workspaces")
        assert response.status_code == 200
        data = response.json()

        # Note: Project creation triggers signal that creates a default workspace
        # So there are auto-created workspaces in addition to the manually created ones
        # User1 should only see workspaces from projects in org1
        org1_workspace_count = await sync_to_async(
            Workspace.objects.filter(project__organization=org1).count
        )()
        assert data["total"] == org1_workspace_count

        # Verify all returned workspaces belong to org1's projects
        org1_project_ids = await sync_to_async(
            lambda: set(Project.objects.filter(organization=org1).values_list("id", flat=True))
        )()
        assert all(ws["project_id"] in org1_project_ids for ws in data["workspaces"])

    @pytest.mark.asyncio
    async def test_list_workspaces_filters_by_project(self, org_setup):
        _org1, _org2, user1, _user2, project1, _project2, _ws1 = org_setup

        client = AsyncClient()
        await client.aforce_login(user1)

        response = await client.get(f"/api/workspaces?project_id={project1.id}")
        assert response.status_code == 200
        data = response.json()
        assert all(ws["project_id"] == project1.id for ws in data["workspaces"])

    @pytest.mark.asyncio
    async def test_workspace_detail_denies_other_org(self, org_setup):
        _org1, _org2, user1, _user2, _project1, project2, _ws1 = org_setup

        # Use filter().first() since project may have multiple workspaces (from signal + manual creation)
        other_workspace = await sync_to_async(
            Workspace.objects.filter(project=project2).first
        )()

        client = AsyncClient()
        await client.aforce_login(user1)

        response = await client.get(f"/api/workspaces/{other_workspace.id}")
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_workspace_endpoints_require_org(self):
        user = await sync_to_async(User.objects.create_user)(
            username="noorg", email="noorg@example.com", password="password123"
        )
        client = AsyncClient()
        await client.aforce_login(user)

        response = await client.get("/api/workspaces")
        assert response.status_code == 403
        assert "not associated" in response.json()["detail"]
