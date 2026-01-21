"""
Document RAG Agent Service.

Provides smolagents CodeAgent integration for document-grounded chat.
Supports multiple LLM providers through the LLMProviderRegistry.
"""

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

from asgiref.sync import sync_to_async
from django.conf import settings
from smolagents import CodeAgent, LiteLLMModel, OpenAIServerModel

from agents.skills import SKILL_LOADER_TOOL_NAME, build_skills_context_block
from agents.tools.skill_loader import SkillLoaderTool
from documents.models import Document
from file_search import FileSearchRegistry
from llm_providers import get_provider_api_key, resolve_llm_config

from .models import RAGSession, RAGSessionMessage
from .telemetry import summarize_smolagents_run
from .tools import DocumentRetrieverTool, ImageAnalyzerTool

if TYPE_CHECKING:
    from projects.models import Project

logger = logging.getLogger(__name__)


@dataclass
class RAGAgentResponse:
    """Response from the RAG agent."""

    response: str
    sources: list[dict]
    thinking_steps: list[str]
    telemetry: dict


class DocumentRAGAgentService:
    """
    smolagents CodeAgent configured for document RAG.

    Supports multiple LLM providers through the LLMProviderRegistry.
    Configuration is resolved from project settings or app defaults.
    Integrates file search as a retrieval tool. The file search backend
    is determined by FileSearchRegistry (defaults to Gemini).
    """

    def __init__(self, session: RAGSession, *, project: "Project | None" = None):
        """
        Initialize the agent service for a RAG session.

        Args:
            session: RAGSession to use for context
            project: Optional project for LLM configuration resolution
        """
        self.session = session

        # Resolve LLM configuration from project or app defaults
        self.config = resolve_llm_config(project=project)
        self.model_id = self.config.model_id
        self.provider_name = self.config.provider

        # Initialize tools
        self.retriever_tool = DocumentRetrieverTool(
            store_id=session.gemini_store_id,
            filters=self._build_search_filters(),
        )
        self.image_analyzer_tool = ImageAnalyzerTool()
        self.skill_loader_tool = SkillLoaderTool()

        # Create the underlying LLM model based on provider
        self.model = self._create_smolagents_model(project)

        logger.debug(
            "DocumentRAGAgentService initialized with provider=%s, model=%s",
            self.provider_name,
            self.model_id,
        )

        # Create CodeAgent with tools
        self.agent = CodeAgent(
            tools=[
                self.retriever_tool,
                self.image_analyzer_tool,
                self.skill_loader_tool,
            ],
            model=self.model,
            max_steps=6,
            verbosity_level=1,
        )

    def _build_search_filters(self) -> dict | None:
        """Build backend-specific filters for this session's context."""
        if not self.session.gemini_store_id:
            return None

        try:
            store = FileSearchRegistry.get()
        except Exception:
            return None
        backend_name = getattr(store, "backend_name", "")

        if backend_name != "chromadb":
            return None

        # ChromaDB requires $and operator for multiple filter conditions
        conditions = [
            {"source_type": "document"},
            {"project_id": str(self.session.project_id)},
            {"workspace_id": str(self.session.workspace_id)},
        ]

        context_type = self.session.context_type
        context_id = self.session.context_id

        if context_type == RAGSession.ContextType.SINGLE:
            conditions.append({"document_id": str(context_id)})
        elif context_type == RAGSession.ContextType.FOLDER:
            conditions.append({"folder_id": str(context_id)})
        elif context_type in {
            RAGSession.ContextType.CLIPBOARD,
            RAGSession.ContextType.COLLECTION,
        }:
            conditions.append(
                {"document_id": {"$in": [str(doc_id) for doc_id in self.session.document_ids]}}
            )

        return {"where": {"$and": conditions}}

    def _create_smolagents_model(self, project: "Project | None"):
        """
        Create the appropriate smolagents model based on provider configuration.

        Args:
            project: Project for API key resolution

        Returns:
            smolagents Model instance
        """
        provider = self.provider_name.lower()

        if provider == "openai":
            api_key = get_provider_api_key("openai", project)
            return OpenAIServerModel(
                model_id=self.model_id,
                api_key=api_key,
            )
        elif provider == "gemini":
            # Use LiteLLM for Gemini support in smolagents
            api_key = get_provider_api_key("gemini", project)
            return LiteLLMModel(
                model_id=f"gemini/{self.model_id}",
                api_key=api_key,
            )
        elif provider == "local":
            # Local models (Ollama, LM Studio) use OpenAI-compatible endpoints
            endpoint = self.config.api_base or getattr(
                settings, "LOCAL_MODEL_ENDPOINT", "http://localhost:11434"
            )
            return OpenAIServerModel(
                model_id=self.model_id,
                api_base=f"{endpoint}/v1",
                api_key="not-needed",  # Local models typically don't need keys
            )
        else:
            # Default to OpenAI for unknown providers
            logger.warning(
                "Unknown provider '%s', falling back to OpenAI", provider
            )
            api_key = get_provider_api_key("openai", project)
            return OpenAIServerModel(
                model_id=self.model_id,
                api_key=api_key,
            )

    async def chat(
        self,
        message: str,
        conversation_history: list[dict] | None = None,
    ) -> RAGAgentResponse:
        """
        Process user message through the CodeAgent.

        Args:
            message: User's message
            conversation_history: Optional previous messages for context

        Returns:
            RAGAgentResponse with response text, sources, and thinking steps
        """
        # Build task with context
        task = self._build_task(message)

        # Run agent (smolagents is synchronous, so we wrap in sync_to_async)
        try:
            run_result = await sync_to_async(self.agent.run)(task, return_full_result=True)

            return RAGAgentResponse(
                response=str(getattr(run_result, "output", run_result)),
                sources=self.retriever_tool.last_retrieved_sources,
                thinking_steps=self._extract_thinking_steps(),
                telemetry={
                    "smolagents": summarize_smolagents_run(run_result),
                    "tools": {
                        "document_retriever": getattr(self.retriever_tool, "telemetry", {}),
                    },
                },
            )
        except Exception as e:
            logger.error(f"Agent error: {e}")
            return RAGAgentResponse(
                response=f"I encountered an error while processing your request: {e}",
                sources=[],
                thinking_steps=[],
                telemetry={
                    "smolagents": {
                        "state": "error",
                        "error_type": type(e).__name__,
                        "error_message": str(e),
                    }
                },
            )

    def _build_task(self, message: str) -> str:
        """
        Build the task string for the agent.

        Args:
            message: User's message

        Returns:
            Formatted task string
        """
        doc_count = self.session.document_count
        context_desc = self.session.get_context_display()
        skills_context = build_skills_context_block(
            context="document_rag",
            tool_name=SKILL_LOADER_TOOL_NAME,
            include_locations=False,
        )
        skills_block = f"\n\n{skills_context}" if skills_context else ""

        return f"""You are a helpful AI assistant with access to {doc_count} documents ({context_desc}).

User's question: {message}

Instructions:
1. Use the document_retriever tool to search for relevant information in the documents.
2. If the user asks about images, use the image_analyzer tool to understand image content.
3. Base your answer on the retrieved information.
4. Cite your sources when providing information from documents.
5. If you can't find relevant information, say so clearly.

Provide a helpful, accurate answer based on the documents.{skills_block}"""

    def _extract_thinking_steps(self) -> list[str]:
        """Extract reasoning steps from agent logs."""
        steps = []
        if hasattr(self.agent, "logs") and self.agent.logs:
            for log in self.agent.logs:
                if isinstance(log, dict) and "step" in log:
                    steps.append(str(log["step"]))
                elif isinstance(log, str):
                    steps.append(log)
        return steps

    async def save_message(
        self,
        role: str,
        content: str,
        sources: list[dict] | None = None,
        thinking_steps: list[str] | None = None,
        telemetry: dict | None = None,
    ) -> RAGSessionMessage:
        """
        Save a message to the session.

        Args:
            role: Message role (user or assistant)
            content: Message content
            sources: Retrieved document sources (for assistant messages)
            thinking_steps: Agent reasoning steps (for assistant messages)

        Returns:
            Created RAGSessionMessage
        """
        return await RAGSessionMessage.objects.acreate(
            session=self.session,
            role=role,
            content=content,
            retrieved_documents=sources or [],
            thinking_steps=thinking_steps or [],
            model_used=self.model_id,
            telemetry=telemetry or {},
        )

    async def get_conversation_history(self) -> list[dict]:
        """
        Get conversation history for this session.

        Returns:
            List of message dicts with role and content
        """
        messages = []
        async for msg in self.session.messages.order_by("created_at"):
            messages.append(
                {
                    "role": msg.role,
                    "content": msg.content,
                }
            )
        return messages

    async def get_document_summary(self) -> str:
        """
        Get a summary of documents in this session.

        Returns:
            Human-readable summary of documents
        """
        doc_ids = self.session.document_ids
        documents = await sync_to_async(list)(
            Document.objects.select_subclasses().filter(id__in=doc_ids)
        )

        if not documents:
            return "No documents in this session."

        lines = [f"Documents in this session ({len(documents)}):"]
        for doc in documents[:10]:  # Limit to first 10
            doc_type = doc.get_type_name()
            lines.append(f"  - {doc.name} ({doc_type})")

        if len(documents) > 10:
            lines.append(f"  ... and {len(documents) - 10} more")

        return "\n".join(lines)
