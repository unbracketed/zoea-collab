"""Tests for platform_adapters models."""

import pytest
from django.contrib.auth import get_user_model

from accounts.models import Account
from platform_adapters.models import (
    PlatformMessage,
    ConnectionStatus,
    MessageDirection,
    MessageStatus,
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
    user = User.objects.create_user(
        username="testuser",
        email="testuser@example.com",
        password="testpass123",
    )
    return user


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
def platform_connection(db, organization, project, user):
    """Create a test platform connection."""
    return PlatformConnection.objects.create(
        organization=organization,
        project=project,
        platform_type=PlatformType.WEBHOOK,
        name="Test Webhook",
        description="Test webhook connection",
        status=ConnectionStatus.ACTIVE,
        created_by=user,
    )


class TestPlatformConnection:
    """Tests for PlatformConnection model."""

    def test_create_connection(self, organization, user):
        """Test creating a platform connection."""
        connection = PlatformConnection.objects.create(
            organization=organization,
            platform_type=PlatformType.SLACK,
            name="Test Slack",
            created_by=user,
        )

        assert connection.id is not None
        assert connection.connection_id is not None
        assert connection.webhook_secret is not None
        assert len(connection.webhook_secret) > 20
        assert connection.status == ConnectionStatus.PENDING

    def test_webhook_url_generation(self, platform_connection):
        """Test webhook URL generation."""
        url = platform_connection.get_webhook_url()

        assert "webhook" in url.lower()
        assert str(platform_connection.connection_id) in url
        assert platform_connection.platform_type in url

    def test_record_message(self, platform_connection):
        """Test recording a message updates stats."""
        initial_count = platform_connection.message_count
        assert platform_connection.last_message_at is None

        platform_connection.record_message()
        platform_connection.refresh_from_db()

        assert platform_connection.message_count == initial_count + 1
        assert platform_connection.last_message_at is not None

    def test_set_status(self, platform_connection):
        """Test setting connection status."""
        platform_connection.set_status(ConnectionStatus.ERROR, "API key invalid")
        platform_connection.refresh_from_db()

        assert platform_connection.status == ConnectionStatus.ERROR
        assert platform_connection.status_message == "API key invalid"

    def test_string_representation(self, platform_connection):
        """Test string representation."""
        expected = f"{platform_connection.name} (Generic Webhook)"
        assert str(platform_connection) == expected


class TestPlatformMessage:
    """Tests for PlatformMessage model."""

    def test_create_message(self, platform_connection):
        """Test creating a channel message."""
        message = PlatformMessage.objects.create(
            connection=platform_connection,
            organization=platform_connection.organization,
            project=platform_connection.project,
            external_id="ext-123",
            channel_id="channel-1",
            sender_id="user-1",
            sender_name="Test User",
            content="Hello, world!",
        )

        assert message.id is not None
        assert message.message_id is not None
        assert message.direction == MessageDirection.INBOUND
        assert message.status == MessageStatus.RECEIVED

    def test_set_status_processing(self, platform_connection):
        """Test setting message status to processing."""
        message = PlatformMessage.objects.create(
            connection=platform_connection,
            organization=platform_connection.organization,
            content="Test message",
        )

        message.set_status(MessageStatus.PROCESSING)
        message.refresh_from_db()

        assert message.status == MessageStatus.PROCESSING

    def test_set_status_processed(self, platform_connection):
        """Test setting message status to processed updates processed_at."""
        message = PlatformMessage.objects.create(
            connection=platform_connection,
            organization=platform_connection.organization,
            content="Test message",
        )
        assert message.processed_at is None

        message.set_status(MessageStatus.PROCESSED)
        message.refresh_from_db()

        assert message.status == MessageStatus.PROCESSED
        assert message.processed_at is not None

    def test_to_trigger_envelope(self, platform_connection):
        """Test converting message to trigger envelope."""
        message = PlatformMessage.objects.create(
            connection=platform_connection,
            organization=platform_connection.organization,
            project=platform_connection.project,
            external_id="ext-123",
            channel_id="channel-1",
            sender_id="user-1",
            sender_name="Test User",
            sender_email="test@example.com",
            content="Hello, world!",
        )

        envelope = message.to_trigger_envelope()

        assert envelope["trigger_type"] == "channel_message"
        assert envelope["source"]["platform"] == PlatformType.WEBHOOK
        assert envelope["source"]["connection_id"] == str(platform_connection.connection_id)
        assert envelope["payload"]["content"] == "Hello, world!"
        assert envelope["payload"]["sender_name"] == "Test User"
        assert envelope["organization_id"] == platform_connection.organization_id
        assert envelope["project_id"] == platform_connection.project_id

    def test_string_representation(self, platform_connection):
        """Test string representation."""
        message = PlatformMessage.objects.create(
            connection=platform_connection,
            organization=platform_connection.organization,
            sender_name="Alice",
            content="This is a long message that should be truncated in the string representation",
        )

        str_repr = str(message)
        assert "Alice" in str_repr
        assert "..." in str_repr  # Should be truncated

    def test_message_with_attachments(self, platform_connection):
        """Test creating a message with attachments."""
        attachments = [
            {"url": "https://example.com/file.pdf", "filename": "doc.pdf", "size": 1024},
            {"url": "https://example.com/image.png", "filename": "image.png", "size": 2048},
        ]

        message = PlatformMessage.objects.create(
            connection=platform_connection,
            organization=platform_connection.organization,
            content="Check out these files",
            attachments=attachments,
        )

        message.refresh_from_db()
        assert len(message.attachments) == 2
        assert message.attachments[0]["filename"] == "doc.pdf"
