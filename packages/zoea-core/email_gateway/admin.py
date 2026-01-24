"""
Django Admin configuration for email gateway models.
"""

from django.contrib import admin
from django.utils.html import format_html

from .models import EmailThread, EmailMessage, EmailAttachment


class EmailMessageInline(admin.TabularInline):
    """Inline display of emails within a thread."""

    model = EmailMessage
    extra = 0
    readonly_fields = [
        'message_id', 'sender', 'subject', 'status',
        'received_at', 'processed_at'
    ]
    fields = ['message_id', 'sender', 'subject', 'status', 'received_at']
    ordering = ['received_at']
    can_delete = False
    show_change_link = True


@admin.register(EmailThread)
class EmailThreadAdmin(admin.ModelAdmin):
    """Admin interface for email threads."""

    list_display = [
        'id', 'subject_truncated', 'initiator_email', 'status',
        'email_count', 'organization', 'last_email_at'
    ]
    list_filter = ['status', 'organization', 'created_at']
    search_fields = ['subject', 'initiator_email', 'thread_id']
    readonly_fields = [
        'thread_id', 'conversation', 'email_count',
        'first_email_at', 'last_email_at', 'created_at', 'updated_at'
    ]
    raw_id_fields = ['organization', 'project', 'initiator_user', 'attachment_folder']
    date_hierarchy = 'last_email_at'
    inlines = [EmailMessageInline]

    fieldsets = (
        ('Thread Info', {
            'fields': ('thread_id', 'subject', 'status')
        }),
        ('Initiator', {
            'fields': ('initiator_email', 'initiator_user', 'recipient_address')
        }),
        ('Organization', {
            'fields': ('organization', 'project')
        }),
        ('Linked Conversation', {
            'fields': ('conversation', 'attachment_folder')
        }),
        ('Statistics', {
            'fields': ('email_count', 'first_email_at', 'last_email_at')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def subject_truncated(self, obj):
        """Truncate subject for list display."""
        if len(obj.subject) > 50:
            return obj.subject[:50] + '...'
        return obj.subject
    subject_truncated.short_description = 'Subject'


@admin.register(EmailMessage)
class EmailMessageAdmin(admin.ModelAdmin):
    """Admin interface for individual email messages."""

    list_display = [
        'id', 'sender', 'subject_truncated', 'status',
        'organization', 'received_at', 'processed_at'
    ]
    list_filter = ['status', 'organization', 'received_at']
    search_fields = ['sender', 'recipient', 'subject', 'message_id']
    readonly_fields = [
        'message_id', 'in_reply_to', 'references',
        'mailgun_timestamp', 'mailgun_token', 'mailgun_signature',
        'received_at', 'processed_at'
    ]
    raw_id_fields = [
        'organization', 'email_thread', 'chat_message', 'sender_user'
    ]
    date_hierarchy = 'received_at'

    fieldsets = (
        ('Email Headers', {
            'fields': ('message_id', 'in_reply_to', 'references')
        }),
        ('Sender/Recipient', {
            'fields': ('sender', 'sender_user', 'recipient', 'subject')
        }),
        ('Content', {
            'fields': ('stripped_text', 'body_plain', 'body_html'),
            'classes': ('collapse',)
        }),
        ('Processing', {
            'fields': ('status', 'error_message', 'email_thread', 'chat_message')
        }),
        ('Organization', {
            'fields': ('organization',)
        }),
        ('Metadata', {
            'fields': ('attachments', 'headers', 'raw_post_data'),
            'classes': ('collapse',)
        }),
        ('Mailgun Verification', {
            'fields': ('mailgun_timestamp', 'mailgun_token', 'mailgun_signature'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('received_at', 'processed_at'),
            'classes': ('collapse',)
        }),
    )

    actions = ['retry_processing']

    def subject_truncated(self, obj):
        """Truncate subject for list display."""
        if len(obj.subject) > 50:
            return obj.subject[:50] + '...'
        return obj.subject
    subject_truncated.short_description = 'Subject'

    def retry_processing(self, request, queryset):
        """Admin action to retry processing failed emails."""
        from .tasks import process_email_message

        count = 0
        for email_msg in queryset.filter(status='failed'):
            email_msg.status = 'queued'
            email_msg.error_message = ''
            email_msg.save(update_fields=['status', 'error_message'])
            try:
                process_email_message(email_msg.id)
                count += 1
            except Exception:
                pass

        self.message_user(request, f"Retried processing for {count} emails.")
    retry_processing.short_description = "Retry processing selected failed emails"


@admin.register(EmailAttachment)
class EmailAttachmentAdmin(admin.ModelAdmin):
    """Admin interface for email attachments."""

    list_display = ['id', 'filename', 'email_message', 'document', 'size', 'content_type', 'created_at']
    search_fields = ['filename', 'content_type', 'email_message__message_id']
    list_filter = ['content_type', 'created_at']
    raw_id_fields = ['email_message', 'organization', 'document']
