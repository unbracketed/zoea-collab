"""Unified channel models for external and internal messaging sources."""

from django.contrib.auth import get_user_model
from django.db import models

from accounts.managers import OrganizationScopedQuerySet

User = get_user_model()


class Channel(models.Model):
    """Represents a unified channel across platforms (Slack, Discord, Email, etc.)."""

    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="channels",
        help_text="Organization that owns this channel",
    )
    project = models.ForeignKey(
        "projects.Project",
        on_delete=models.CASCADE,
        related_name="channels",
        null=True,
        blank=True,
        help_text="Optional project scope for this channel",
    )

    adapter_type = models.CharField(
        max_length=50,
        help_text="Adapter/platform type (slack, discord, email, zoea_chat)",
    )
    external_id = models.CharField(
        max_length=255,
        help_text="Platform-specific channel identifier",
    )
    display_name = models.CharField(
        max_length=255,
        blank=True,
        help_text="Human-readable channel name",
    )
    metadata = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = OrganizationScopedQuerySet.as_manager()

    class Meta:
        verbose_name = "Channel"
        verbose_name_plural = "Channels"
        ordering = ["adapter_type", "display_name", "external_id"]
        indexes = [
            models.Index(fields=["organization", "adapter_type"]),
            models.Index(fields=["organization", "external_id"]),
        ]
        unique_together = [["organization", "adapter_type", "external_id"]]

    def __str__(self):
        label = self.display_name or self.external_id
        return f"{self.adapter_type}:{label}"


class ChannelMessage(models.Model):
    """Message within a unified channel."""

    ROLE_CHOICES = [
        ("user", "User"),
        ("assistant", "Assistant"),
        ("system", "System"),
    ]

    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="channel_messages",
        help_text="Organization that owns this message",
    )
    channel = models.ForeignKey(
        Channel,
        on_delete=models.CASCADE,
        related_name="messages",
        help_text="Channel this message belongs to",
    )
    external_id = models.CharField(
        max_length=255,
        blank=True,
        help_text="Platform-specific message identifier",
    )
    sender_id = models.CharField(
        max_length=255,
        blank=True,
        help_text="Platform-specific sender identifier",
    )
    sender_name = models.CharField(
        max_length=255,
        blank=True,
        help_text="Sender display name",
    )
    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        default="user",
        help_text="Message role",
    )
    content = models.TextField(help_text="Normalized message content")
    raw_content = models.TextField(blank=True, help_text="Raw platform content")
    attachments = models.JSONField(default=list, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    objects = OrganizationScopedQuerySet.as_manager()

    class Meta:
        verbose_name = "Channel Message"
        verbose_name_plural = "Channel Messages"
        ordering = ["created_at"]
        indexes = [
            models.Index(fields=["channel", "created_at"]),
            models.Index(fields=["sender_id", "created_at"]),
        ]

    def __str__(self):
        preview = self.content[:50] + ("..." if len(self.content) > 50 else "")
        return f"{self.role}: {preview}"

    def save(self, *args, **kwargs):
        if self.channel_id and not self.organization_id:
            self.organization_id = self.channel.organization_id
        super().save(*args, **kwargs)
