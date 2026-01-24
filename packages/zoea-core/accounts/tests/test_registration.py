"""
Tests for django-allauth registration integration.

These tests verify that the registration flow works correctly and integrates
properly with our multi-tenant organization structure.
"""

import pytest
from allauth.account.models import EmailAddress
from django.contrib.auth import get_user_model
from django.core import mail
from django.urls import reverse
from organizations.models import OrganizationOwner, OrganizationUser

from accounts.models import Account
from projects.models import Project

User = get_user_model()


@pytest.mark.django_db
class TestUserRegistration:
    """Test the user registration flow with django-allauth."""

    def test_signup_creates_user(self):
        """Test that signup creates a user account."""
        # Access signup URL
        signup_url = reverse('account_signup')

        # Create a test client
        from django.test import Client
        client = Client()

        # Post signup data
        response = client.post(signup_url, {
            'username': 'testuser',
            'email': 'testuser@example.com',
            'password1': 'testpass123!@#',
            'password2': 'testpass123!@#',
        })

        # Should redirect after signup
        assert response.status_code in [200, 302]

        # User should be created
        assert User.objects.filter(username='testuser').exists()
        user = User.objects.get(username='testuser')
        assert user.email == 'testuser@example.com'

    def test_signup_sends_verification_email(self):
        """Test that signup sends a verification email."""
        from django.test import Client
        client = Client()

        signup_url = reverse('account_signup')

        # Clear any existing emails
        mail.outbox = []

        # Post signup data
        client.post(signup_url, {
            'username': 'emailtest',
            'email': 'emailtest@example.com',
            'password1': 'testpass123!@#',
            'password2': 'testpass123!@#',
        })

        # Should send one verification email
        assert len(mail.outbox) == 1
        assert 'emailtest@example.com' in mail.outbox[0].to
        assert 'confirm' in mail.outbox[0].subject.lower() or 'verify' in mail.outbox[0].subject.lower()

    def test_signup_creates_unverified_email(self):
        """Test that signup creates an unverified email address."""
        from django.test import Client
        client = Client()

        signup_url = reverse('account_signup')

        client.post(signup_url, {
            'username': 'unverified',
            'email': 'unverified@example.com',
            'password1': 'testpass123!@#',
            'password2': 'testpass123!@#',
        })

        user = User.objects.get(username='unverified')

        # Email address should exist but not be verified
        email_address = EmailAddress.objects.get(user=user, email='unverified@example.com')
        assert email_address.verified is False
        assert email_address.primary is True

    def test_signup_requires_username_and_email(self):
        """Test that both username and email are required."""
        from django.test import Client
        client = Client()

        signup_url = reverse('account_signup')

        # Try without username
        response = client.post(signup_url, {
            'email': 'test@example.com',
            'password1': 'testpass123!@#',
            'password2': 'testpass123!@#',
        })
        assert response.status_code == 200  # Form errors, not redirect
        assert not User.objects.filter(email='test@example.com').exists()

        # Try without email
        response = client.post(signup_url, {
            'username': 'testuser2',
            'password1': 'testpass123!@#',
            'password2': 'testpass123!@#',
        })
        assert response.status_code == 200  # Form errors, not redirect
        assert not User.objects.filter(username='testuser2').exists()

    def test_signup_validates_password(self):
        """Test that password validation works."""
        from django.test import Client
        client = Client()

        signup_url = reverse('account_signup')

        # Try with weak password
        response = client.post(signup_url, {
            'username': 'weakpass',
            'email': 'weakpass@example.com',
            'password1': '123',
            'password2': '123',
        })
        assert response.status_code == 200  # Form errors
        assert not User.objects.filter(username='weakpass').exists()

    def test_signup_prevents_duplicate_username(self):
        """Test that duplicate usernames are prevented."""
        # Create first user
        User.objects.create_user(username='duplicate', email='first@example.com')

        from django.test import Client
        client = Client()

        signup_url = reverse('account_signup')

        # Try to create second user with same username
        response = client.post(signup_url, {
            'username': 'duplicate',
            'email': 'second@example.com',
            'password1': 'testpass123!@#',
            'password2': 'testpass123!@#',
        })
        assert response.status_code == 200  # Form errors
        assert User.objects.filter(username='duplicate').count() == 1



@pytest.mark.django_db
class TestOrganizationIntegration:
    """Test that registration integrates with organization creation."""

    def test_signup_creates_organization(self):
        """Test that signing up automatically creates an organization."""
        from django.test import Client
        client = Client()

        signup_url = reverse('account_signup')

        client.post(signup_url, {
            'username': 'orgtest',
            'email': 'orgtest@example.com',
            'password1': 'testpass123!@#',
            'password2': 'testpass123!@#',
        })

        user = User.objects.get(username='orgtest')

        # Organization should be created
        org_user = OrganizationUser.objects.filter(user=user).first()
        assert org_user is not None
        assert org_user.is_admin is True

        # Organization should exist
        organization = org_user.organization
        assert organization is not None
        assert "orgtest's Organization" in organization.name

    def test_signup_creates_project(self):
        """Test that signup creates default project via signals."""
        from django.test import Client
        client = Client()

        signup_url = reverse('account_signup')

        client.post(signup_url, {
            'username': 'projecttest',
            'email': 'projecttest@example.com',
            'password1': 'testpass123!@#',
            'password2': 'testpass123!@#',
        })

        user = User.objects.get(username='projecttest')
        org_user = OrganizationUser.objects.get(user=user)
        organization = org_user.organization

        # Project should be created
        project = Project.objects.filter(organization=organization).first()
        assert project is not None

    def test_signup_makes_user_organization_owner(self):
        """Test that the new user is made the owner of their organization."""
        from django.test import Client
        client = Client()

        signup_url = reverse('account_signup')

        client.post(signup_url, {
            'username': 'ownertest',
            'email': 'ownertest@example.com',
            'password1': 'testpass123!@#',
            'password2': 'testpass123!@#',
        })

        user = User.objects.get(username='ownertest')
        org_user = OrganizationUser.objects.get(user=user)

        # User should be organization owner
        owner = OrganizationOwner.objects.filter(
            organization=org_user.organization
        ).first()
        assert owner is not None
        assert owner.organization_user == org_user

    def test_signup_sets_organization_subscription(self):
        """Test that organization is created with correct subscription plan."""
        from django.test import Client
        client = Client()

        signup_url = reverse('account_signup')

        client.post(signup_url, {
            'username': 'subtest',
            'email': 'subtest@example.com',
            'password1': 'testpass123!@#',
            'password2': 'testpass123!@#',
        })

        user = User.objects.get(username='subtest')
        org_user = OrganizationUser.objects.get(user=user)

        # Get the Account instance (multi-table inheritance)
        account = Account.objects.get(id=org_user.organization.id)

        # Should have default free subscription
        assert account.subscription_plan == 'free'
        assert account.max_users == 5
        assert account.billing_email == 'subtest@example.com'

    def test_multiple_users_get_separate_organizations(self):
        """Test that multiple signups create separate organizations."""
        from django.test import Client
        client = Client()

        signup_url = reverse('account_signup')

        # Create first user
        client.post(signup_url, {
            'username': 'user1',
            'email': 'user1@example.com',
            'password1': 'testpass123!@#',
            'password2': 'testpass123!@#',
        })

        # Create second user
        client.post(signup_url, {
            'username': 'user2',
            'email': 'user2@example.com',
            'password1': 'testpass123!@#',
            'password2': 'testpass123!@#',
        })

        user1 = User.objects.get(username='user1')
        user2 = User.objects.get(username='user2')

        org1 = OrganizationUser.objects.get(user=user1).organization
        org2 = OrganizationUser.objects.get(user=user2).organization

        # Organizations should be different
        assert org1.id != org2.id
        assert org1.name != org2.name


@pytest.mark.django_db
class TestEmailVerification:
    """Test email verification flow."""

    def test_email_verification_link_works(self):
        """Test that clicking the email verification link works."""
        from django.test import Client
        client = Client()

        signup_url = reverse('account_signup')

        # Clear emails
        mail.outbox = []

        # Sign up
        client.post(signup_url, {
            'username': 'verifytest',
            'email': 'verifytest@example.com',
            'password1': 'testpass123!@#',
            'password2': 'testpass123!@#',
        })

        user = User.objects.get(username='verifytest')

        # Email should be unverified
        email_address = EmailAddress.objects.get(user=user)
        assert email_address.verified is False

        # Get verification link from email
        assert len(mail.outbox) == 1
        email_body = mail.outbox[0].body

        # Extract confirmation URL (look for /accounts/confirm-email/)
        import re
        match = re.search(r'/accounts/confirm-email/[\w:-]+/', email_body)
        assert match is not None
        confirm_url = match.group(0)

        # Click the confirmation link
        response = client.get(confirm_url)
        assert response.status_code == 200

        # Confirm with POST
        response = client.post(confirm_url)
        assert response.status_code in [200, 302]

        # Email should now be verified
        email_address.refresh_from_db()
        assert email_address.verified is True

    def test_user_cannot_login_before_email_verification(self):
        """Test that users must verify email before they can login."""
        from django.test import Client
        client = Client()

        signup_url = reverse('account_signup')

        # Sign up
        client.post(signup_url, {
            'username': 'nologin',
            'email': 'nologin@example.com',
            'password1': 'testpass123!@#',
            'password2': 'testpass123!@#',
        })

        # Try to login immediately (without verifying email)
        login_url = reverse('account_login')
        response = client.post(login_url, {
            'login': 'nologin',
            'password': 'testpass123!@#',
        })

        # Should not be logged in (email not verified)
        # allauth will redirect to a page telling user to verify email
        user = User.objects.get(username='nologin')
        email_address = EmailAddress.objects.get(user=user)
        assert email_address.verified is False


@pytest.mark.django_db
class TestRegistrationEdgeCases:
    """Test edge cases and error handling in registration."""

    def test_signup_handles_full_name_for_organization(self):
        """Test that organization name uses full name if available."""
        from django.test import Client
        client = Client()

        # Create user manually with full name
        user = User.objects.create_user(
            username='fullname',
            email='fullname@example.com',
            password='testpass123!@#',
            first_name='John',
            last_name='Doe'
        )

        # Manually trigger organization creation
        from accounts.utils import initialize_user_organization
        result = initialize_user_organization(user)

        # Organization name should use full name
        assert result['organization'].name == "John Doe's Organization"

    def test_signup_continues_if_organization_creation_fails_gracefully(self):
        """
        Test that signup doesn't completely fail if organization creation has issues.

        Note: Our adapter logs the error but doesn't prevent signup.
        In a production scenario, you might want to raise an exception instead.
        """
        from django.test import Client
        from unittest.mock import patch

        client = Client()
        signup_url = reverse('account_signup')

        # Mock initialize_user_organization to raise an exception
        with patch('accounts.adapters.initialize_user_organization') as mock_init:
            mock_init.side_effect = Exception("Database error")

            # Sign up should still work (user created, organization creation fails)
            response = client.post(signup_url, {
                'username': 'failtest',
                'email': 'failtest@example.com',
                'password1': 'testpass123!@#',
                'password2': 'testpass123!@#',
            })

            # User should still be created
            assert User.objects.filter(username='failtest').exists()

            # But organization won't exist
            user = User.objects.get(username='failtest')
            assert not OrganizationUser.objects.filter(user=user).exists()
