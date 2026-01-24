"""
Database models for email gateway - storing inbound emails and linking to conversations.
"""

from django.db import models
from django.contrib.auth import get_user_model

from accounts.managers import OrganizationScopedQuerySet

User = get_user_model()


class EmailThread(models.Model):
    """
    Links email threads to Conversations with email-specific metadata.

    Email threads are identified by RFC 2822 threading (Message-ID, In-Reply-To, References).
    Each thread creates a corresponding Conversation for viewing in the chat interface.
    """

    STATUS_CHOICES = [
        ('active', 'Active'),
        ('closed', 'Closed'),
        ('archived', 'Archived'),
    ]

    organization = models.ForeignKey(
        'organizations.Organization',
        on_delete=models.CASCADE,
        related_name='email_threads',
        help_text="Organization this email thread belongs to"
    )
    project = models.ForeignKey(
        'projects.Project',
        on_delete=models.CASCADE,
        related_name='email_threads',
        null=True,
        blank=True,
        help_text="Project this email thread belongs to"
    )
    conversation = models.OneToOneField(
        'chat.Conversation',
        on_delete=models.CASCADE,
        related_name='email_thread',
        help_text="Linked chat conversation"
    )

    # RFC 2822 threading
    thread_id = models.CharField(
        max_length=512,
        unique=True,
        db_index=True,
        help_text="RFC 2822 thread identifier (usually first Message-ID)"
    )

    # Email metadata
    subject = models.CharField(
        max_length=998,  # RFC 5322 line limit
        help_text="Email subject line"
    )
    initiator_email = models.EmailField(
        help_text="Email address that started this thread"
    )
    initiator_user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='initiated_email_threads',
        help_text="User account matched to initiator email"
    )
    recipient_address = models.EmailField(
        help_text="Inbound email address (e.g., inbox@mail.zoea.studio)"
    )
    attachment_folder = models.ForeignKey(
        'documents.Folder',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='email_threads',
        help_text="DEPRECATED: Use attachments collection instead. Folder holding attachments for this thread"
    )
    attachments = models.ForeignKey(
        'documents.DocumentCollection',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='email_threads',
        help_text="Collection of attachments for this email thread"
    )

    # Status and timestamps
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='active',
        help_text="Thread status"
    )
    email_count = models.PositiveIntegerField(
        default=0,
        help_text="Cached count of emails in this thread"
    )
    first_email_at = models.DateTimeField(
        help_text="Timestamp of first email in thread"
    )
    last_email_at = models.DateTimeField(
        help_text="Timestamp of most recent email in thread"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = OrganizationScopedQuerySet.as_manager()

    class Meta:
        ordering = ['-last_email_at']
        indexes = [
            models.Index(fields=['-last_email_at']),
            models.Index(fields=['organization', '-last_email_at']),
            models.Index(fields=['status', '-last_email_at']),
            models.Index(fields=['initiator_email']),
        ]

    def __str__(self):
        return f"{self.subject} ({self.email_count} emails)"

    def get_or_create_attachments(self, created_by=None):
        """
        Get or lazily create the attachments collection for this email thread.

        Creates a DocumentCollection with collection_type='attachment' if one
        doesn't exist. The collection is scoped to the thread's organization
        and project.

        Args:
            created_by: User to attribute the collection creation to (optional)

        Returns:
            DocumentCollection: The attachments collection for this thread.
        """
        if self.attachments_id:
            return self.attachments

        from documents.models import DocumentCollection, CollectionType

        collection = DocumentCollection.objects.create(
            organization=self.organization,
            project=self.project,
            collection_type=CollectionType.ATTACHMENT,
            name=f"Email Attachments: {self.subject[:50]}",
            created_by=created_by or self.initiator_user,
        )
        self.attachments = collection
        self.save(update_fields=['attachments'])
        return collection


class EmailMessage(models.Model):
    """
    Stores individual emails with full Mailgun data.

    Each email is linked to an EmailThread and creates a corresponding Message
    in the chat Conversation.
    """

    STATUS_CHOICES = [
        ('received', 'Received'),
        ('queued', 'Queued'),
        ('processing', 'Processing'),
        ('processed', 'Processed'),
        ('failed', 'Failed'),
    ]

    organization = models.ForeignKey(
        'organizations.Organization',
        on_delete=models.CASCADE,
        related_name='email_messages',
        null=True,
        blank=True,
        help_text="Organization this email belongs to (set during processing)"
    )
    email_thread = models.ForeignKey(
        EmailThread,
        on_delete=models.CASCADE,
        related_name='emails',
        null=True,
        blank=True,
        help_text="Parent email thread (set during processing)"
    )
    chat_message = models.OneToOneField(
        'chat.Message',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='email_message',
        help_text="Created chat message"
    )

    # RFC 2822 identifiers for threading
    message_id = models.CharField(
        max_length=512,
        unique=True,
        db_index=True,
        help_text="RFC 2822 Message-ID header"
    )
    in_reply_to = models.CharField(
        max_length=512,
        blank=True,
        help_text="RFC 2822 In-Reply-To header"
    )
    references = models.TextField(
        blank=True,
        help_text="RFC 2822 References header (space-separated Message-IDs)"
    )

    # Sender/recipient
    sender = models.EmailField(
        help_text="From email address"
    )
    sender_user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='sent_emails',
        help_text="User account matched to sender"
    )
    recipient = models.EmailField(
        help_text="To email address"
    )
    subject = models.CharField(
        max_length=998,
        help_text="Email subject"
    )

    # Email content
    stripped_text = models.TextField(
        blank=True,
        help_text="Mailgun stripped-text (quoted parts removed)"
    )
    body_plain = models.TextField(
        blank=True,
        help_text="Full plain text body"
    )
    body_html = models.TextField(
        blank=True,
        help_text="Full HTML body"
    )

    # Metadata
    attachments = models.JSONField(
        default=list,
        blank=True,
        help_text="Attachment metadata from Mailgun"
    )
    headers = models.JSONField(
        default=dict,
        blank=True,
        help_text="All email headers"
    )
    raw_post_data = models.JSONField(
        default=dict,
        blank=True,
        help_text="Complete Mailgun POST data"
    )

    # Mailgun signature verification
    mailgun_timestamp = models.CharField(
        max_length=50,
        blank=True,
        help_text="Mailgun timestamp for signature verification"
    )
    mailgun_token = models.CharField(
        max_length=100,
        blank=True,
        help_text="Mailgun token for signature verification"
    )
    mailgun_signature = models.CharField(
        max_length=256,
        blank=True,
        help_text="Mailgun HMAC signature"
    )

    # Processing status
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='received',
        help_text="Processing status"
    )
    error_message = models.TextField(
        blank=True,
        help_text="Error message if processing failed"
    )

    # Timestamps
    received_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When the webhook was received"
    )
    processed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When processing completed"
    )

    objects = OrganizationScopedQuerySet.as_manager()

    class Meta:
        ordering = ['received_at']
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['organization', 'status']),
            models.Index(fields=['sender']),
            models.Index(fields=['received_at']),
        ]

    def __str__(self):
        return f"From {self.sender}: {self.subject[:50]}"


class EmailAttachment(models.Model):
    """
    Stored attachment file for an inbound email message.

    Attachments are persisted immediately on webhook receipt so they remain
    available for later processing even if background tasks fail.
    """

    organization = models.ForeignKey(
        'organizations.Organization',
        on_delete=models.CASCADE,
        related_name='email_attachments',
        null=True,
        blank=True,
        help_text="Organization this attachment belongs to (set during processing)"
    )
    email_message = models.ForeignKey(
        EmailMessage,
        on_delete=models.CASCADE,
        related_name='stored_attachments',
        help_text="Parent email message"
    )
    file = models.FileField(
        upload_to='email_attachments/%Y/%m/%d/',
        help_text="Uploaded attachment file"
    )
    filename = models.CharField(
        max_length=1024,
        help_text="Original filename"
    )
    content_type = models.CharField(
        max_length=255,
        blank=True,
        help_text="MIME type reported by Mailgun"
    )
    size = models.BigIntegerField(
        default=0,
        help_text="Attachment size in bytes"
    )
    content_id = models.CharField(
        max_length=255,
        blank=True,
        help_text="Content-ID from email headers (for inline attachments)"
    )
    document = models.ForeignKey(
        'documents.Document',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='email_attachments',
        help_text="Document created from this attachment (if any)"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    objects = OrganizationScopedQuerySet.as_manager()

    class Meta:
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['organization']),
            models.Index(fields=['email_message']),
        ]

    def __str__(self):
        return self.filename
