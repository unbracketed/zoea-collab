from django.contrib import admin
from django.utils.html import format_html

from .models import Conversation, Message


class MessageInline(admin.TabularInline):
    """Inline admin for viewing messages within a conversation."""
    model = Message
    extra = 0
    fields = ['role', 'content_preview', 'created_at', 'token_count']
    readonly_fields = ['content_preview', 'created_at']
    can_delete = False

    def content_preview(self, obj):
        """Show preview of message content."""
        if len(obj.content) > 100:
            return obj.content[:100] + '...'
        return obj.content
    content_preview.short_description = "Content"


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    """Admin interface for managing conversations."""

    list_display = [
        'id',
        'title_display',
        'organization',
        'created_by',
        'agent_name',
        'message_count_display',
        'created_at',
        'updated_at'
    ]
    list_filter = ['agent_name', 'created_at', 'organization']
    search_fields = ['title', 'created_by__username', 'created_by__email', 'organization__name']
    readonly_fields = ['created_at', 'updated_at', 'message_count_display']
    date_hierarchy = 'created_at'

    fieldsets = [
        ('Conversation Info', {
            'fields': ['title', 'agent_name']
        }),
        ('Organization & User', {
            'fields': ['organization', 'created_by']
        }),
        ('Metadata', {
            'fields': ['message_count_display', 'created_at', 'updated_at'],
            'classes': ['collapse']
        }),
    ]

    inlines = [MessageInline]

    def title_display(self, obj):
        """Display conversation title with fallback."""
        return obj.get_title()
    title_display.short_description = "Title"

    def message_count_display(self, obj):
        """Display message count."""
        total = obj.message_count()
        user_msgs = obj.user_message_count()
        return format_html(
            '<strong>{}</strong> total ({} user, {} assistant)',
            total,
            user_msgs,
            total - user_msgs
        )
    message_count_display.short_description = "Messages"

    def get_queryset(self, request):
        """Optimize queryset with select_related."""
        qs = super().get_queryset(request)
        return qs.select_related('organization', 'created_by').prefetch_related('messages')


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    """Admin interface for viewing individual messages."""

    list_display = [
        'id',
        'conversation_link',
        'role',
        'content_preview',
        'created_at',
        'token_count'
    ]
    list_filter = ['role', 'created_at']
    search_fields = ['content', 'conversation__title']
    readonly_fields = ['created_at']
    date_hierarchy = 'created_at'

    fieldsets = [
        ('Message Info', {
            'fields': ['conversation', 'role', 'content']
        }),
        ('Metadata', {
            'fields': ['token_count', 'model_used', 'created_at'],
            'classes': ['collapse']
        }),
    ]

    def conversation_link(self, obj):
        """Link to parent conversation."""
        from django.urls import reverse
        from django.utils.html import format_html

        url = reverse('admin:chat_conversation_change', args=[obj.conversation.id])
        return format_html('<a href="{}">{}</a>', url, obj.conversation.get_title())
    conversation_link.short_description = "Conversation"

    def content_preview(self, obj):
        """Show preview of message content."""
        if len(obj.content) > 100:
            return obj.content[:100] + '...'
        return obj.content
    content_preview.short_description = "Content"

    def get_queryset(self, request):
        """Optimize queryset with select_related."""
        qs = super().get_queryset(request)
        return qs.select_related('conversation', 'conversation__organization')
