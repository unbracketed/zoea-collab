"""
AI service wrapper for ChatAgentService.

Provides both sync and async interfaces for use in workflow nodes.
"""

import asyncio
import logging
from typing import List, Optional

logger = logging.getLogger(__name__)


class AIService:
    """
    AI service wrapper providing sync/async chat interfaces.

    Wraps ChatAgentService to provide:
    - Synchronous chat() for use in PocketFlow nodes
    - Asynchronous achat() for direct async usage

    Example config in flow-config.yaml:
        SERVICES:
          - name: AIService
            ctxref: ai

    Example usage in nodes:
        def prep(self, shared):
            ctx = shared['ctx']
            return "Generate a plan for this issue..."

        def run(self, prompt):
            # In workflow nodes, we get the service from context
            # and call it synchronously
            return self._ai_service.chat(prompt)
    """

    def __init__(self, model_id: Optional[str] = None):
        """
        Initialize AI service.

        Args:
            model_id: Optional model ID override (default from settings)
        """
        # Lazy import to avoid Django setup issues
        from chat.agent_service import ChatAgentService

        self._service = ChatAgentService(model_id=model_id)
        self._agent_configured = False

    def configure_agent(
        self,
        name: str = "WorkflowAgent",
        instructions: str = "You are a helpful AI assistant.",
    ) -> None:
        """
        Configure the agent for subsequent chat calls.

        Args:
            name: Agent name
            instructions: System instructions/prompt
        """
        self._service.create_agent(name=name, instructions=instructions)
        self._agent_configured = True
        logger.debug(f"Configured AI agent: {name}")

    def chat(
        self,
        message: str,
        conversation_messages: Optional[List[dict]] = None,
        agent_name: Optional[str] = None,
        instructions: Optional[str] = None,
    ) -> str:
        """
        Synchronous chat interface for use in PocketFlow nodes.

        Runs the async ChatAgentService.chat() via asyncio.run().

        Args:
            message: The message/prompt to send
            conversation_messages: Optional prior conversation context
            agent_name: Optional agent name (configures agent if provided)
            instructions: Optional system instructions (configures agent if provided)

        Returns:
            The AI response text
        """
        # Configure agent if parameters provided
        if agent_name or instructions:
            self.configure_agent(
                name=agent_name or "WorkflowAgent",
                instructions=instructions or "You are a helpful AI assistant.",
            )
        elif not self._agent_configured:
            self.configure_agent()

        # Run async method synchronously
        return asyncio.run(self._service.chat(message, conversation_messages=conversation_messages))

    async def achat(
        self,
        message: str,
        conversation_messages: Optional[List[dict]] = None,
        agent_name: Optional[str] = None,
        instructions: Optional[str] = None,
    ) -> str:
        """
        Asynchronous chat interface.

        Args:
            message: The message/prompt to send
            conversation_messages: Optional prior conversation context
            agent_name: Optional agent name (configures agent if provided)
            instructions: Optional system instructions (configures agent if provided)

        Returns:
            The AI response text
        """
        # Configure agent if parameters provided
        if agent_name or instructions:
            self.configure_agent(
                name=agent_name or "WorkflowAgent",
                instructions=instructions or "You are a helpful AI assistant.",
            )
        elif not self._agent_configured:
            self.configure_agent()

        return await self._service.chat(message, conversation_messages=conversation_messages)

    async def astream(
        self,
        message: str,
        conversation_messages: Optional[List[dict]] = None,
    ):
        """
        Async streaming chat interface.

        Args:
            message: The message/prompt to send
            conversation_messages: Optional prior conversation context

        Yields:
            Response text chunks
        """
        if not self._agent_configured:
            self.configure_agent()

        async for chunk in self._service.chat_stream(
            message, conversation_messages=conversation_messages
        ):
            yield chunk
