"""
Tests for the chat application.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch, Mock
from asgiref.sync import sync_to_async
from django.test import AsyncClient
from pydantic import ValidationError

from chat.agent_service import ChatAgentService
from chat.schemas import ChatRequest, ChatResponse


class TestChatAgentService:
    """Tests for the ChatAgentService class."""

    def test_create_agent(self):
        """Test creating a new chat agent."""
        service = ChatAgentService()
        agent = service.create_agent(
            name="TestAgent", instructions="You are a test assistant."
        )

        assert agent is not None
        assert agent["name"] == "TestAgent"
        assert agent["instructions"] == "You are a test assistant."
        assert service.agent_name == "TestAgent"
        assert service.instructions == "You are a test assistant."

    @pytest.mark.asyncio
    async def test_chat(self):
        """Test sending a chat message."""
        service = ChatAgentService()

        # Mock the provider's chat_async method
        mock_response = MagicMock()
        mock_response.content = "Hello! I'm the test assistant."

        with patch.object(
            service.provider, "chat_async", new_callable=AsyncMock
        ) as mock_chat:
            mock_chat.return_value = mock_response
            response = await service.chat("Hello, agent!")
            assert response == "Hello! I'm the test assistant."
            mock_chat.assert_awaited()

    @pytest.mark.asyncio
    async def test_chat_creates_agent_if_none(self):
        """Test that chat creates an agent if one doesn't exist."""
        service = ChatAgentService()

        mock_response = MagicMock()
        mock_response.content = "Response"

        with patch.object(
            service, "create_agent", wraps=service.create_agent
        ) as mock_create, patch.object(
            service.provider, "chat_async", new_callable=AsyncMock
        ) as mock_chat:
            mock_chat.return_value = mock_response
            service.agent_name = None
            service.instructions = None

            await service.chat("Test message")

            mock_create.assert_called_once()
            assert service.agent_name == "ZoeaAssistant"
            assert service.instructions == "You are a helpful AI assistant for Zoea Studio."

    @pytest.mark.asyncio
    async def test_chat_stream(self):
        """Test streaming chat responses."""
        from llm_providers import StreamChunk

        service = ChatAgentService()

        async def fake_stream(*args, **kwargs):
            chunks = [
                StreamChunk(content="Hello"),
                StreamChunk(content=" "),
                StreamChunk(content="World"),
                StreamChunk(content="!"),
            ]
            for chunk in chunks:
                yield chunk

        with patch.object(
            service.provider, "chat_stream_async", return_value=fake_stream()
        ):
            chunks = []
            async for chunk in service.chat_stream("Test message"):
                chunks.append(chunk)

            assert chunks == ["Hello", " ", "World", "!"]


class TestSchemas:
    """Tests for Pydantic schemas."""

    def test_chat_request_valid(self):
        """Test valid ChatRequest."""
        request = ChatRequest(
            message="Hello",
            agent_name="TestAgent",
            instructions="Test instructions",
        )

        assert request.message == "Hello"
        assert request.agent_name == "TestAgent"
        assert request.instructions == "Test instructions"

    def test_chat_request_defaults(self):
        """Test ChatRequest default values."""
        request = ChatRequest(message="Hello")

        assert request.message == "Hello"
        assert request.agent_name == "ZoeaAssistant"
        assert request.instructions == "You are a helpful AI assistant for Zoea Studio."

    def test_chat_request_empty_message_fails(self):
        """Test that empty message fails validation."""
        with pytest.raises(ValidationError):
            ChatRequest(message="")

    def test_chat_response_valid(self):
        """Test valid ChatResponse."""
        response = ChatResponse(
            response="Hello back!",
            agent_name="TestAgent",
            conversation_id=1
        )

        assert response.response == "Hello back!"
        assert response.agent_name == "TestAgent"
        assert response.conversation_id == 1


@pytest.mark.django_db(transaction=True)
class TestAPIEndpoints:
    """Tests for API endpoints."""

    @pytest.fixture
    async def organization(self):
        """Create a test organization."""
        from accounts.models import Account

        return await sync_to_async(Account.objects.create)(
            name="Test Organization",
            subscription_plan="free",
        )

    @pytest.fixture
    async def user_with_org(self, organization):
        """Create a user associated with an organization."""
        from django.contrib.auth import get_user_model
        from organizations.models import OrganizationUser

        User = get_user_model()
        user = await sync_to_async(User.objects.create_user)(
            username="testuser",
            email="test@example.com",
            password="testpass123",
        )
        await sync_to_async(OrganizationUser.objects.create)(
            organization=organization,
            user=user,
            is_admin=True,
        )
        return user

    @pytest.mark.asyncio
    async def test_health_endpoint(self):
        """Test the health check endpoint."""
        from django.test import AsyncClient

        client = AsyncClient()
        response = await client.get("/api/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["service"] == "chat"

    @pytest.mark.asyncio
    async def test_chat_endpoint_basic(self, user_with_org, organization):
        """Test basic chat endpoint without conversation history."""
        from django.test import AsyncClient
        from agents.context import AgentType

        client = AsyncClient()
        await client.aforce_login(user_with_org)

        # Mock the route result to return empty tools (uses ChatAgentService path)
        mock_route_result = MagicMock()
        mock_route_result.agent_type = AgentType.CHAT
        mock_route_result.tools = []  # Empty tools = use ChatAgentService

        # Mock the ChatAgentService
        with (
            patch("chat.api._route_request", return_value=mock_route_result),
            patch("chat.api.ChatAgentService") as mock_service_class,
        ):
            mock_service = MagicMock()
            mock_service.chat = AsyncMock(return_value="Test response")
            mock_service.model_used = "gpt-4o-mini"
            mock_service_class.return_value = mock_service

            response = await client.post(
                "/api/chat",
                data={
                    "message": "Hello",
                    "agent_name": "TestAgent",
                    "instructions": "Test",
                },
                content_type="application/json",
            )

            assert response.status_code == 200
            data = response.json()
            assert data["response"] == "Test response"
            assert data["agent_name"] == "TestAgent"
            assert "conversation_id" in data
            assert isinstance(data["conversation_id"], int)

            # Verify agent was created with organization context
            mock_service.create_agent.assert_called_once()
            call_args = mock_service.create_agent.call_args
            assert "Test Organization" in call_args.kwargs["instructions"]
            assert "testuser" in call_args.kwargs["instructions"]

    @pytest.mark.asyncio
    async def test_chat_endpoint_without_organization(self):
        """Test chat endpoint rejects users without organization."""
        from django.test import AsyncClient
        from django.contrib.auth import get_user_model

        User = get_user_model()
        user = await sync_to_async(User.objects.create_user)(
            username="noorg",
            email="noorg@example.com",
            password="testpass123",
        )

        client = AsyncClient()
        await client.aforce_login(user)

        response = await client.post(
            "/api/chat",
            data={"message": "Hello"},
            content_type="application/json",
        )

        assert response.status_code == 403
        data = response.json()
        assert "not associated with any organization" in data["detail"]

    @pytest.mark.asyncio
    async def test_chat_endpoint_includes_debug_context(self, user_with_org, organization):
        """Debug flag should include enhanced instructions with org/user context."""
        from django.test import AsyncClient
        from agents.context import AgentType

        client = AsyncClient()
        await client.aforce_login(user_with_org)

        # Mock the route result to return empty tools (uses ChatAgentService path)
        mock_route_result = MagicMock()
        mock_route_result.agent_type = AgentType.CHAT
        mock_route_result.tools = []

        with (
            patch("chat.api._route_request", return_value=mock_route_result),
            patch("chat.api.ChatAgentService") as mock_service_class,
        ):
            mock_service = MagicMock()
            mock_service.chat = AsyncMock(return_value="Debug response")
            mock_service.model_used = "gpt-4o-mini"
            mock_service_class.return_value = mock_service

            response = await client.post(
                "/api/chat",
                data={
                    "message": "Hello",
                    "debug": True,
                },
                content_type="application/json",
            )

            assert response.status_code == 200
            data = response.json()
            assert data["response"] == "Debug response"
            assert "system_instructions" in data
            assert organization.name in data["system_instructions"]
            assert data["organization"] == organization.name

            # Enhanced instructions should be passed to the agent
            call_args = mock_service_class.return_value.create_agent.call_args
            assert organization.name in call_args.kwargs["instructions"]
            assert user_with_org.username in call_args.kwargs["instructions"]

    @pytest.mark.asyncio
    async def test_chat_endpoint_rejects_empty_message(self, user_with_org, organization):
        """Pydantic validation should reject empty messages."""
        from django.test import AsyncClient

        client = AsyncClient()
        await client.aforce_login(user_with_org)

        response = await client.post(
            "/api/chat",
            data={"message": ""},
            content_type="application/json",
        )

        # Ninja returns 422 for schema validation errors
        assert response.status_code == 422
        body = response.json()
        assert "message" in str(body).lower()

    @pytest.mark.asyncio
    async def test_chat_endpoint_persists_conversation(self, user_with_org, organization):
        """Test that chat endpoint creates conversation and messages in database."""
        from django.test import AsyncClient
        from chat.models import Conversation, Message
        from agents.context import AgentType

        client = AsyncClient()
        await client.aforce_login(user_with_org)

        # Verify no conversations exist initially
        initial_count = await sync_to_async(Conversation.objects.count)()
        assert initial_count == 0

        # Mock the route result to return empty tools (uses ChatAgentService path)
        mock_route_result = MagicMock()
        mock_route_result.agent_type = AgentType.CHAT
        mock_route_result.tools = []

        # Mock the ChatAgentService
        with (
            patch("chat.api._route_request", return_value=mock_route_result),
            patch("chat.api.ChatAgentService") as mock_service_class,
        ):
            mock_service = MagicMock()
            mock_service.chat = AsyncMock(return_value="Test response from agent")
            mock_service.model_used = "gpt-4o-mini"
            mock_service_class.return_value = mock_service

            response = await client.post(
                "/api/chat",
                data={
                    "message": "Hello, how are you?",
                    "agent_name": "TestAgent",
                    "instructions": "Test instructions",
                },
                content_type="application/json",
            )

            assert response.status_code == 200

            # Verify conversation was created
            conversation_count = await sync_to_async(Conversation.objects.count)()
            assert conversation_count == 1

            # Verify conversation details
            @sync_to_async
            def get_conversation():
                return Conversation.objects.select_related('organization', 'created_by').first()

            conversation = await get_conversation()
            assert conversation.organization.id == organization.id
            assert conversation.created_by.id == user_with_org.id
            assert conversation.agent_name == "TestAgent"

            # Verify messages were created
            @sync_to_async
            def get_messages():
                msgs = list(Message.objects.filter(conversation=conversation).order_by('created_at'))
                # Return simplified data to avoid lazy loading issues in async context
                return [
                    {
                        'role': msg.role,
                        'content': msg.content,
                        'conversation_id': msg.conversation_id,
                        'model_used': msg.model_used
                    }
                    for msg in msgs
                ]

            messages = await get_messages()
            assert len(messages) == 2

            # Check user message
            assert messages[0]['role'] == "user"
            assert messages[0]['content'] == "Hello, how are you?"
            assert messages[0]['conversation_id'] == conversation.id

            # Check assistant message
            assert messages[1]['role'] == "assistant"
            assert messages[1]['content'] == "Test response from agent"
            assert messages[1]['conversation_id'] == conversation.id
            assert messages[1]['model_used'] == "gpt-4o-mini"  # Uses service.model_used

    @pytest.mark.asyncio
    async def test_multiple_chats_create_separate_conversations(self, user_with_org, organization):
        """Test that each chat request creates a new conversation."""
        from django.test import AsyncClient
        from chat.models import Conversation
        from agents.context import AgentType

        client = AsyncClient()
        await client.aforce_login(user_with_org)

        # Mock the route result to return empty tools (uses ChatAgentService path)
        mock_route_result = MagicMock()
        mock_route_result.agent_type = AgentType.CHAT
        mock_route_result.tools = []

        # Mock the ChatAgentService
        with (
            patch("chat.api._route_request", return_value=mock_route_result),
            patch("chat.api.ChatAgentService") as mock_service_class,
        ):
            mock_service = MagicMock()
            mock_service.chat = AsyncMock(return_value="Response")
            mock_service.model_used = "gpt-4o-mini"
            mock_service_class.return_value = mock_service

            # Send first chat
            await client.post(
                "/api/chat",
                data={"message": "First message"},
                content_type="application/json",
            )

            # Send second chat
            await client.post(
                "/api/chat",
                data={"message": "Second message"},
                content_type="application/json",
            )

            # Verify two separate conversations were created
            conversation_count = await sync_to_async(Conversation.objects.count)()
            assert conversation_count == 2

    @pytest.mark.asyncio
    async def test_chat_endpoint_continues_existing_conversation(self, user_with_org, organization):
        """Test that providing conversation_id continues an existing conversation."""
        from django.test import AsyncClient
        from chat.models import Conversation, Message
        from agents.context import AgentType

        client = AsyncClient()
        await client.aforce_login(user_with_org)

        # Mock the route result to return empty tools (uses ChatAgentService path)
        mock_route_result = MagicMock()
        mock_route_result.agent_type = AgentType.CHAT
        mock_route_result.tools = []

        # Mock the ChatAgentService
        with (
            patch("chat.api._route_request", return_value=mock_route_result),
            patch("chat.api.ChatAgentService") as mock_service_class,
        ):
            mock_service = MagicMock()
            mock_service.chat = AsyncMock(return_value="Response")
            mock_service.model_used = "gpt-4o-mini"
            mock_service_class.return_value = mock_service

            # Send first message (creates new conversation)
            response1 = await client.post(
                "/api/chat",
                data={"message": "First message"},
                content_type="application/json",
            )

            assert response1.status_code == 200
            data1 = response1.json()
            conversation_id = data1["conversation_id"]

            # Send second message to same conversation
            response2 = await client.post(
                "/api/chat",
                data={
                    "message": "Second message",
                    "conversation_id": conversation_id
                },
                content_type="application/json",
            )

            assert response2.status_code == 200
            data2 = response2.json()
            assert data2["conversation_id"] == conversation_id

            # Verify only one conversation was created
            conversation_count = await sync_to_async(Conversation.objects.count)()
            assert conversation_count == 1

            # Verify both user messages are in the same conversation
            @sync_to_async
            def get_message_count():
                return Message.objects.filter(
                    conversation_id=conversation_id,
                    role='user'
                ).count()

            user_message_count = await get_message_count()
            assert user_message_count == 2

    @pytest.mark.asyncio
    async def test_chat_endpoint_rejects_invalid_conversation_id(self, user_with_org, organization):
        """Test that providing an invalid conversation_id returns 404."""
        from django.test import AsyncClient

        client = AsyncClient()
        await client.aforce_login(user_with_org)

        response = await client.post(
            "/api/chat",
            data={
                "message": "Hello",
                "conversation_id": 99999  # Non-existent ID
            },
            content_type="application/json",
        )

        assert response.status_code == 404
        data = response.json()
        assert "not found" in data["detail"].lower()

    @pytest.mark.asyncio
    async def test_chat_endpoint_rejects_other_users_conversation(self, organization):
        """Test that users can't access other users' conversations."""
        from django.test import AsyncClient
        from django.contrib.auth import get_user_model
        from organizations.models import OrganizationUser
        from chat.models import Conversation

        User = get_user_model()

        # Create two users in the same organization
        user1 = await sync_to_async(User.objects.create_user)(
            username="user1",
            email="user1@example.com",
            password="testpass123",
        )
        user2 = await sync_to_async(User.objects.create_user)(
            username="user2",
            email="user2@example.com",
            password="testpass123",
        )

        await sync_to_async(OrganizationUser.objects.create)(
            organization=organization,
            user=user1,
        )
        await sync_to_async(OrganizationUser.objects.create)(
            organization=organization,
            user=user2,
        )

        # Create a conversation for user1
        @sync_to_async
        def create_conversation():
            return Conversation.objects.create(
                organization=organization,
                created_by=user1,
                agent_name="TestAgent"
            )

        conversation = await create_conversation()

        # Try to access user1's conversation as user2
        client = AsyncClient()
        await client.aforce_login(user2)

        response = await client.post(
            "/api/chat",
            data={
                "message": "Hello",
                "conversation_id": conversation.id
            },
            content_type="application/json",
        )

        assert response.status_code == 404
        data = response.json()
        assert "not found" in data["detail"].lower() or "access denied" in data["detail"].lower()

    @pytest.mark.asyncio
    async def test_list_conversations_empty(self, user_with_org, organization):
        """Test listing conversations when user has none."""
        from django.test import AsyncClient

        client = AsyncClient()
        await client.aforce_login(user_with_org)

        response = await client.get("/api/conversations")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert data["conversations"] == []

    @pytest.mark.asyncio
    async def test_list_conversations_with_data(self, user_with_org, organization):
        """Test listing conversations with existing conversations."""
        from django.test import AsyncClient
        from chat.models import Conversation, Message

        # Create some test conversations
        @sync_to_async
        def create_test_data():
            conv1 = Conversation.objects.create(
                organization=organization,
                created_by=user_with_org,
                agent_name="TestAgent1"
            )
            Message.objects.create(
                conversation=conv1,
                role='user',
                content='Hello from conversation 1'
            )
            Message.objects.create(
                conversation=conv1,
                role='assistant',
                content='Response 1'
            )

            conv2 = Conversation.objects.create(
                organization=organization,
                created_by=user_with_org,
                agent_name="TestAgent2"
            )
            Message.objects.create(
                conversation=conv2,
                role='user',
                content='Hello from conversation 2'
            )

            return conv1, conv2

        conv1, conv2 = await create_test_data()

        client = AsyncClient()
        await client.aforce_login(user_with_org)

        response = await client.get("/api/conversations")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        assert len(data["conversations"]) == 2

        # Verify conversation data
        # Most recently updated should be first (conv2)
        assert data["conversations"][0]["id"] == conv2.id
        assert data["conversations"][0]["agent_name"] == "TestAgent2"
        assert data["conversations"][0]["message_count"] == 1
        assert data["conversations"][0]["title"] == "Hello from conversation 2"

        assert data["conversations"][1]["id"] == conv1.id
        assert data["conversations"][1]["agent_name"] == "TestAgent1"
        assert data["conversations"][1]["message_count"] == 2
        assert data["conversations"][1]["title"] == "Hello from conversation 1"

    @pytest.mark.asyncio
    async def test_list_conversations_only_shows_user_conversations(self, organization):
        """Test that users only see their own conversations."""
        from django.test import AsyncClient
        from django.contrib.auth import get_user_model
        from organizations.models import OrganizationUser
        from chat.models import Conversation, Message

        User = get_user_model()

        # Create two users in the same organization
        user1 = await sync_to_async(User.objects.create_user)(
            username="user1",
            email="user1@example.com",
            password="testpass123",
        )
        user2 = await sync_to_async(User.objects.create_user)(
            username="user2",
            email="user2@example.com",
            password="testpass123",
        )

        await sync_to_async(OrganizationUser.objects.create)(
            organization=organization,
            user=user1,
        )
        await sync_to_async(OrganizationUser.objects.create)(
            organization=organization,
            user=user2,
        )

        # Create conversations for both users
        @sync_to_async
        def create_conversations():
            # User1's conversation
            conv1 = Conversation.objects.create(
                organization=organization,
                created_by=user1,
                agent_name="Agent1"
            )
            Message.objects.create(
                conversation=conv1,
                role='user',
                content='User 1 message'
            )

            # User2's conversation
            conv2 = Conversation.objects.create(
                organization=organization,
                created_by=user2,
                agent_name="Agent2"
            )
            Message.objects.create(
                conversation=conv2,
                role='user',
                content='User 2 message'
            )

        await create_conversations()

        # Login as user1 and verify they only see their conversation
        client = AsyncClient()
        await client.aforce_login(user1)

        response = await client.get("/api/conversations")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["conversations"][0]["title"] == "User 1 message"

    @pytest.mark.asyncio
    async def test_list_conversations_requires_authentication(self):
        """Test that listing conversations requires authentication."""
        from django.test import AsyncClient

        client = AsyncClient()
        # Don't login

        response = await client.get("/api/conversations")

        # Should be rejected (401 or 403)
        assert response.status_code in [401, 403]

    @pytest.mark.asyncio
    async def test_message_creation_updates_conversation_timestamp(self, user_with_org, organization):
        """Test that creating a message updates the conversation's updated_at timestamp."""
        from chat.models import Conversation, Message
        from datetime import datetime
        import time

        # Create a conversation
        @sync_to_async
        def create_conversation():
            return Conversation.objects.create(
                organization=organization,
                created_by=user_with_org,
                title="Test Conversation",
                agent_name="TestAgent"
            )

        conversation = await create_conversation()

        # Get initial updated_at timestamp
        @sync_to_async
        def get_updated_at():
            conversation.refresh_from_db()
            return conversation.updated_at

        initial_updated_at = await get_updated_at()

        # Wait a tiny bit to ensure timestamps differ
        time.sleep(0.01)

        # Create a message
        @sync_to_async
        def create_message():
            return Message.objects.create(
                conversation=conversation,
                role='user',
                content='Test message'
            )

        await create_message()

        # Get updated_at after message creation
        final_updated_at = await get_updated_at()

        # The conversation's updated_at should have been updated by the signal
        assert final_updated_at > initial_updated_at

    @pytest.mark.asyncio
    async def test_delete_conversation_success(self, user_with_org, organization):
        """Test that a user can delete their own conversation."""
        from django.test import AsyncClient
        from chat.models import Conversation, Message

        # Create a conversation with messages
        @sync_to_async
        def create_conversation():
            conv = Conversation.objects.create(
                organization=organization,
                created_by=user_with_org,
                agent_name="TestAgent"
            )
            Message.objects.create(
                conversation=conv,
                role='user',
                content='Test message'
            )
            return conv

        conversation = await create_conversation()
        conv_id = conversation.id

        client = AsyncClient()
        await client.aforce_login(user_with_org)

        response = await client.delete(f"/api/conversations/{conv_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

        # Verify conversation was actually deleted
        @sync_to_async
        def check_deleted():
            return not Conversation.objects.filter(id=conv_id).exists()

        assert await check_deleted()

    @pytest.mark.asyncio
    async def test_delete_conversation_not_found(self, user_with_org, organization):
        """Test deleting a non-existent conversation returns 404."""
        from django.test import AsyncClient

        client = AsyncClient()
        await client.aforce_login(user_with_org)

        response = await client.delete("/api/conversations/99999")

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_conversation_other_user(self, organization):
        """Test that a user cannot delete another user's conversation."""
        from django.test import AsyncClient
        from django.contrib.auth import get_user_model
        from organizations.models import OrganizationUser
        from chat.models import Conversation

        User = get_user_model()

        # Create two users in the same organization
        user1 = await sync_to_async(User.objects.create_user)(
            username="deleter1",
            email="deleter1@example.com",
            password="testpass123",
        )
        user2 = await sync_to_async(User.objects.create_user)(
            username="deleter2",
            email="deleter2@example.com",
            password="testpass123",
        )

        await sync_to_async(OrganizationUser.objects.create)(
            organization=organization,
            user=user1,
        )
        await sync_to_async(OrganizationUser.objects.create)(
            organization=organization,
            user=user2,
        )

        # Create conversation for user1
        @sync_to_async
        def create_conversation():
            return Conversation.objects.create(
                organization=organization,
                created_by=user1,
                agent_name="TestAgent"
            )

        conversation = await create_conversation()

        # Login as user2 and try to delete user1's conversation
        client = AsyncClient()
        await client.aforce_login(user2)

        response = await client.delete(f"/api/conversations/{conversation.id}")

        # Should be rejected
        assert response.status_code == 404

        # Verify conversation still exists
        @sync_to_async
        def check_exists():
            return Conversation.objects.filter(id=conversation.id).exists()

        assert await check_exists()
