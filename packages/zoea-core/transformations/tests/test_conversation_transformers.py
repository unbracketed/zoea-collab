"""Tests for Conversation transformers.

This module tests the concrete transformers that convert Conversation objects
and ConversationPayload value objects to various output formats.
"""

from datetime import datetime

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from accounts.models import Account
from accounts.utils import get_user_organization
from chat.models import Conversation, Message
from organizations.models import OrganizationUser
from projects.models import Project
from transformations import OutputFormat, transform
from transformations.value_objects import ConversationPayload, MarkdownPayload
from workspaces.models import Workspace

User = get_user_model()


@pytest.fixture
def user_with_org(db):
    """Create a user with an organization."""
    user = User.objects.create_user(username="testuser", password="testpass")
    account = Account.objects.create(name="Test Org")
    OrganizationUser.objects.create(organization=account, user=user)
    return user


@pytest.fixture
def workspace(db, user_with_org):
    """Create a workspace for testing."""
    account = get_user_organization(user_with_org)
    project = Project.objects.create(
        name="Test Project", description="Test", organization=account
    )
    return Workspace.objects.create(
        name="Test Workspace", project=project
    )


@pytest.fixture
def conversation(db, workspace, user_with_org):
    """Create a conversation with messages for testing."""
    account = workspace.project.organization

    conv = Conversation.objects.create(
        agent_name="TestAgent",
        organization=account,
        project=workspace.project,
        workspace=workspace,
        created_by=user_with_org,
    )

    # Add some messages
    Message.objects.create(
        conversation=conv,
        role="user",
        content="What is the weather like?",
    )

    Message.objects.create(
        conversation=conv,
        role="assistant",
        content="I don't have access to real-time weather data.",
        model_used="gpt-4",
        token_count=25,
    )

    Message.objects.create(
        conversation=conv,
        role="user",
        content="Can you help me with Python code?",
    )

    return conv


@pytest.mark.django_db
class TestConversationToMarkdownTransformer:
    """Tests for Conversation to Markdown transformation."""

    def test_transform_conversation_to_markdown(self, conversation):
        """Test converting Conversation to Markdown format."""
        result = transform(conversation, OutputFormat.MARKDOWN)

        assert isinstance(result, str)

        # Check that title is included (generated from first user message)
        assert "# What is the weather like?" in result

        # Check metadata
        assert "**Agent:** TestAgent" in result
        assert "**Created by:** testuser" in result
        assert "**Created at:**" in result

        # Check messages are included
        assert "## User" in result
        assert "What is the weather like?" in result

        assert "## Assistant" in result
        assert "I don't have access to real-time weather data." in result

        assert "Can you help me with Python code?" in result

        # Check metadata for assistant message
        assert "Model: gpt-4" in result
        assert "Tokens: 25" in result

        # Check separators
        assert result.count("---") >= 3  # At least 3 separators

    def test_transform_prefetched_conversation(self, conversation):
        """Test that transformation works with prefetched messages."""
        # Prefetch to avoid N+1 queries
        conv = Conversation.objects.prefetch_related("messages").get(id=conversation.id)

        result = transform(conv, OutputFormat.MARKDOWN)

        assert "What is the weather like?" in result
        assert "I don't have access to real-time weather data." in result

    def test_transform_empty_conversation(self, workspace, user_with_org):
        """Test converting conversation with no messages."""
        account = workspace.project.organization

        empty_conv = Conversation.objects.create(
            agent_name="EmptyAgent",
            organization=account,
            project=workspace.project,
            workspace=workspace,
            created_by=user_with_org,
        )

        result = transform(empty_conv, OutputFormat.MARKDOWN)

        # Title will be "Conversation {id}" since there are no messages
        assert f"# Conversation {empty_conv.id}" in result
        assert "**Agent:** EmptyAgent" in result
        # Should have metadata separator but no message content
        assert "---" in result


@pytest.mark.django_db
class TestConversationPayloadToMarkdownTransformer:
    """Tests for ConversationPayload to Markdown transformation."""

    def test_transform_payload_to_markdown(self):
        """Test converting ConversationPayload to Markdown."""
        now = timezone.now()

        payload = ConversationPayload(
            title="My Conversation",
            agent_name="TestBot",
            messages=[
                ("user", "Hello!", now),
                ("assistant", "Hi there!", now),
                ("user", "How are you?", None),  # No timestamp
            ],
        )

        result = transform(payload, OutputFormat.MARKDOWN)

        assert isinstance(result, str)
        assert "# My Conversation" in result
        assert "**Agent:** TestBot" in result

        assert "## user" in result
        assert "Hello!" in result

        assert "## assistant" in result
        assert "Hi there!" in result

        assert "How are you?" in result

    def test_transform_minimal_payload(self):
        """Test converting minimal ConversationPayload."""
        payload = ConversationPayload(
            messages=[("user", "Test message", None)],
        )

        result = transform(payload, OutputFormat.MARKDOWN)

        assert "## user" in result
        assert "Test message" in result
        # Should not have title heading since they weren't provided
        # (but will have ## for message roles)
        title_headings = [line for line in result.split("\n") if line.startswith("# ") and not line.startswith("## ")]
        assert len(title_headings) == 0


@pytest.mark.django_db
class TestConversationToJSONTransformer:
    """Tests for Conversation to JSON transformation."""

    def test_transform_conversation_to_json(self, conversation):
        """Test converting Conversation to JSON dict."""
        result = transform(conversation, OutputFormat.JSON)

        assert isinstance(result, dict)

        # Check conversation fields
        assert result["id"] == conversation.id
        assert result["agent_name"] == "TestAgent"
        assert result["created_by"] == "testuser"
        assert "created_at" in result
        assert "updated_at" in result

        # Check messages
        assert "messages" in result
        messages = result["messages"]
        assert len(messages) == 3

        # Check first message
        msg1 = messages[0]
        assert msg1["role"] == "user"
        assert msg1["content"] == "What is the weather like?"
        assert "created_at" in msg1

        # Check second message with metadata
        msg2 = messages[1]
        assert msg2["role"] == "assistant"
        assert msg2["content"] == "I don't have access to real-time weather data."
        assert msg2["model_used"] == "gpt-4"
        assert msg2["token_count"] == 25

    def test_json_is_serializable(self, conversation):
        """Test that JSON output is actually JSON-serializable."""
        import json

        result = transform(conversation, OutputFormat.JSON)

        # This should not raise
        json_str = json.dumps(result)
        assert isinstance(json_str, str)

        # Should be able to parse back
        parsed = json.loads(json_str)
        assert parsed["agent_name"] == "TestAgent"


@pytest.mark.django_db
class TestConversationChaining:
    """Tests for chaining conversation transformations."""

    def test_conversation_to_markdown_to_payload(self, conversation):
        """Test chaining: Conversation → Markdown → MarkdownPayload → Outline."""
        # First transform conversation to markdown
        markdown_text = transform(conversation, OutputFormat.MARKDOWN)

        # Create a MarkdownPayload from the result
        from transformations.value_objects import MarkdownPayload

        payload = MarkdownPayload(content=markdown_text)

        # Now transform to outline
        outline = transform(payload, OutputFormat.OUTLINE)

        assert "sections" in outline
        sections = outline["sections"]

        # Should have parsed the conversation structure
        # The main heading should be level 1
        # Each message should be level 2
        assert len(sections) > 0
        assert sections[0]["level"] == 1

    def test_conversation_payload_to_outline(self):
        """Test chaining starting from ConversationPayload value object."""
        payload = ConversationPayload(
            title="Payload Conversation",
            agent_name="PayloadBot",
            messages=[
                ("user", "Hello there!", timezone.now()),
                ("assistant", "Hi! How can I help?", timezone.now()),
            ],
        )

        markdown_text = transform(payload, OutputFormat.MARKDOWN)
        outline = transform(MarkdownPayload(content=markdown_text), OutputFormat.OUTLINE)

        assert "sections" in outline
        sections = outline["sections"]
        assert len(sections) >= 1
        assert sections[0]["title"] == "Payload Conversation"
        # First section should have child entries for each message
        assert len(sections[0]["children"]) >= 1
