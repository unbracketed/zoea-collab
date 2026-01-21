"""
Agent Router for Context-Aware Routing.

Routes requests to appropriate agents based on context (view type, document type,
selected documents, etc.).
"""

import logging
from typing import TYPE_CHECKING

from agents.context import AgentContext, AgentRouteResult, AgentType
from agents.registry import ToolRegistry

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class AgentRouter:
    """
    Routes requests to appropriate agents based on context.

    The router examines the AgentContext and determines:
    1. Which agent type to use
    2. Which tools should be available
    3. Any special configuration needed

    Routing Rules:
    - ExcalidrawDiagram document -> EXCALIDRAW agent with image tools
    - RAG session context -> DOCUMENT_RAG agent
    - Multi-document selection -> DOCUMENT_RAG agent
    - Deep research request -> DEEP_RESEARCH agent
    - Default -> CHAT agent with enabled tools

    Example:
        router = AgentRouter()
        context = AgentContext(
            project=project,
            workspace=workspace,
            document=excalidraw_doc,
        )
        result = router.route(context)
        # result.agent_type == AgentType.EXCALIDRAW
    """

    def __init__(self):
        self.tool_registry = ToolRegistry.get_instance()

    def route(self, context: AgentContext) -> AgentRouteResult:
        """
        Determine agent and tools for the given context.

        Args:
            context: AgentContext with request information

        Returns:
            AgentRouteResult with agent type and configured tools
        """
        # Check for explicit deep research request
        if context.requested_capabilities:
            if "deep_research" in context.requested_capabilities:
                return self._route_deep_research(context)

        # Check for Excalidraw document
        if context.document_type == "Excalidraw":
            return self._route_excalidraw(context)

        # Check for RAG context
        if context.rag_session_id or context.is_multi_document:
            return self._route_document_rag(context)

        # Check for folder/collection context
        if context.folder_id or context.collection_id:
            return self._route_document_rag(context)

        # Default to chat agent
        return self._route_chat(context)

    def _route_chat(self, context: AgentContext) -> AgentRouteResult:
        """Route to chat agent with general tools."""
        tools = self.tool_registry.get_enabled_tools(
            project=context.project,
            context="chat",
        )
        return AgentRouteResult(
            agent_type=AgentType.CHAT,
            tools=tools,
            config={
                "project_id": context.project.id,
                "workspace_id": context.workspace.id,
            },
        )

    def _route_document_rag(self, context: AgentContext) -> AgentRouteResult:
        """Route to document RAG agent."""
        tools = self.tool_registry.get_enabled_tools(
            project=context.project,
            context="document_rag",
        )
        return AgentRouteResult(
            agent_type=AgentType.DOCUMENT_RAG,
            tools=tools,
            config={
                "project_id": context.project.id,
                "workspace_id": context.workspace.id,
                "document_ids": context.document_ids,
                "folder_id": context.folder_id,
                "collection_id": context.collection_id,
                "rag_session_id": context.rag_session_id,
            },
        )

    def _route_excalidraw(self, context: AgentContext) -> AgentRouteResult:
        """Route to Excalidraw-specialized agent."""
        tools = self.tool_registry.get_enabled_tools(
            project=context.project,
            context="excalidraw",
        )
        return AgentRouteResult(
            agent_type=AgentType.EXCALIDRAW,
            tools=tools,
            config={
                "project_id": context.project.id,
                "workspace_id": context.workspace.id,
                "document_id": context.document.id if context.document else None,
            },
        )

    def _route_deep_research(self, context: AgentContext) -> AgentRouteResult:
        """Route to deep research agent."""
        tools = self.tool_registry.get_enabled_tools(
            project=context.project,
            context="research",
        )
        return AgentRouteResult(
            agent_type=AgentType.DEEP_RESEARCH,
            tools=tools,
            config={
                "project_id": context.project.id,
                "workspace_id": context.workspace.id,
                "max_passes": 3,  # Multi-pass search
            },
        )
