"""Tests for workflow models and org scoping."""

import pytest
from django.contrib.auth import get_user_model
from organizations.models import OrganizationUser

from accounts.models import Account
from workflows.models import Workflow

User = get_user_model()


@pytest.mark.django_db
class TestWorkflowModel:
    """Validate workflow model helpers and scoping."""

    @pytest.fixture
    def orgs_and_users(self):
        org1 = Account.objects.create(name="Org One")
        org2 = Account.objects.create(name="Org Two")
        user1 = User.objects.create_user(username="user1")
        user2 = User.objects.create_user(username="user2")
        OrganizationUser.objects.create(organization=org1, user=user1)
        OrganizationUser.objects.create(organization=org2, user=user2)
        return org1, org2, user1, user2

    def test_queryset_for_user(self, orgs_and_users):
        org1, org2, user1, user2 = orgs_and_users
        wf1 = Workflow.objects.create(
            organization=org1, name="Org1 Workflow", created_by=user1
        )
        Workflow.objects.create(
            organization=org2, name="Org2 Workflow", created_by=user2
        )

        user1_workflows = list(Workflow.objects.for_user(user1))
        assert user1_workflows == [wf1]

    def test_unique_per_org_and_str(self, orgs_and_users):
        org1, _org2, user1, _user2 = orgs_and_users
        wf1 = Workflow.objects.create(
            organization=org1, name="Build", created_by=user1
        )
        assert str(wf1) == "Build (Org One)"

        with pytest.raises(Exception):
            Workflow.objects.create(
                organization=org1, name="Build", created_by=user1
            )
