"""
Chat agent service using LLM Provider abstraction.

Supports multiple LLM providers (OpenAI, Gemini, local models) through
the LLMProviderRegistry. Configuration is resolved from project settings
or app defaults.
"""

import logging
from collections.abc import AsyncGenerator
from typing import TYPE_CHECKING

from llm_providers import (
    ChatMessage,
    LLMProviderRegistry,
    resolve_llm_config,
)

if TYPE_CHECKING:
    from projects.models import Project

logger = logging.getLogger(__name__)


class ChatAgentService:
    """
    Service for managing chat agent interactions.

    Uses the LLMProviderRegistry to support multiple LLM backends.
    Configuration is resolved from project settings or app defaults.
    """

    def __init__(
        self,
        *,
        project: "Project | None" = None,
        model_id: str | None = None,
        provider_name: str | None = None,
    ):
        """
        Initialize the chat agent service.

        Args:
            project: Optional project to use for configuration resolution.
            model_id: Optional model ID override.
            provider_name: Optional provider name override.
        """
        # Resolve configuration from hierarchy
        agent_config = {}
        if provider_name:
            agent_config["provider"] = provider_name
        if model_id:
            agent_config["model"] = model_id

        self.config = resolve_llm_config(
            project=project,
            agent_config=agent_config if agent_config else None,
        )

        self.provider = LLMProviderRegistry.get(self.config.provider, config=self.config)
        self.model_id = self.config.model_id

        self.agent_name: str | None = "ZoeaAssistant"
        self.instructions: str | None = "You are a helpful AI assistant for Zoea Studio."

        logger.debug(
            "ChatAgentService initialized with provider=%s, model=%s",
            self.config.provider,
            self.model_id,
        )

    def create_agent(
        self,
        name: str = "ZoeaAssistant",
        instructions: str = "You are a helpful AI assistant for Zoea Studio.",
    ):
        """
        Set agent metadata for downstream requests.

        Args:
            name: Name of the agent
            instructions: System instructions for the agent
        """
        self.agent_name = name
        self.instructions = instructions
        return {"name": name, "instructions": instructions}

    async def chat(
        self,
        message: str,
        conversation_messages: list[dict] | None = None,
        image_contents: list[dict] | None = None,
    ) -> str:
        """
        Send a message and get a response with optional conversation context.

        Args:
            message: User message to send
            conversation_messages: Optional list of prior messages for context
                                  Format: [{"role": "user/assistant/system", "content": "..."}]
            image_contents: Optional list of image content parts (OpenAI format)

        Returns:
            Agent's response text
        """
        if not self.instructions or not self.agent_name:
            self.create_agent(
                name=self.agent_name or "ZoeaAssistant",
                instructions="You are a helpful AI assistant for Zoea Studio.",
            )

        # Build messages list
        messages = [ChatMessage(role="system", content=self.instructions)]

        # Add conversation history (may include multimodal content with images)
        if conversation_messages:
            for msg in conversation_messages:
                messages.append(ChatMessage(role=msg["role"], content=msg["content"]))

        # Add current user message
        # For vision models with image_contents, use multimodal format
        if image_contents:
            # Multimodal format: content is a list of text + images
            multimodal_content = [{"type": "text", "text": message}] + image_contents
            messages.append(ChatMessage(role="user", content=multimodal_content))
        else:
            messages.append(ChatMessage(role="user", content=message))

        logger.debug(
            "Dispatching %s messages to %s/%s",
            len(messages),
            self.config.provider,
            self.model_id,
        )

        # Use provider's async chat method
        response = await self.provider.chat_async(
            messages,
            model_id=self.model_id,
        )

        return response.content

    async def chat_stream(
        self,
        message: str,
        conversation_messages: list[dict] | None = None,
    ) -> AsyncGenerator[str, None]:
        """
        Send a message and stream the response.

        Args:
            message: User message to send
            conversation_messages: Optional list of prior messages for context

        Yields:
            Chunks of agent's response text
        """
        if not self.instructions:
            self.create_agent(
                name=self.agent_name or "ZoeaAssistant",
                instructions="You are a helpful AI assistant for Zoea Studio.",
            )

        # Build messages list
        messages = [ChatMessage(role="system", content=self.instructions)]

        if conversation_messages:
            for msg in conversation_messages:
                messages.append(ChatMessage(role=msg["role"], content=msg["content"]))

        messages.append(ChatMessage(role="user", content=message))

        logger.debug(
            "Streaming %s messages to %s/%s",
            len(messages),
            self.config.provider,
            self.model_id,
        )

        # Use provider's async streaming method
        async for chunk in self.provider.chat_stream_async(messages, model_id=self.model_id):
            if chunk.content:
                yield chunk.content

    @property
    def provider_name(self) -> str:
        """Return the provider name being used."""
        return self.config.provider

    @property
    def model_used(self) -> str:
        """Return the model ID being used."""
        return self.model_id
