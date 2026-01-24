"""
Tests for email gateway models.
"""

import pytest
from django.contrib.auth import get_user_model

from organizations.models import Organization
from projects.models import Project
from chat.models import Conversation

from email_gateway.models import EmailThread, EmailMessage

User = get_user_model()


@pytest.fixture
def organization(db):
    """Create a test organization."""
    return Organization.objects.create(name='Test Organization')


@pytest.fixture
def user(db, organization):
    """Create a test user in the organization."""
    user = User.objects.create_user(
        username='testuser',
        email='test@example.com',
        password='testpass'
    )
    organization.add_user(user)
    return user


@pytest.fixture
def project(db, organization, user):
    """Create a test project."""
    return Project.objects.create(
        organization=organization,
        name='Test Project',
        working_directory='/tmp/test',
        created_by=user
    )


@pytest.fixture
def conversation(db, organization, project, user):
    """Create a test conversation."""
    return Conversation.objects.create(
        organization=organization,
        project=project,
        created_by=user,
        agent_name='TestAgent',
        title='Test Conversation'
    )


@pytest.mark.django_db
class TestEmailThreadModel:
    """Tests for EmailThread model."""

    def test_create_email_thread(self, organization, project, conversation, user):
        """Test creating an email thread."""
        from django.utils import timezone

        now = timezone.now()
        thread = EmailThread.objects.create(
            organization=organization,
            project=project,
            conversation=conversation,
            thread_id='<test123@example.com>',
            subject='Test Email Thread',
            initiator_email='sender@example.com',
            initiator_user=user,
            recipient_address='inbox@mail.zoea.studio',
            status='active',
            email_count=0,
            first_email_at=now,
            last_email_at=now,
        )

        assert thread.id is not None
        assert thread.organization == organization
        assert thread.conversation == conversation
        assert thread.thread_id == '<test123@example.com>'
        assert thread.status == 'active'

    def test_email_thread_str(self, organization, conversation):
        """Test string representation."""
        from django.utils import timezone

        now = timezone.now()
        thread = EmailThread.objects.create(
            organization=organization,
            conversation=conversation,
            thread_id='<test123@example.com>',
            subject='Test Subject',
            initiator_email='sender@example.com',
            recipient_address='inbox@mail.zoea.studio',
            email_count=5,
            first_email_at=now,
            last_email_at=now,
        )

        assert str(thread) == 'Test Subject (5 emails)'

    def test_email_thread_ordering(self, organization, conversation):
        """Test that threads are ordered by last_email_at descending."""
        from django.utils import timezone
        from datetime import timedelta

        now = timezone.now()

        # Create a second conversation for the second thread
        conversation2 = Conversation.objects.create(
            organization=organization,
            created_by=conversation.created_by,
            agent_name='TestAgent',
            title='Test Conversation 2'
        )

        thread1 = EmailThread.objects.create(
            organization=organization,
            conversation=conversation,
            thread_id='<older@example.com>',
            subject='Older Thread',
            initiator_email='sender@example.com',
            recipient_address='inbox@mail.zoea.studio',
            first_email_at=now - timedelta(days=2),
            last_email_at=now - timedelta(days=2),
        )

        thread2 = EmailThread.objects.create(
            organization=organization,
            conversation=conversation2,
            thread_id='<newer@example.com>',
            subject='Newer Thread',
            initiator_email='sender@example.com',
            recipient_address='inbox@mail.zoea.studio',
            first_email_at=now,
            last_email_at=now,
        )

        threads = list(EmailThread.objects.all())
        assert threads[0] == thread2  # Newer first
        assert threads[1] == thread1


@pytest.mark.django_db
class TestEmailMessageModel:
    """Tests for EmailMessage model."""

    def test_create_email_message(self, organization):
        """Test creating an email message."""
        msg = EmailMessage.objects.create(
            organization=organization,
            message_id='<msg123@example.com>',
            sender='sender@example.com',
            recipient='inbox@mail.zoea.studio',
            subject='Test Email',
            body_plain='Hello World',
            stripped_text='Hello World',
            status='queued',
        )

        assert msg.id is not None
        assert msg.message_id == '<msg123@example.com>'
        assert msg.status == 'queued'

    def test_email_message_without_organization(self):
        """Test creating message without organization (webhook receives without knowing org)."""
        msg = EmailMessage.objects.create(
            organization=None,  # Unknown at webhook time
            message_id='<unknown123@example.com>',
            sender='unknown@example.com',
            recipient='inbox@mail.zoea.studio',
            subject='Unknown Sender',
            status='queued',
        )

        assert msg.id is not None
        assert msg.organization is None

    def test_email_message_str(self, organization):
        """Test string representation."""
        msg = EmailMessage.objects.create(
            organization=organization,
            message_id='<msg123@example.com>',
            sender='sender@example.com',
            recipient='inbox@mail.zoea.studio',
            subject='This is a very long subject that should be truncated',
            status='queued',
        )

        assert 'sender@example.com' in str(msg)
        assert 'This is a very long subject that should be' in str(msg)

    def test_email_message_unique_message_id(self, organization):
        """Test that message_id must be unique."""
        EmailMessage.objects.create(
            organization=organization,
            message_id='<unique@example.com>',
            sender='sender@example.com',
            recipient='inbox@mail.zoea.studio',
            subject='First',
            status='queued',
        )

        with pytest.raises(Exception):  # IntegrityError
            EmailMessage.objects.create(
                organization=organization,
                message_id='<unique@example.com>',  # Duplicate
                sender='sender@example.com',
                recipient='inbox@mail.zoea.studio',
                subject='Second',
                status='queued',
            )
