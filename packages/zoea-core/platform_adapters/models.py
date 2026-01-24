"""
Models for platform adapter connections and unified messages.

This module defines:
- PlatformType: Enum of supported external platforms
- PlatformConnection: Configuration for connecting to external platforms
- ChannelMessage: Unified message format from any platform
"""

from __future__ import annotations

import secrets
import uuid
from typing import Any

from django.conf import settings
from django.db import models
from django.utils import timezone


class PlatformType(models.TextChoices):
    """Supported external platform types."""

    SLACK = "slack", "Slack"
    DISCORD = "discord", "Discord"
    EMAIL = "email", "Email"
    WEBHOOK = "webhook", "Generic Webhook"
    NOTION = "notion", "Notion"
    GITHUB = "github", "GitHub"
    LINEAR = "linear", "Linear"


class ConnectionStatus(models.TextChoices):
    """Status of a platform connection."""

    PENDING = "pending", "Pending Setup"
    ACTIVE = "active", "Active"
    ERROR = "error", "Error"
    DISABLED = "disabled", "Disabled"


def generate_webhook_secret() -> str:
    """Generate a secure webhook secret."""
    return secrets.token_urlsafe(32)


class PlatformConnection(models.Model):
    """
    Configuration for connecting to an external platform.

    Stores credentials, webhook secrets, and platform-specific settings
    for integrating with external services like Slack, Discord, or webhooks.

    Each connection belongs to an organization and optionally a project.
    Multiple connections of the same type are allowed (e.g., multiple Slack workspaces).
    """

    # Unique identifier for webhook URLs
    connection_id = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
        help_text="Unique ID used in webhook URLs",
    )

    # Organization relationship (required for multi-tenancy)
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="platform_connections",
    )

    # Optional project scope
    project = models.ForeignKey(
        "projects.Project",
        on_delete=models.CASCADE,
        related_name="platform_connections",
        null=True,
        blank=True,
        help_text="If set, messages are scoped to this project",
    )

    # Platform configuration
    platform_type = models.CharField(
        max_length=20,
        choices=PlatformType.choices,
        help_text="Type of external platform",
    )

    name = models.CharField(
        max_length=255,
        help_text="Human-readable name for this connection",
    )

    description = models.TextField(
        blank=True,
        help_text="Optional description of this connection's purpose",
    )

    # Connection status
    status = models.CharField(
        max_length=20,
        choices=ConnectionStatus.choices,
        default=ConnectionStatus.PENDING,
    )

    status_message = models.TextField(
        blank=True,
        help_text="Details about the current status (e.g., error message)",
    )

    # Authentication and configuration
    webhook_secret = models.CharField(
        max_length=64,
        default=generate_webhook_secret,
        help_text="Secret for validating incoming webhooks",
    )

    credentials = models.JSONField(
        default=dict,
        blank=True,
        help_text="Encrypted credentials (API keys, tokens, etc.)",
    )

    config = models.JSONField(
        default=dict,
        blank=True,
        help_text="Platform-specific configuration",
    )

    # Metadata
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="created_platform_connections",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Activity tracking
    last_message_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the last message was received",
    )

    message_count = models.PositiveIntegerField(
        default=0,
        help_text="Total messages received through this connection",
    )

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["organization", "platform_type"]),
            models.Index(fields=["connection_id"]),
            models.Index(fields=["status"]),
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.get_platform_type_display()})"

    def get_webhook_url(self) -> str:
        """Get the full webhook URL for this connection."""
        base_url = getattr(settings, "ZOEA_BASE_URL", "http://localhost:8000")
        return f"{base_url}/api/webhooks/{self.platform_type}/{self.connection_id}"

    def record_message(self) -> None:
        """Record that a message was received."""
        self.last_message_at = timezone.now()
        self.message_count = models.F("message_count") + 1
        self.save(update_fields=["last_message_at", "message_count"])

    def set_status(self, status: str, message: str = "") -> None:
        """Update the connection status."""
        self.status = status
        self.status_message = message
        self.save(update_fields=["status", "status_message", "updated_at"])


class MessageDirection(models.TextChoices):
    """Direction of a channel message."""

    INBOUND = "inbound", "Inbound (received)"
    OUTBOUND = "outbound", "Outbound (sent)"


class MessageStatus(models.TextChoices):
    """Processing status of a channel message."""

    RECEIVED = "received", "Received"
    PROCESSING = "processing", "Processing"
    PROCESSED = "processed", "Processed"
    FAILED = "failed", "Failed"
    IGNORED = "ignored", "Ignored"


class PlatformMessage(models.Model):
    """
    Unified message format from any external platform.

    Normalizes messages from Slack, Discord, Email, Webhooks, etc.
    into a common structure for processing by the event system.
    """

    # Unique identifier
    message_id = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
    )

    # Connection that received/sent this message
    connection = models.ForeignKey(
        PlatformConnection,
        on_delete=models.CASCADE,
        related_name="messages",
    )

    # Organization (denormalized for efficient queries)
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="platform_messages",
    )

    # Optional project scope
    project = models.ForeignKey(
        "projects.Project",
        on_delete=models.CASCADE,
        related_name="platform_messages",
        null=True,
        blank=True,
    )

    # Message direction and status
    direction = models.CharField(
        max_length=10,
        choices=MessageDirection.choices,
        default=MessageDirection.INBOUND,
    )

    status = models.CharField(
        max_length=20,
        choices=MessageStatus.choices,
        default=MessageStatus.RECEIVED,
    )

    status_message = models.TextField(
        blank=True,
        help_text="Processing status details or error message",
    )

    # Platform-specific identifiers
    external_id = models.CharField(
        max_length=255,
        blank=True,
        help_text="Platform's unique identifier for this message",
    )

    channel_id = models.CharField(
        max_length=255,
        blank=True,
        help_text="Platform channel/room/thread identifier",
    )

    thread_id = models.CharField(
        max_length=255,
        blank=True,
        help_text="Thread/conversation identifier if applicable",
    )

    # Sender information
    sender_id = models.CharField(
        max_length=255,
        blank=True,
        help_text="Platform's identifier for the sender",
    )

    sender_name = models.CharField(
        max_length=255,
        blank=True,
        help_text="Display name of the sender",
    )

    sender_email = models.EmailField(
        blank=True,
        help_text="Email address of the sender if available",
    )

    # Message content
    content = models.TextField(
        blank=True,
        help_text="Text content of the message",
    )

    content_type = models.CharField(
        max_length=50,
        default="text/plain",
        help_text="MIME type of the content",
    )

    # Attachments and metadata
    attachments = models.JSONField(
        default=list,
        blank=True,
        help_text="List of attachment metadata",
    )

    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional platform-specific metadata",
    )

    # Raw payload for debugging/replay
    raw_payload = models.JSONField(
        default=dict,
        blank=True,
        help_text="Original webhook payload",
    )

    # Timestamps
    platform_timestamp = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the message was created on the platform",
    )

    received_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When we received the message",
    )

    processed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When processing completed",
    )

    # Link to execution system
    execution_run = models.ForeignKey(
        "execution.ExecutionRun",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="platform_messages",
        help_text="ExecutionRun created for this message",
    )

    class Meta:
        ordering = ["-received_at"]
        indexes = [
            models.Index(fields=["connection", "-received_at"]),
            models.Index(fields=["organization", "-received_at"]),
            models.Index(fields=["status"]),
            models.Index(fields=["external_id"]),
            models.Index(fields=["channel_id"]),
        ]

    def __str__(self) -> str:
        sender = self.sender_name or self.sender_id or "Unknown"
        preview = (self.content[:50] + "...") if len(self.content) > 50 else self.content
        return f"{sender}: {preview}"

    def set_status(self, status: str, message: str = "") -> None:
        """Update the message processing status."""
        self.status = status
        self.status_message = message
        if status == MessageStatus.PROCESSED:
            self.processed_at = timezone.now()
        self.save(update_fields=["status", "status_message", "processed_at"])

    def to_trigger_envelope(self) -> dict[str, Any]:
        """
        Convert this message to a TriggerEnvelope for the event system.

        Returns:
            Dict matching the TriggerEnvelope TypedDict structure.
        """
        return {
            "trigger_type": "channel_message",
            "source": {
                "platform": self.connection.platform_type,
                "connection_id": str(self.connection.connection_id),
                "connection_name": self.connection.name,
            },
            "channel": {
                "channel_id": self.channel_id,
                "thread_id": self.thread_id,
            },
            "payload": {
                "message_id": str(self.message_id),
                "external_id": self.external_id,
                "sender_id": self.sender_id,
                "sender_name": self.sender_name,
                "sender_email": self.sender_email,
                "content": self.content,
                "content_type": self.content_type,
                "metadata": self.metadata,
            },
            "attachments": self.attachments,
            "organization_id": self.organization_id,
            "project_id": self.project_id,
        }
