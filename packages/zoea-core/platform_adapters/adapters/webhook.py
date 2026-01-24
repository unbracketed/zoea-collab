"""
Generic webhook adapter for n8n, Zapier, and custom integrations.

This adapter handles arbitrary webhook payloads with flexible field mapping,
making it suitable for:
- n8n workflow automations
- Zapier integrations
- Custom webhook integrations
- Any HTTP POST-based integration
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
from typing import TYPE_CHECKING, Any

from .base import (
    BasePlatformAdapter,
    ParsedMessage,
    SendMessageResult,
    WebhookValidationResult,
)

if TYPE_CHECKING:
    from django.http import HttpRequest

logger = logging.getLogger(__name__)


class GenericWebhookAdapter(BasePlatformAdapter):
    """
    Adapter for generic webhook integrations.

    Supports flexible field mapping to extract message data from arbitrary
    JSON payloads. Configuration options:

    connection.config:
        field_mappings: Dict mapping normalized fields to payload paths
            - content: "message" or "data.text" (dot notation for nested)
            - sender_id: "user.id"
            - sender_name: "user.name"
            - channel_id: "channel"
            - external_id: "id"
            - attachments: "files"
        signature_header: Header name for HMAC signature (default: X-Webhook-Signature)
        signature_algorithm: HMAC algorithm (default: sha256)
        require_signature: Whether to require signature validation (default: True)
        content_field: Shortcut for simple content extraction (default: "content")
    """

    DEFAULT_FIELD_MAPPINGS = {
        "content": "content",
        "sender_id": "sender_id",
        "sender_name": "sender_name",
        "sender_email": "sender_email",
        "channel_id": "channel_id",
        "thread_id": "thread_id",
        "external_id": "id",
        "attachments": "attachments",
    }

    def validate_webhook(self, request: HttpRequest) -> WebhookValidationResult:
        """
        Validate an incoming webhook request.

        Checks HMAC signature if configured, then parses the JSON payload.
        """
        require_signature = self.get_config("require_signature", True)
        signature_header = self.get_config("signature_header", "X-Webhook-Signature")
        signature_algorithm = self.get_config("signature_algorithm", "sha256")

        # Get the raw body for signature verification
        try:
            body = request.body
        except Exception as e:
            logger.warning(f"Failed to read request body: {e}")
            return WebhookValidationResult(
                is_valid=False,
                error_message="Failed to read request body",
            )

        # Verify signature if required
        if require_signature:
            signature = request.headers.get(signature_header)
            if not signature:
                logger.warning(f"Missing signature header: {signature_header}")
                return WebhookValidationResult(
                    is_valid=False,
                    error_message=f"Missing {signature_header} header",
                )

            if not self._verify_signature(body, signature, signature_algorithm):
                logger.warning("Invalid webhook signature")
                return WebhookValidationResult(
                    is_valid=False,
                    error_message="Invalid webhook signature",
                )

        # Parse JSON payload
        try:
            payload = json.loads(body)
        except json.JSONDecodeError as e:
            logger.warning(f"Invalid JSON payload: {e}")
            return WebhookValidationResult(
                is_valid=False,
                error_message="Invalid JSON payload",
            )

        return WebhookValidationResult(
            is_valid=True,
            payload=payload,
        )

    def parse_inbound(self, payload: dict[str, Any]) -> ParsedMessage:
        """
        Parse a webhook payload into a normalized message.

        Uses field mappings from config to extract data from arbitrary payloads.
        """
        field_mappings = self.get_config("field_mappings", self.DEFAULT_FIELD_MAPPINGS)

        # Extract fields using dot notation
        content = self._extract_field(payload, field_mappings.get("content", "content"))
        sender_id = self._extract_field(payload, field_mappings.get("sender_id", "sender_id"))
        sender_name = self._extract_field(payload, field_mappings.get("sender_name", "sender_name"))
        sender_email = self._extract_field(payload, field_mappings.get("sender_email", "sender_email"))
        channel_id = self._extract_field(payload, field_mappings.get("channel_id", "channel_id"))
        thread_id = self._extract_field(payload, field_mappings.get("thread_id", "thread_id"))
        external_id = self._extract_field(payload, field_mappings.get("external_id", "id"))
        attachments = self._extract_field(payload, field_mappings.get("attachments", "attachments"))

        # Ensure content is a string
        if content is None:
            content = ""
        elif not isinstance(content, str):
            content = str(content)

        # Ensure attachments is a list
        if attachments is None:
            attachments = []
        elif not isinstance(attachments, list):
            attachments = [attachments]

        # Normalize attachment format
        normalized_attachments = []
        for att in attachments:
            if isinstance(att, dict):
                normalized_attachments.append({
                    "url": att.get("url", ""),
                    "filename": att.get("filename", att.get("name", "")),
                    "content_type": att.get("content_type", att.get("type", "")),
                    "size": att.get("size", 0),
                })
            elif isinstance(att, str):
                # Assume it's a URL
                normalized_attachments.append({"url": att, "filename": "", "content_type": "", "size": 0})

        # Determine if message should be processed
        should_process = True
        ignore_reason = ""

        # Check for empty content (unless attachments present)
        if not content and not normalized_attachments:
            should_process = False
            ignore_reason = "Empty message with no attachments"

        # Check for ignore patterns
        ignore_patterns = self.get_config("ignore_patterns", [])
        for pattern in ignore_patterns:
            if pattern in content:
                should_process = False
                ignore_reason = f"Matched ignore pattern: {pattern}"
                break

        return ParsedMessage(
            external_id=str(external_id) if external_id else "",
            channel_id=str(channel_id) if channel_id else "",
            thread_id=str(thread_id) if thread_id else "",
            sender_id=str(sender_id) if sender_id else "",
            sender_name=str(sender_name) if sender_name else "",
            sender_email=str(sender_email) if sender_email else "",
            content=content,
            content_type="text/plain",
            attachments=normalized_attachments,
            metadata={"raw_payload_keys": list(payload.keys())},
            should_process=should_process,
            ignore_reason=ignore_reason,
        )

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
        Send a message via webhook callback.

        Generic webhooks typically don't support outbound messaging,
        but this can be configured via a callback URL.
        """
        callback_url = self.get_config("callback_url")
        if not callback_url:
            return SendMessageResult(
                success=False,
                error_message="No callback URL configured for outbound messages",
            )

        import requests

        try:
            response = requests.post(
                callback_url,
                json={
                    "channel_id": channel_id,
                    "thread_id": thread_id,
                    "content": content,
                    "attachments": attachments or [],
                    "metadata": metadata or {},
                },
                headers={
                    "Content-Type": "application/json",
                    "X-Webhook-Secret": self.connection.webhook_secret,
                },
                timeout=30,
            )
            response.raise_for_status()

            return SendMessageResult(
                success=True,
                response_data=response.json() if response.content else {},
            )

        except requests.RequestException as e:
            logger.error(f"Failed to send webhook callback: {e}")
            return SendMessageResult(
                success=False,
                error_message=str(e),
            )

    def _verify_signature(self, body: bytes, signature: str, algorithm: str) -> bool:
        """Verify HMAC signature of the request body."""
        secret = self.connection.webhook_secret.encode()

        if algorithm == "sha256":
            expected = hmac.new(secret, body, hashlib.sha256).hexdigest()
        elif algorithm == "sha1":
            expected = hmac.new(secret, body, hashlib.sha1).hexdigest()
        else:
            logger.warning(f"Unsupported signature algorithm: {algorithm}")
            return False

        # Support both raw hex and prefixed formats (e.g., "sha256=...")
        if "=" in signature:
            signature = signature.split("=", 1)[1]

        return hmac.compare_digest(expected.lower(), signature.lower())

    def _extract_field(self, payload: dict[str, Any], path: str) -> Any:
        """
        Extract a field from payload using dot notation.

        Args:
            payload: The JSON payload dict.
            path: Dot-separated path (e.g., "data.user.name").

        Returns:
            The extracted value, or None if not found.
        """
        if not path:
            return None

        parts = path.split(".")
        value = payload

        for part in parts:
            if isinstance(value, dict):
                value = value.get(part)
            elif isinstance(value, list) and part.isdigit():
                idx = int(part)
                value = value[idx] if 0 <= idx < len(value) else None
            else:
                return None

            if value is None:
                return None

        return value
