"""
Base class for platform adapters.

All platform-specific adapters inherit from BasePlatformAdapter and implement
the abstract methods for parsing inbound messages and sending outbound messages.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from django.http import HttpRequest

    from platform_adapters.models import PlatformMessage, PlatformConnection

logger = logging.getLogger(__name__)


@dataclass
class ParsedMessage:
    """
    Result of parsing an inbound webhook payload.

    Represents the normalized message data extracted from a platform-specific
    webhook payload before it's stored as a PlatformMessage.
    """

    # Platform identifiers
    external_id: str = ""
    channel_id: str = ""
    thread_id: str = ""

    # Sender info
    sender_id: str = ""
    sender_name: str = ""
    sender_email: str = ""

    # Content
    content: str = ""
    content_type: str = "text/plain"

    # Attachments (list of dicts with url, filename, content_type, size)
    attachments: list[dict[str, Any]] = field(default_factory=list)

    # Additional metadata
    metadata: dict[str, Any] = field(default_factory=dict)

    # Original timestamp from platform
    platform_timestamp: str | None = None

    # Should this message be processed or ignored?
    should_process: bool = True
    ignore_reason: str = ""


@dataclass
class WebhookValidationResult:
    """Result of validating an incoming webhook request."""

    is_valid: bool
    error_message: str = ""
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass
class SendMessageResult:
    """Result of sending an outbound message."""

    success: bool
    external_id: str = ""
    error_message: str = ""
    response_data: dict[str, Any] = field(default_factory=dict)


class BasePlatformAdapter(ABC):
    """
    Abstract base class for platform adapters.

    Each platform (Slack, Discord, Email, Webhook, etc.) implements this
    interface to handle:
    - Validating incoming webhook requests
    - Parsing inbound messages into a normalized format
    - Sending outbound messages to the platform

    Usage:
        adapter = SlackAdapter(connection)
        validation = adapter.validate_webhook(request)
        if validation.is_valid:
            parsed = adapter.parse_inbound(validation.payload)
            if parsed.should_process:
                # Create PlatformMessage and process
    """

    def __init__(self, connection: PlatformConnection):
        """
        Initialize the adapter with a platform connection.

        Args:
            connection: The PlatformConnection configuration for this adapter.
        """
        self.connection = connection

    @property
    def platform_type(self) -> str:
        """Return the platform type this adapter handles."""
        return self.connection.platform_type

    @abstractmethod
    def validate_webhook(self, request: HttpRequest) -> WebhookValidationResult:
        """
        Validate an incoming webhook request.

        Verifies the request signature/authentication and extracts the payload.

        Args:
            request: The incoming Django HttpRequest.

        Returns:
            WebhookValidationResult with validation status and payload.
        """
        pass

    @abstractmethod
    def parse_inbound(self, payload: dict[str, Any]) -> ParsedMessage:
        """
        Parse an inbound webhook payload into a normalized message.

        Args:
            payload: The validated webhook payload (JSON).

        Returns:
            ParsedMessage with normalized message data.
        """
        pass

    @abstractmethod
    def send_message(
        self,
        channel_id: str,
        content: str,
        *,
        thread_id: str | None = None,
        attachments: list[dict[str, Any]] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> SendMessageResult:
        """
        Send a message to the platform.

        Args:
            channel_id: The channel/room/thread to send to.
            content: The message content.
            thread_id: Optional thread to reply to.
            attachments: Optional list of attachments.
            metadata: Optional platform-specific metadata.

        Returns:
            SendMessageResult with send status.
        """
        pass

    def get_config(self, key: str, default: Any = None) -> Any:
        """Get a configuration value from the connection config."""
        return self.connection.config.get(key, default)

    def get_credential(self, key: str, default: Any = None) -> Any:
        """Get a credential value from the connection credentials."""
        return self.connection.credentials.get(key, default)

    def create_channel_message(
        self,
        parsed: ParsedMessage,
        raw_payload: dict[str, Any],
    ) -> PlatformMessage:
        """
        Create a PlatformMessage from a parsed message.

        Args:
            parsed: The parsed message data.
            raw_payload: The original webhook payload for debugging.

        Returns:
            Unsaved PlatformMessage instance.
        """
        from platform_adapters.models import PlatformMessage, MessageStatus

        return PlatformMessage(
            connection=self.connection,
            organization=self.connection.organization,
            project=self.connection.project,
            external_id=parsed.external_id,
            channel_id=parsed.channel_id,
            thread_id=parsed.thread_id,
            sender_id=parsed.sender_id,
            sender_name=parsed.sender_name,
            sender_email=parsed.sender_email,
            content=parsed.content,
            content_type=parsed.content_type,
            attachments=parsed.attachments,
            metadata=parsed.metadata,
            raw_payload=raw_payload,
            status=MessageStatus.RECEIVED if parsed.should_process else MessageStatus.IGNORED,
            status_message="" if parsed.should_process else parsed.ignore_reason,
        )
