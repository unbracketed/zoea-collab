"""
Tests for email processing service.
"""

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.core.files.uploadedfile import SimpleUploadedFile

from organizations.models import Organization, OrganizationUser
from projects.models import Project
from chat.models import Conversation, Message
from documents.models import FileDocument, Folder

from email_gateway.models import EmailThread, EmailMessage, EmailAttachment
from email_gateway.services import EmailProcessingService, EmailProcessingError

User = get_user_model()


@pytest.fixture
def organization(db):
    """Create a test organization."""
    return Organization.objects.create(name='Test Organization')


@pytest.fixture
def user(db, organization):
    """Create a test user with email in the organization."""
    user = User.objects.create_user(
        username='testuser',
        email='sender@example.com',  # Important: matches sender in tests
        password='testpass'
    )
    org_user = organization.add_user(user)
    org_user.is_admin = True
    org_user.save()
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
def email_message(db, organization, project):
    """Create a test email message ready for processing."""
    return EmailMessage.objects.create(
        organization=None,  # Will be set during processing
        message_id='<test-123@example.com>',
        sender='sender@example.com',
        recipient=project.canonical_email,
        subject='Test Email Subject',
        stripped_text='This is the email content.',
        body_plain='This is the email content.\n\n-- \nSignature',
        status='queued',
    )


@pytest.fixture
def service():
    """Create email processing service."""
    return EmailProcessingService()


@pytest.mark.django_db
class TestEmailProcessingService:
    """Tests for EmailProcessingService."""

    def test_process_email_creates_thread_and_message(
        self, service, email_message, user, organization, project
    ):
        """Test that processing creates EmailThread and chat Message."""
        result = service.process_email(email_message.id)

        assert result is True

        # Reload from database
        email_message.refresh_from_db()

        assert email_message.status == 'processed'
        assert email_message.organization == organization
        assert email_message.sender_user == user
        assert email_message.email_thread is not None
        assert email_message.chat_message is not None

        # Check thread was created
        thread = email_message.email_thread
        assert thread.subject == 'Test Email Subject'
        assert thread.initiator_email == 'sender@example.com'
        assert thread.initiator_user == user
        assert thread.organization == organization
        assert thread.conversation is not None

        # Check chat message was created
        chat_msg = email_message.chat_message
        assert chat_msg.role == 'user'
        assert chat_msg.content == 'This is the email content.'

    def test_process_email_unknown_sender_fails(self, service, db, project):
        """Test that processing fails for unknown senders."""
        email_msg = EmailMessage.objects.create(
            message_id='<unknown-sender@example.com>',
            sender='unknown@nowhere.com',
            recipient=project.canonical_email,
            subject='Unknown Sender',
            stripped_text='Hello',
            status='queued',
        )

        with pytest.raises(EmailProcessingError) as exc:
            service.process_email(email_msg.id)

        assert 'not a registered user' in str(exc.value)

        # Check status was updated
        email_msg.refresh_from_db()
        assert email_msg.status == 'failed'

    def test_process_email_already_processed(self, service, email_message, user):
        """Test that already processed emails are skipped."""
        email_message.status = 'processed'
        email_message.save()

        result = service.process_email(email_message.id)

        assert result is False

    def test_thread_resolution_via_references(
        self, service, organization, user, project
    ):
        """Test that replies are linked via References header."""
        # First email creates a thread
        first_email = EmailMessage.objects.create(
            message_id='<first@example.com>',
            sender='sender@example.com',
            recipient=project.canonical_email,
            subject='Original Subject',
            stripped_text='First message',
            status='queued',
        )
        service.process_email(first_email.id)
        first_email.refresh_from_db()

        # Reply email with References pointing to first
        reply_email = EmailMessage.objects.create(
            message_id='<reply@example.com>',
            sender='sender@example.com',
            recipient=project.canonical_email,
            subject='Re: Original Subject',
            stripped_text='Reply message',
            references='<first@example.com>',  # Points to first email
            status='queued',
        )
        service.process_email(reply_email.id)
        reply_email.refresh_from_db()

        # Both should be in same thread
        assert reply_email.email_thread == first_email.email_thread
        assert first_email.email_thread.email_count == 2

    def test_thread_resolution_via_in_reply_to(
        self, service, organization, user, project
    ):
        """Test that replies are linked via In-Reply-To header."""
        # First email creates a thread
        first_email = EmailMessage.objects.create(
            message_id='<original@example.com>',
            sender='sender@example.com',
            recipient=project.canonical_email,
            subject='Original Subject',
            stripped_text='First message',
            status='queued',
        )
        service.process_email(first_email.id)
        first_email.refresh_from_db()

        # Reply email with In-Reply-To
        reply_email = EmailMessage.objects.create(
            message_id='<reply2@example.com>',
            sender='sender@example.com',
            recipient=project.canonical_email,
            subject='Re: Original Subject',
            stripped_text='Reply message',
            in_reply_to='<original@example.com>',  # Points to first email
            status='queued',
        )
        service.process_email(reply_email.id)
        reply_email.refresh_from_db()

        # Both should be in same thread
        assert reply_email.email_thread == first_email.email_thread

    def test_thread_creation_for_new_email(
        self, service, organization, user, project
    ):
        """Test that new emails create new threads."""
        email1 = EmailMessage.objects.create(
            message_id='<standalone1@example.com>',
            sender='sender@example.com',
            recipient=project.canonical_email,
            subject='Subject 1',
            stripped_text='Content 1',
            status='queued',
        )
        service.process_email(email1.id)

        email2 = EmailMessage.objects.create(
            message_id='<standalone2@example.com>',
            sender='sender@example.com',
            recipient=project.canonical_email,
            subject='Subject 2',
            stripped_text='Content 2',
            status='queued',
        )
        service.process_email(email2.id)

        email1.refresh_from_db()
        email2.refresh_from_db()

        # Should be different threads
        assert email1.email_thread != email2.email_thread
        assert email1.email_thread.conversation != email2.email_thread.conversation

    def test_conversation_title_from_subject(
        self, service, organization, user, project
    ):
        """Test that conversation title is set from email subject."""
        email_msg = EmailMessage.objects.create(
            message_id='<subject-test@example.com>',
            sender='sender@example.com',
            recipient=project.canonical_email,
            subject='Important Discussion Topic',
            stripped_text='Content',
            status='queued',
        )
        service.process_email(email_msg.id)
        email_msg.refresh_from_db()

        conversation = email_msg.email_thread.conversation
        assert 'Email: Important Discussion Topic' in conversation.title

    def test_uses_stripped_text_over_body_plain(
        self, service, organization, user, project
    ):
        """Test that stripped_text is preferred over body_plain."""
        email_msg = EmailMessage.objects.create(
            message_id='<stripped-test@example.com>',
            sender='sender@example.com',
            recipient=project.canonical_email,
            subject='Test',
            stripped_text='Clean content without quotes',
            body_plain='Clean content without quotes\n\n> Quoted text\n> More quotes',
            status='queued',
        )
        service.process_email(email_msg.id)
        email_msg.refresh_from_db()

        assert email_msg.chat_message.content == 'Clean content without quotes'

    def test_process_email_converts_attachments_to_documents(
        self, service, organization, user, project
    ):
        """Attachments are converted to FileDocuments in a hidden folder."""
        email_msg = EmailMessage.objects.create(
            organization=None,
            message_id='<with-attachments@example.com>',
            sender='sender@example.com',
            recipient=project.canonical_email,
            subject='With attachments',
            stripped_text='Content',
            status='queued',
        )

        upload1 = SimpleUploadedFile("note.txt", b"hello", content_type="text/plain")
        upload2 = SimpleUploadedFile("image.png", b"\x89PNG\r\n", content_type="image/png")

        att1 = EmailAttachment.objects.create(
            email_message=email_msg,
            filename="note.txt",
            content_type="text/plain",
            size=upload1.size,
        )
        att1.file.save("note.txt", upload1, save=True)

        att2 = EmailAttachment.objects.create(
            email_message=email_msg,
            filename="image.png",
            content_type="image/png",
            size=upload2.size,
        )
        att2.file.save("image.png", upload2, save=True)

        result = service.process_email(email_msg.id)
        assert result is True

        email_msg.refresh_from_db()
        thread = email_msg.email_thread
        assert thread.attachment_folder is not None
        assert thread.attachment_folder.is_system is True
        assert thread.attachment_folder.project == project

        attachments = list(email_msg.stored_attachments.all())
        assert all(a.document_id for a in attachments)
        docs = FileDocument.objects.filter(folder=thread.attachment_folder)
        assert docs.count() == 2
        names = {d.name for d in docs}
        assert names == {"note.txt", "image.png"}
