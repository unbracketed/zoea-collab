"""
Tests for the accounts app and django-organizations integration.

These tests verify that the multi-tenant architecture works correctly,
including organization creation, user relationships, and access control.
"""

import pytest
from django.contrib.auth import get_user_model
from organizations.models import OrganizationUser, OrganizationOwner

from accounts.models import Account
from accounts.utils import (
    get_user_organization,
    require_organization,
    get_user_organizations,
    is_organization_admin,
    is_organization_owner,
    can_add_user_to_organization,
    initialize_user_organization,
)

User = get_user_model()


@pytest.mark.django_db
class TestAccountModel:
    """Test the Account model functionality."""

    def test_create_account(self):
        """Test creating a basic account."""
        account = Account.objects.create(
            name="Test Organization",
            subscription_plan="free",
        )
        assert account.name == "Test Organization"
        assert account.subscription_plan == "free"
        assert account.max_users == 5  # default
        assert account.slug == "test-organization"

    def test_account_str(self):
        """Test the string representation of an account."""
        account = Account.objects.create(
            name="My Company",
            subscription_plan="pro",
        )
        assert str(account) == "My Company (Pro)"

    def test_user_limit_methods(self):
        """Test user limit checking methods."""
        account = Account.objects.create(
            name="Limited Org",
            max_users=2,
        )

        # No users yet
        assert account.can_add_user() is True
        assert account.is_at_user_limit() is False

        # Add first user
        user1 = User.objects.create_user(username="user1", email="user1@test.com")
        OrganizationUser.objects.create(organization=account, user=user1)

        assert account.can_add_user() is True
        assert account.is_at_user_limit() is False

        # Add second user (at limit)
        user2 = User.objects.create_user(username="user2", email="user2@test.com")
        OrganizationUser.objects.create(organization=account, user=user2)

        assert account.can_add_user() is False
        assert account.is_at_user_limit() is True


@pytest.mark.django_db
class TestOrganizationUtils:
    """Test utility functions for organization access."""

    @pytest.fixture
    def account(self):
        """Create a test account."""
        return Account.objects.create(
            name="Test Org",
            subscription_plan="free",
        )

    @pytest.fixture
    def user(self):
        """Create a test user."""
        return User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123",
        )

    @pytest.fixture
    def org_user(self, account, user):
        """Create an organization user relationship."""
        return OrganizationUser.objects.create(
            organization=account,
            user=user,
            is_admin=True,
        )

    def test_get_user_organization(self, account, user, org_user):
        """Test getting a user's organization."""
        org = get_user_organization(user)
        assert org is not None
        assert org.id == account.id
        assert org.name == account.name

    def test_get_user_organization_no_org(self, user):
        """Test getting organization for user without one."""
        org = get_user_organization(user)
        assert org is None

    def test_require_organization(self, account, user, org_user):
        """Test requiring an organization (success case)."""
        org = require_organization(user)
        assert org.id == account.id

    def test_require_organization_raises(self, user):
        """Test requiring an organization raises when user has none."""
        with pytest.raises(ValueError, match="not associated with any organization"):
            require_organization(user)

    def test_get_user_organizations(self, user):
        """Test getting all organizations for a user."""
        # Create multiple organizations
        org1 = Account.objects.create(name="Org 1")
        org2 = Account.objects.create(name="Org 2")

        OrganizationUser.objects.create(organization=org1, user=user)
        OrganizationUser.objects.create(organization=org2, user=user)

        orgs = get_user_organizations(user)
        assert orgs.count() == 2
        # Compare IDs due to multi-table inheritance
        org_ids = list(orgs.values_list('id', flat=True))
        assert org1.id in org_ids
        assert org2.id in org_ids

    def test_is_organization_admin(self, account, user):
        """Test checking if user is organization admin."""
        # Not admin initially
        OrganizationUser.objects.create(
            organization=account,
            user=user,
            is_admin=False,
        )
        assert is_organization_admin(user, account) is False

        # Update to admin
        org_user = OrganizationUser.objects.get(user=user, organization=account)
        org_user.is_admin = True
        org_user.save()

        assert is_organization_admin(user, account) is True

    def test_is_organization_owner(self, account, user, org_user):
        """Test checking if user is organization owner."""
        # Not owner initially
        assert is_organization_owner(user, account) is False

        # Make them owner
        OrganizationOwner.objects.create(
            organization=account,
            organization_user=org_user,
        )

        assert is_organization_owner(user, account) is True

    def test_can_add_user_to_organization(self):
        """Test checking if users can be added to organization."""
        account = Account.objects.create(
            name="Limited Org",
            max_users=1,
        )

        # Can add initially
        assert can_add_user_to_organization(account) is True

        # Add a user
        user = User.objects.create_user(username="user1", email="user1@test.com")
        OrganizationUser.objects.create(organization=account, user=user)

        # At limit now
        assert can_add_user_to_organization(account) is False


@pytest.mark.django_db
class TestOrganizationIsolation:
    """Test that organizations properly isolate data between tenants."""

    @pytest.fixture
    def org1(self):
        """Create first organization."""
        return Account.objects.create(name="Organization 1")

    @pytest.fixture
    def org2(self):
        """Create second organization."""
        return Account.objects.create(name="Organization 2")

    @pytest.fixture
    def user1(self, org1):
        """Create user in org1."""
        user = User.objects.create_user(username="user1", email="user1@test.com")
        OrganizationUser.objects.create(organization=org1, user=user)
        return user

    @pytest.fixture
    def user2(self, org2):
        """Create user in org2."""
        user = User.objects.create_user(username="user2", email="user2@test.com")
        OrganizationUser.objects.create(organization=org2, user=user)
        return user

    def test_users_see_only_their_organization(self, org1, org2, user1, user2):
        """Test that users only see their own organization."""
        # User 1 should only see org1
        orgs1 = get_user_organizations(user1)
        assert orgs1.count() == 1
        # Compare IDs due to multi-table inheritance
        org1_ids = list(orgs1.values_list('id', flat=True))
        assert org1.id in org1_ids
        assert org2.id not in org1_ids

        # User 2 should only see org2
        orgs2 = get_user_organizations(user2)
        assert orgs2.count() == 1
        org2_ids = list(orgs2.values_list('id', flat=True))
        assert org2.id in org2_ids
        assert org1.id not in org2_ids

    def test_user_cannot_be_admin_of_other_org(self, org1, org2, user1):
        """Test that user is not admin of organizations they don't belong to."""
        assert is_organization_admin(user1, org1) is False  # Not admin yet
        assert is_organization_admin(user1, org2) is False  # Different org


@pytest.mark.django_db
class TestInitializeUserOrganization:
    """Test the initialize_user_organization utility function."""

    def test_initialize_user_organization_creates_complete_setup(self):
        """Test that initialize_user_organization creates org, project, and workspace."""
        from accounts.utils import initialize_user_organization
        from projects.models import Project
        from workspaces.models import Workspace

        # Create a user
        user = User.objects.create_user(
            username='alice',
            email='alice@example.com',
            password='testpass123'
        )

        # Initialize organization for user
        result = initialize_user_organization(user)

        # Verify all objects were created
        assert 'organization' in result
        assert 'project' in result
        assert 'workspace' in result

        organization = result['organization']
        project = result['project']
        workspace = result['workspace']

        # Verify organization
        assert organization is not None
        assert organization.name == "alice's Organization"
        assert organization.subscription_plan == 'free'
        assert organization.max_users == 5
        assert organization.billing_email == 'alice@example.com'

        # Verify user is a member and owner
        assert OrganizationUser.objects.filter(
            organization=organization,
            user=user,
            is_admin=True
        ).exists()
        assert OrganizationOwner.objects.filter(
            organization=organization,
        ).exists()

        # Verify project was created by signals
        assert project is not None
        assert project.organization.id == organization.id  # Compare IDs due to multi-table inheritance
        assert Project.objects.filter(organization=organization).count() == 1

        # Verify workspace was created by signals
        assert workspace is not None
        assert workspace.project == project
        assert workspace.parent is None  # Root workspace
        assert Workspace.objects.filter(project=project, parent=None).count() == 1

    def test_initialize_user_organization_with_custom_org_name(self):
        """Test creating organization with custom name."""
        from accounts.utils import initialize_user_organization

        user = User.objects.create_user(
            username='bob',
            email='bob@example.com',
            password='testpass123'
        )

        result = initialize_user_organization(user, org_name="Bob's Company")

        assert result['organization'].name == "Bob's Company"

    def test_initialize_user_organization_with_custom_subscription(self):
        """Test creating organization with pro subscription."""
        from accounts.utils import initialize_user_organization

        user = User.objects.create_user(
            username='charlie',
            email='charlie@example.com',
            password='testpass123'
        )

        result = initialize_user_organization(
            user,
            subscription_plan='pro',
            max_users=10
        )

        org = result['organization']
        assert org.subscription_plan == 'pro'
        assert org.max_users == 10

    def test_initialize_user_organization_uses_full_name_if_available(self):
        """Test that org name defaults to user's full name if set."""
        from accounts.utils import initialize_user_organization

        user = User.objects.create_user(
            username='dave',
            email='dave@example.com',
            password='testpass123',
            first_name='David',
            last_name='Smith'
        )

        result = initialize_user_organization(user)

        assert result['organization'].name == "David Smith's Organization"

    def test_initialize_user_organization_rollback_on_error(self):
        """Test that transaction rolls back if signals fail."""
        from accounts.utils import initialize_user_organization
        from unittest.mock import patch

        user = User.objects.create_user(
            username='eve',
            email='eve@example.com',
            password='testpass123'
        )

        # Mock Project.objects.filter to simulate signal failure
        with patch('projects.models.Project.objects.filter') as mock_filter:
            mock_filter.return_value.first.return_value = None

            # Should raise ValueError due to missing project
            with pytest.raises(ValueError, match="Failed to initialize user organization"):
                initialize_user_organization(user)

        # Verify rollback - no organization should exist
        assert Account.objects.filter(billing_email='eve@example.com').count() == 0
        assert OrganizationUser.objects.filter(user=user).count() == 0

    def test_initialize_user_organization_atomic_transaction(self):
        """Test that all operations are atomic."""
        from accounts.utils import initialize_user_organization

        user = User.objects.create_user(
            username='frank',
            email='frank@example.com',
            password='testpass123'
        )

        # Get counts before
        org_count_before = Account.objects.count()
        org_user_count_before = OrganizationUser.objects.count()
        owner_count_before = OrganizationOwner.objects.count()

        # Initialize
        result = initialize_user_organization(user)

        # Verify exactly one of each was created
        assert Account.objects.count() == org_count_before + 1
        assert OrganizationUser.objects.count() == org_user_count_before + 1
        assert OrganizationOwner.objects.count() == owner_count_before + 1

    def test_initialize_user_organization_multiple_users(self):
        """Test creating organizations for multiple users."""
        from accounts.utils import initialize_user_organization

        # Create two users
        user1 = User.objects.create_user(
            username='grace',
            email='grace@example.com',
            password='testpass123'
        )
        user2 = User.objects.create_user(
            username='henry',
            email='henry@example.com',
            password='testpass123'
        )

        # Initialize organizations for both
        result1 = initialize_user_organization(user1)
        result2 = initialize_user_organization(user2)

        # Verify they have separate organizations
        assert result1['organization'].id != result2['organization'].id
        assert result1['project'].id != result2['project'].id
        assert result1['workspace'].id != result2['workspace'].id


@pytest.mark.django_db
class TestAuthAPIEndpoints:
    """Test authentication API endpoints."""

    @pytest.fixture
    def api_client(self):
        """Create an API client for testing."""
        from django.test import Client
        return Client()

    def test_signup_endpoint_success(self, api_client):
        """Test successful user registration via API."""
        from allauth.account.models import EmailAddress

        payload = {
            'username': 'newuser',
            'email': 'newuser@example.com',
            'password1': 'testpass123!',
            'password2': 'testpass123!',
        }

        response = api_client.post(
            '/api/auth/signup',
            data=payload,
            content_type='application/json'
        )

        assert response.status_code == 200
        data = response.json()
        assert data['success'] is True
        assert data['username'] == 'newuser'
        assert data['email'] == 'newuser@example.com'
        assert 'verify' in data['message'].lower()

        # Verify user was created
        user = User.objects.get(username='newuser')
        assert user.email == 'newuser@example.com'

        # Verify organization was created
        from accounts.utils import get_user_organization
        org = get_user_organization(user)
        assert org is not None
        assert "newuser's Organization" in org.name

        # Verify email address was created but not verified
        email_address = EmailAddress.objects.get(user=user, email='newuser@example.com')
        assert email_address.verified is False

    def test_signup_endpoint_password_mismatch(self, api_client):
        """Test signup fails when passwords don't match."""
        payload = {
            'username': 'testuser',
            'email': 'test@example.com',
            'password1': 'password123!',
            'password2': 'different123!',
        }

        response = api_client.post(
            '/api/auth/signup',
            data=payload,
            content_type='application/json'
        )

        assert response.status_code == 400
        data = response.json()
        assert 'password' in data['detail'].lower()

    def test_signup_endpoint_duplicate_username(self, api_client):
        """Test signup fails with duplicate username."""
        # Create existing user
        User.objects.create_user(username='existing', email='existing@example.com')

        payload = {
            'username': 'existing',
            'email': 'newemail@example.com',
            'password1': 'testpass123!',
            'password2': 'testpass123!',
        }

        response = api_client.post(
            '/api/auth/signup',
            data=payload,
            content_type='application/json'
        )

        assert response.status_code == 400
        data = response.json()
        assert 'username' in data['detail'].lower()

    def test_signup_endpoint_duplicate_email(self, api_client):
        """Test signup fails with duplicate email."""
        # Create existing user
        User.objects.create_user(username='user1', email='duplicate@example.com')

        payload = {
            'username': 'newuser',
            'email': 'duplicate@example.com',
            'password1': 'testpass123!',
            'password2': 'testpass123!',
        }

        response = api_client.post(
            '/api/auth/signup',
            data=payload,
            content_type='application/json'
        )

        assert response.status_code == 400
        data = response.json()
        assert 'email' in data['detail'].lower()

    def test_signup_endpoint_weak_password(self, api_client):
        """Test signup fails with weak password."""
        payload = {
            'username': 'testuser',
            'email': 'test@example.com',
            'password1': '123',
            'password2': '123',
        }

        response = api_client.post(
            '/api/auth/signup',
            data=payload,
            content_type='application/json'
        )

        # Pydantic validation returns 422 for schema violations
        assert response.status_code in [400, 422]
        data = response.json()
        # Check that the error is about password length
        response_str = str(data).lower()
        assert 'password' in response_str or 'length' in response_str

    def test_signup_endpoint_invalid_email(self, api_client):
        """Test signup fails with invalid email."""
        payload = {
            'username': 'testuser',
            'email': 'not-an-email',
            'password1': 'testpass123!',
            'password2': 'testpass123!',
        }

        response = api_client.post(
            '/api/auth/signup',
            data=payload,
            content_type='application/json'
        )

        assert response.status_code == 400
        data = response.json()
        assert 'email' in data['detail'].lower()

    def test_verify_email_endpoint_success(self, api_client):
        """Test email verification with valid key."""
        from allauth.account.models import EmailAddress, EmailConfirmation
        from django.utils import timezone

        # Create user
        user = User.objects.create_user(
            username='verifyuser',
            email='verify@example.com',
            password='testpass123!'
        )

        # Create email address (not verified)
        email_address = EmailAddress.objects.create(
            user=user,
            email='verify@example.com',
            verified=False,
            primary=True
        )

        # Create email confirmation
        email_confirmation = EmailConfirmation.create(email_address)
        email_confirmation.sent = timezone.now()  # Set sent timestamp
        email_confirmation.save()

        # Verify email
        payload = {'key': email_confirmation.key}
        response = api_client.post(
            '/api/auth/verify-email',
            data=payload,
            content_type='application/json'
        )

        assert response.status_code == 200
        data = response.json()
        assert data['success'] is True
        assert 'verified successfully' in data['message'].lower()

        # Verify email is now verified
        email_address.refresh_from_db()
        assert email_address.verified is True

    def test_verify_email_endpoint_invalid_key(self, api_client):
        """Test email verification with invalid key."""
        payload = {'key': 'invalid-key-12345'}
        response = api_client.post(
            '/api/auth/verify-email',
            data=payload,
            content_type='application/json'
        )

        assert response.status_code == 400
        data = response.json()
        assert 'invalid' in data['detail'].lower()

    def test_verify_email_endpoint_already_verified(self, api_client):
        """Test email verification when already verified."""
        from allauth.account.models import EmailAddress, EmailConfirmation
        from django.utils import timezone

        # Create user with verified email
        user = User.objects.create_user(
            username='verifieduser',
            email='verified@example.com',
            password='testpass123!'
        )

        email_address = EmailAddress.objects.create(
            user=user,
            email='verified@example.com',
            verified=True,
            primary=True
        )

        # Create confirmation anyway
        email_confirmation = EmailConfirmation.create(email_address)
        email_confirmation.sent = timezone.now()  # Set sent timestamp
        email_confirmation.save()

        # Try to verify
        payload = {'key': email_confirmation.key}
        response = api_client.post(
            '/api/auth/verify-email',
            data=payload,
            content_type='application/json'
        )

        assert response.status_code == 200
        data = response.json()
        assert data['success'] is True
        assert 'already verified' in data['message'].lower()

    def test_resend_verification_endpoint_success(self, api_client):
        """Test resending verification email."""
        from allauth.account.models import EmailAddress

        # Create user with unverified email
        user = User.objects.create_user(
            username='resenduser',
            email='resend@example.com',
            password='testpass123!'
        )

        EmailAddress.objects.create(
            user=user,
            email='resend@example.com',
            verified=False,
            primary=True
        )

        payload = {'email': 'resend@example.com'}
        response = api_client.post(
            '/api/auth/resend-verification',
            data=payload,
            content_type='application/json'
        )

        assert response.status_code == 200
        data = response.json()
        assert data['success'] is True
        assert 'verification email sent' in data['message'].lower()

    def test_resend_verification_endpoint_already_verified(self, api_client):
        """Test resending verification to already verified email."""
        from allauth.account.models import EmailAddress

        # Create user with verified email
        user = User.objects.create_user(
            username='alreadyverified',
            email='already@example.com',
            password='testpass123!'
        )

        EmailAddress.objects.create(
            user=user,
            email='already@example.com',
            verified=True,
            primary=True
        )

        payload = {'email': 'already@example.com'}
        response = api_client.post(
            '/api/auth/resend-verification',
            data=payload,
            content_type='application/json'
        )

        assert response.status_code == 400
        data = response.json()
        assert 'already verified' in data['detail'].lower()

    def test_resend_verification_endpoint_nonexistent_email(self, api_client):
        """Test resending verification to non-existent email (should succeed for security)."""
        payload = {'email': 'nonexistent@example.com'}
        response = api_client.post(
            '/api/auth/resend-verification',
            data=payload,
            content_type='application/json'
        )

        # Should return success to avoid revealing whether email exists
        assert response.status_code == 200
        data = response.json()
        assert data['success'] is True

    def test_signup_creates_complete_organization_structure(self, api_client):
        """Test that signup creates org, project, workspace, and clipboard."""
        from projects.models import Project
        from workspaces.models import Workspace
        from context_clipboards.models import Clipboard

        payload = {
            'username': 'fullsetup',
            'email': 'fullsetup@example.com',
            'password1': 'testpass123!',
            'password2': 'testpass123!',
        }

        response = api_client.post(
            '/api/auth/signup',
            data=payload,
            content_type='application/json'
        )

        assert response.status_code == 200

        # Verify user
        user = User.objects.get(username='fullsetup')

        # Verify organization
        from accounts.utils import get_user_organization
        org = get_user_organization(user)
        assert org is not None

        # Verify project
        project = Project.objects.filter(organization=org).first()
        assert project is not None

        # Verify workspace
        workspace = Workspace.objects.filter(project=project, parent=None).first()
        assert workspace is not None

        # Verify clipboard
        clipboard = Clipboard.objects.filter(workspace=workspace, owner=user, is_active=True).first()
        assert clipboard is not None
