"""
Database models for chat conversations and messages.

These models provide persistent storage for chat interactions,
enabling conversation history, analytics, and audit trails.
"""

from django.db import models
from django.contrib.auth import get_user_model
from django.db.models.signals import post_save
from django.dispatch import receiver

from accounts.managers import OrganizationScopedQuerySet

User = get_user_model()


class Conversation(models.Model):
    """
    A conversation thread between a user and an agent.

    Each conversation belongs to an organization and project.
    Conversations contain multiple messages exchanged between the user and the AI agent.
    """

    organization = models.ForeignKey(
        'organizations.Organization',
        on_delete=models.CASCADE,
        related_name='conversations',
        help_text="Organization this conversation belongs to"
    )
    project = models.ForeignKey(
        'projects.Project',
        on_delete=models.CASCADE,
        related_name='conversations',
        null=True,
        blank=True,
        help_text="Project this conversation belongs to"
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='conversations',
        help_text="User who started this conversation"
    )
    agent_name = models.CharField(
        max_length=100,
        default='ZoeaAssistant',
        help_text="Name of the AI agent used in this conversation"
    )
    title = models.CharField(
        max_length=200,
        blank=True,
        help_text="Optional title for the conversation (auto-generated if empty)"
    )
    artifacts = models.ForeignKey(
        'documents.DocumentCollection',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='conversations',
        help_text="Collection of artifacts (code blocks, files, etc.) from this conversation"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Use organization-scoped queryset for multi-tenant filtering
    objects = OrganizationScopedQuerySet.as_manager()

    class Meta:
        ordering = ['-updated_at']
        indexes = [
            models.Index(fields=['-updated_at']),
            models.Index(fields=['organization', '-updated_at']),
            models.Index(fields=['project', '-updated_at']),
            models.Index(fields=['created_by', '-updated_at']),
        ]

    def __str__(self):
        if self.title:
            return f"{self.title} - {self.created_by.username}"
        return f"Conversation {self.id} - {self.created_by.username}"

    def get_title(self):
        """
        Get conversation title, auto-generating from first message if not set.

        Returns:
            str: Conversation title
        """
        if self.title:
            return self.title

        # Generate title from first user message
        first_message = self.messages.filter(role='user').first()
        if first_message:
            # Take first 50 chars of message as title
            return first_message.content[:50] + ('...' if len(first_message.content) > 50 else '')

        return f"Conversation {self.id}"

    def message_count(self):
        """Get total number of messages in this conversation."""
        return self.messages.count()

    def user_message_count(self):
        """Get number of user messages in this conversation."""
        return self.messages.filter(role='user').count()

    def get_or_create_artifacts(self):
        """
        Get or lazily create the artifacts collection for this conversation.

        Creates a DocumentCollection with collection_type='artifact' if one
        doesn't exist. The collection is scoped to the conversation's
        organization and project.

        Returns:
            DocumentCollection: The artifacts collection for this conversation.
        """
        if self.artifacts_id:
            return self.artifacts

        from documents.models import DocumentCollection, CollectionType

        collection = DocumentCollection.objects.create(
            organization=self.organization,
            project=self.project,
            collection_type=CollectionType.ARTIFACT,
            name=f"Artifacts: {self.get_title()[:50]}",
            created_by=self.created_by,
        )
        self.artifacts = collection
        self.save(update_fields=['artifacts'])
        return collection


class Message(models.Model):
    """
    A single message in a conversation.

    Messages can be from the user, assistant, or system. Each message
    is timestamped and optionally tracks token usage for cost analysis.
    """

    ROLE_CHOICES = [
        ('user', 'User'),
        ('assistant', 'Assistant'),
        ('system', 'System'),
    ]

    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name='messages',
        help_text="Conversation this message belongs to"
    )
    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        help_text="Who sent this message"
    )
    content = models.TextField(
        help_text="The message content"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    # Optional metadata for analytics
    token_count = models.IntegerField(
        null=True,
        blank=True,
        help_text="Number of tokens in this message (for cost tracking)"
    )
    model_used = models.CharField(
        max_length=100,
        blank=True,
        help_text="AI model used to generate this message (for assistant messages)"
    )

    class Meta:
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['conversation', 'created_at']),
            models.Index(fields=['role', 'created_at']),
        ]

    def __str__(self):
        preview = self.content[:50] + ('...' if len(self.content) > 50 else '')
        return f"{self.get_role_display()}: {preview}"

    def is_user_message(self):
        """Check if this message is from a user."""
        return self.role == 'user'

    def is_assistant_message(self):
        """Check if this message is from an assistant."""
        return self.role == 'assistant'


@receiver(post_save, sender=Message)
def update_conversation_timestamp(sender, instance, created, **kwargs):
    """
    Update the conversation's updated_at timestamp when a message is created.

    This ensures that conversations are properly sorted by most recent activity.
    """
    if created:
        # Touch the conversation to update its updated_at timestamp
        instance.conversation.save(update_fields=['updated_at'])
