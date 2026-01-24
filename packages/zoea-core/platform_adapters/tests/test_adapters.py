"""Tests for platform adapters."""

import hashlib
import hmac
import json
from unittest.mock import MagicMock, patch

import pytest
from django.contrib.auth import get_user_model
from django.test import RequestFactory

from accounts.models import Account
from platform_adapters.adapters.webhook import GenericWebhookAdapter
from platform_adapters.models import (
    ConnectionStatus,
    PlatformConnection,
    PlatformType,
)
from projects.models import Project

User = get_user_model()


@pytest.fixture
def organization(db):
    """Create a test organization."""
    return Account.objects.create(name="Test Organization", slug="test-org")


@pytest.fixture
def user(db, organization):
    """Create a test user."""
    return User.objects.create_user(
        username="testuser",
        email="testuser@example.com",
        password="testpass123",
    )


@pytest.fixture
def project(db, organization, user):
    """Create a test project."""
    return Project.objects.create(
        organization=organization,
        name="Test Project",
        working_directory="/tmp/test-project",
        created_by=user,
    )


@pytest.fixture
def webhook_connection(db, organization, project, user):
    """Create a webhook connection for testing."""
    return PlatformConnection.objects.create(
        organization=organization,
        project=project,
        platform_type=PlatformType.WEBHOOK,
        name="Test Webhook",
        status=ConnectionStatus.ACTIVE,
        webhook_secret="test-secret-key-12345",
        config={
            "require_signature": True,
            "signature_header": "X-Webhook-Signature",
            "signature_algorithm": "sha256",
        },
        created_by=user,
    )


@pytest.fixture
def request_factory():
    """Django request factory."""
    return RequestFactory()


class TestGenericWebhookAdapter:
    """Tests for GenericWebhookAdapter."""

    def test_validate_webhook_valid_signature(self, webhook_connection, request_factory):
        """Test validating webhook with valid signature."""
        adapter = GenericWebhookAdapter(webhook_connection)

        payload = {"content": "Hello", "sender_name": "Alice"}
        body = json.dumps(payload).encode()

        # Generate valid signature
        signature = hmac.new(
            webhook_connection.webhook_secret.encode(),
            body,
            hashlib.sha256,
        ).hexdigest()

        request = request_factory.post(
            "/api/webhooks/webhook/test",
            data=body,
            content_type="application/json",
            HTTP_X_WEBHOOK_SIGNATURE=signature,
        )

        result = adapter.validate_webhook(request)

        assert result.is_valid
        assert result.payload == payload

    def test_validate_webhook_invalid_signature(self, webhook_connection, request_factory):
        """Test validating webhook with invalid signature."""
        adapter = GenericWebhookAdapter(webhook_connection)

        payload = {"content": "Hello"}
        body = json.dumps(payload).encode()

        request = request_factory.post(
            "/api/webhooks/webhook/test",
            data=body,
            content_type="application/json",
            HTTP_X_WEBHOOK_SIGNATURE="invalid-signature",
        )

        result = adapter.validate_webhook(request)

        assert not result.is_valid
        assert "Invalid" in result.error_message

    def test_validate_webhook_missing_signature(self, webhook_connection, request_factory):
        """Test validating webhook with missing signature header."""
        adapter = GenericWebhookAdapter(webhook_connection)

        payload = {"content": "Hello"}
        body = json.dumps(payload).encode()

        request = request_factory.post(
            "/api/webhooks/webhook/test",
            data=body,
            content_type="application/json",
        )

        result = adapter.validate_webhook(request)

        assert not result.is_valid
        assert "Missing" in result.error_message

    def test_validate_webhook_no_signature_required(self, webhook_connection, request_factory):
        """Test validating webhook when signature not required."""
        webhook_connection.config["require_signature"] = False
        webhook_connection.save()

        adapter = GenericWebhookAdapter(webhook_connection)

        payload = {"content": "Hello"}
        body = json.dumps(payload).encode()

        request = request_factory.post(
            "/api/webhooks/webhook/test",
            data=body,
            content_type="application/json",
        )

        result = adapter.validate_webhook(request)

        assert result.is_valid
        assert result.payload == payload

    def test_validate_webhook_invalid_json(self, webhook_connection, request_factory):
        """Test validating webhook with invalid JSON."""
        webhook_connection.config["require_signature"] = False
        webhook_connection.save()

        adapter = GenericWebhookAdapter(webhook_connection)

        request = request_factory.post(
            "/api/webhooks/webhook/test",
            data=b"not valid json",
            content_type="application/json",
        )

        result = adapter.validate_webhook(request)

        assert not result.is_valid
        assert "Invalid JSON" in result.error_message

    def test_parse_inbound_simple_payload(self, webhook_connection):
        """Test parsing a simple inbound payload."""
        adapter = GenericWebhookAdapter(webhook_connection)

        payload = {
            "content": "Hello, world!",
            "sender_id": "user-123",
            "sender_name": "Alice",
            "channel_id": "channel-1",
        }

        result = adapter.parse_inbound(payload)

        assert result.content == "Hello, world!"
        assert result.sender_id == "user-123"
        assert result.sender_name == "Alice"
        assert result.channel_id == "channel-1"
        assert result.should_process is True

    def test_parse_inbound_nested_fields(self, webhook_connection):
        """Test parsing payload with nested fields using dot notation."""
        webhook_connection.config["field_mappings"] = {
            "content": "message.text",
            "sender_id": "user.id",
            "sender_name": "user.profile.name",
            "channel_id": "room.id",
        }
        webhook_connection.save()

        adapter = GenericWebhookAdapter(webhook_connection)

        payload = {
            "message": {"text": "Nested content"},
            "user": {
                "id": "u-456",
                "profile": {"name": "Bob"},
            },
            "room": {"id": "room-789"},
        }

        result = adapter.parse_inbound(payload)

        assert result.content == "Nested content"
        assert result.sender_id == "u-456"
        assert result.sender_name == "Bob"
        assert result.channel_id == "room-789"

    def test_parse_inbound_empty_content_ignored(self, webhook_connection):
        """Test that empty messages are marked as should not process."""
        adapter = GenericWebhookAdapter(webhook_connection)

        payload = {
            "content": "",
            "sender_id": "user-123",
        }

        result = adapter.parse_inbound(payload)

        assert result.should_process is False
        assert "Empty" in result.ignore_reason

    def test_parse_inbound_with_attachments(self, webhook_connection):
        """Test parsing payload with attachments."""
        adapter = GenericWebhookAdapter(webhook_connection)

        payload = {
            "content": "Check this file",
            "attachments": [
                {"url": "https://example.com/file.pdf", "name": "doc.pdf", "size": 1024},
                {"url": "https://example.com/image.png", "filename": "pic.png"},
            ],
        }

        result = adapter.parse_inbound(payload)

        assert len(result.attachments) == 2
        assert result.attachments[0]["url"] == "https://example.com/file.pdf"
        assert result.attachments[0]["filename"] == "doc.pdf"
        assert result.attachments[1]["filename"] == "pic.png"

    def test_parse_inbound_string_attachment(self, webhook_connection):
        """Test parsing payload where attachments are just URLs."""
        adapter = GenericWebhookAdapter(webhook_connection)

        payload = {
            "content": "Files attached",
            "attachments": ["https://example.com/file1.pdf", "https://example.com/file2.png"],
        }

        result = adapter.parse_inbound(payload)

        assert len(result.attachments) == 2
        assert result.attachments[0]["url"] == "https://example.com/file1.pdf"

    def test_parse_inbound_ignore_patterns(self, webhook_connection):
        """Test that messages matching ignore patterns are ignored."""
        webhook_connection.config["ignore_patterns"] = ["[AUTOMATED]", "[BOT]"]
        webhook_connection.save()

        adapter = GenericWebhookAdapter(webhook_connection)

        payload = {
            "content": "[AUTOMATED] This is an automated message",
            "sender_id": "bot",
        }

        result = adapter.parse_inbound(payload)

        assert result.should_process is False
        assert "[AUTOMATED]" in result.ignore_reason

    def test_create_channel_message(self, webhook_connection):
        """Test creating a ChannelMessage from parsed data."""
        adapter = GenericWebhookAdapter(webhook_connection)

        payload = {
            "content": "Test message",
            "sender_name": "Alice",
            "id": "ext-123",
        }

        parsed = adapter.parse_inbound(payload)
        raw_payload = payload

        message = adapter.create_channel_message(parsed, raw_payload)

        assert message.connection == webhook_connection
        assert message.organization == webhook_connection.organization
        assert message.project == webhook_connection.project
        assert message.content == "Test message"
        assert message.sender_name == "Alice"
        assert message.external_id == "ext-123"
        assert message.raw_payload == payload

    def test_send_message_no_callback_url(self, webhook_connection):
        """Test sending message when no callback URL configured."""
        adapter = GenericWebhookAdapter(webhook_connection)

        result = adapter.send_message("channel-1", "Hello")

        assert not result.success
        assert "No callback URL" in result.error_message

    @patch("requests.post")
    def test_send_message_with_callback(self, mock_post, webhook_connection):
        """Test sending message via callback URL."""
        webhook_connection.config["callback_url"] = "https://example.com/callback"
        webhook_connection.save()

        mock_response = MagicMock()
        mock_response.json.return_value = {"status": "sent"}
        mock_response.content = b'{"status": "sent"}'
        mock_post.return_value = mock_response

        adapter = GenericWebhookAdapter(webhook_connection)

        result = adapter.send_message("channel-1", "Hello")

        assert result.success
        mock_post.assert_called_once()
        call_kwargs = mock_post.call_args
        assert call_kwargs[1]["json"]["content"] == "Hello"
        assert call_kwargs[1]["json"]["channel_id"] == "channel-1"

    def test_extract_field_array_index(self, webhook_connection):
        """Test extracting field from array using index."""
        adapter = GenericWebhookAdapter(webhook_connection)

        payload = {
            "items": [
                {"name": "first"},
                {"name": "second"},
            ]
        }

        result = adapter._extract_field(payload, "items.0.name")
        assert result == "first"

        result = adapter._extract_field(payload, "items.1.name")
        assert result == "second"

    def test_signature_with_prefix(self, webhook_connection, request_factory):
        """Test validating signature with sha256= prefix."""
        adapter = GenericWebhookAdapter(webhook_connection)

        payload = {"content": "Hello"}
        body = json.dumps(payload).encode()

        # Generate signature with prefix
        sig = hmac.new(
            webhook_connection.webhook_secret.encode(),
            body,
            hashlib.sha256,
        ).hexdigest()
        signature = f"sha256={sig}"

        request = request_factory.post(
            "/api/webhooks/webhook/test",
            data=body,
            content_type="application/json",
            HTTP_X_WEBHOOK_SIGNATURE=signature,
        )

        result = adapter.validate_webhook(request)

        assert result.is_valid
