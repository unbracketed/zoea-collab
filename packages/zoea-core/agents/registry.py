"""
Tool Registry for Agent Orchestration.

Central registry for all available smolagents tools with support for:
- Tool registration with metadata
- Per-project enablement checking
- Context-based filtering
- Factory pattern for tool instantiation
"""

import logging
import os
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Callable, Optional

from smolagents import Tool

if TYPE_CHECKING:
    from projects.models import Project

logger = logging.getLogger(__name__)


@dataclass
class ToolDefinition:
    """Metadata about a registered tool."""

    name: str
    description: str
    tool_class: type[Tool]
    category: str
    default_enabled: bool = True
    requires_api_key: Optional[str] = None  # e.g., "SERPAPI_API_KEY"
    supported_contexts: list[str] = field(default_factory=lambda: ["*"])
    factory: Optional[Callable[..., Tool]] = None


class ToolRegistry:
    """
    Central registry for all available smolagents tools.

    Singleton pattern - use ToolRegistry.get_instance() to access.

    Features:
    - Auto-discovery of tools in agents/tools/
    - Per-project enablement checking
    - Factory pattern for tool instantiation with config
    - Context filtering for view-specific tools

    Example:
        registry = ToolRegistry.get_instance()

        # Get all tools enabled for a project
        tools = registry.get_enabled_tools(project)

        # Get tools for specific context
        tools = registry.get_tools_for_context(project, "excalidraw")
    """

    _instance: Optional["ToolRegistry"] = None

    def __init__(self):
        self._tools: dict[str, ToolDefinition] = {}

    @classmethod
    def get_instance(cls) -> "ToolRegistry":
        """Get singleton registry instance."""
        if cls._instance is None:
            cls._instance = cls()
            cls._instance._register_builtins()
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """Reset singleton (useful for testing)."""
        cls._instance = None

    def _register_builtins(self) -> None:
        """Register built-in tools."""
        # WebSearchTool - always available
        try:
            from agents.tools.web_search import WebSearchTool

            self.register(
                name="web_search",
                description="Search the web using DuckDuckGo",
                tool_class=WebSearchTool,
                category="search",
                default_enabled=True,
                supported_contexts=["*"],
            )
        except ImportError as e:
            logger.warning(f"Could not register WebSearchTool: {e}")

        # VisitWebpageTool - fetch and read webpage content
        try:
            from agents.tools.visit_webpage import VisitWebpageTool

            self.register(
                name="visit_webpage",
                description="Visit a URL and read its content as markdown",
                tool_class=VisitWebpageTool,
                category="search",
                default_enabled=True,
                supported_contexts=["*"],
            )
        except ImportError as e:
            logger.warning(f"Could not register VisitWebpageTool: {e}")

        # ImageAnalyzerTool - requires OpenAI API key
        try:
            from agents.tools.image_analyzer import ImageAnalyzerTool

            self.register(
                name="image_analyzer",
                description="Analyze images using OpenAI vision models",
                tool_class=ImageAnalyzerTool,
                category="analysis",
                default_enabled=True,
                requires_api_key="OPENAI_API_KEY",
                supported_contexts=["document_rag", "image", "excalidraw"],
            )
        except ImportError as e:
            logger.warning(f"Could not register ImageAnalyzerTool: {e}")

        # Note: DocumentRetrieverTool requires a store_id and is instantiated
        # directly by RAG sessions, not through the registry. It's available
        # in agents.tools.document_retriever for direct use.

        # OpenAI Image Generation Tool (#97)
        try:
            from agents.tools.image_gen_openai import OpenAIImageGenTool

            self.register(
                name="image_gen_openai",
                description="Generate images using OpenAI DALL-E",
                tool_class=OpenAIImageGenTool,
                category="image",
                default_enabled=True,
                requires_api_key="OPENAI_API_KEY",
                supported_contexts=["*"],
            )
        except ImportError as e:
            logger.warning(f"Could not register OpenAIImageGenTool: {e}")

        # Hugging Face Image Generation Tool (#98)
        try:
            from agents.tools.image_gen_hf import HuggingFaceImageGenTool

            self.register(
                name="image_gen_huggingface",
                description="Generate images using Hugging Face models (Stable Diffusion, FLUX, etc.)",
                tool_class=HuggingFaceImageGenTool,
                category="image",
                default_enabled=True,
                requires_api_key="HF_API_TOKEN",
                supported_contexts=["*"],
            )
        except ImportError as e:
            logger.warning(f"Could not register HuggingFaceImageGenTool: {e}")

        # Gemini/Nano Banana Image Generation Tool (#96)
        try:
            from agents.tools.image_gen_gemini import GeminiImageGenTool

            self.register(
                name="image_gen_gemini",
                description="Generate images using Google Gemini (Nano Banana)",
                tool_class=GeminiImageGenTool,
                category="image",
                default_enabled=True,
                requires_api_key="GEMINI_API_KEY",
                supported_contexts=["*"],
            )
        except ImportError as e:
            logger.warning(f"Could not register GeminiImageGenTool: {e}")

        # Unstructured.io Document Extraction Tool (#102)
        try:
            from agents.tools.unstructured import UnstructuredTool

            self.register(
                name="unstructured_extract",
                description="Extract structured data from documents using Unstructured.io",
                tool_class=UnstructuredTool,
                category="data",
                default_enabled=True,
                requires_api_key="UNSTRUCTURED_API_KEY",
                supported_contexts=["document_rag", "document"],
            )
        except ImportError as e:
            logger.warning(f"Could not register UnstructuredTool: {e}")

        # Sports News Tool - PlainTextSports.com
        try:
            from agents.tools.sports_news import SportsNewsTool

            self.register(
                name="sports_news",
                description="Get live sports scores, schedules, and standings from PlainTextSports.com",
                tool_class=SportsNewsTool,
                category="search",
                default_enabled=True,
                supported_contexts=["*"],
            )
        except ImportError as e:
            logger.warning(f"Could not register SportsNewsTool: {e}")

        # Webpage Summarizer Tool (#109) - Fetch and summarize web pages
        try:
            from agents.tools.webpage_summarizer import WebpageSummarizerTool

            self.register(
                name="summarize_webpage",
                description="PREFERRED tool for summarizing web pages - use instead of visit_webpage when summaries are needed",
                tool_class=WebpageSummarizerTool,
                category="search",
                default_enabled=True,
                supported_contexts=["*"],
            )
        except ImportError as e:
            logger.warning(f"Could not register WebpageSummarizerTool: {e}")

        # Agent Skills Loader - read SKILL.md instructions and related files
        try:
            from agents.tools.skill_loader import SkillLoaderTool

            self.register(
                name="load_skill",
                description="Load Agent Skills instructions or resources from SKILL.md",
                tool_class=SkillLoaderTool,
                category="skills",
                default_enabled=True,
                supported_contexts=["*"],
            )
        except ImportError as e:
            logger.warning(f"Could not register SkillLoaderTool: {e}")

        # Project Document Search - search indexed project documents
        try:
            from agents.tools.project_document_search import (
                ProjectDocumentSearchTool,
                create_project_document_search_tool,
            )

            self.register(
                name="search_project_documents",
                description="Search through documents in this project's knowledge base",
                tool_class=ProjectDocumentSearchTool,
                category="search",
                default_enabled=True,
                requires_api_key="GEMINI_API_KEY",
                supported_contexts=["chat", "document_rag"],
                factory=create_project_document_search_tool,
            )
        except ImportError as e:
            logger.warning(f"Could not register ProjectDocumentSearchTool: {e}")

    def register(
        self,
        name: str,
        description: str,
        tool_class: type[Tool],
        category: str,
        default_enabled: bool = True,
        requires_api_key: Optional[str] = None,
        supported_contexts: Optional[list[str]] = None,
        factory: Optional[Callable[..., Tool]] = None,
    ) -> None:
        """
        Register a tool with the registry.

        Args:
            name: Unique tool identifier
            description: Human-readable description
            tool_class: The smolagents Tool class
            category: Tool category for grouping
            default_enabled: Whether enabled by default
            requires_api_key: Environment variable name for required API key
            supported_contexts: List of contexts where tool is available
            factory: Optional factory function for custom instantiation
        """
        self._tools[name] = ToolDefinition(
            name=name,
            description=description,
            tool_class=tool_class,
            category=category,
            default_enabled=default_enabled,
            requires_api_key=requires_api_key,
            supported_contexts=supported_contexts or ["*"],
            factory=factory,
        )
        logger.debug(f"Registered tool: {name}")

    def get_tool_definition(self, name: str) -> Optional[ToolDefinition]:
        """Get tool definition by name."""
        return self._tools.get(name)

    def list_tools(self) -> list[ToolDefinition]:
        """List all registered tools."""
        return list(self._tools.values())

    def get_enabled_tools(
        self,
        project: "Project",
        context: Optional[str] = None,
    ) -> list[Tool]:
        """
        Get instantiated tools that are enabled for a project.

        Args:
            project: Project to check enablement for
            context: Optional context to filter tools

        Returns:
            List of instantiated Tool objects
        """
        from agents.models import ProjectToolConfig

        # Get project-specific overrides
        overrides = {
            config.tool_name: config
            for config in ProjectToolConfig.objects.filter(project=project)
        }

        enabled_tools = []
        for name, definition in self._tools.items():
            # Check project override, fall back to default
            if name in overrides:
                if not overrides[name].is_enabled:
                    continue
                config_overrides = overrides[name].config_overrides
            else:
                if not definition.default_enabled:
                    continue
                config_overrides = {}

            # Check context compatibility
            if context and context not in definition.supported_contexts:
                if "*" not in definition.supported_contexts:
                    continue

            # Check API key availability
            if definition.requires_api_key:
                if not os.getenv(definition.requires_api_key):
                    logger.warning(
                        f"Tool {name} requires {definition.requires_api_key} "
                        "but it's not set"
                    )
                    continue

            # Instantiate tool
            try:
                tool = self._create_tool(definition, config_overrides, project=project)
                if tool is not None:
                    enabled_tools.append(tool)
            except Exception as e:
                logger.error(f"Failed to instantiate tool {name}: {e}")

        return enabled_tools

    def get_tool_status(self, project: "Project") -> list[dict[str, Any]]:
        """
        Get status of all tools for a project.

        Returns:
            List of dicts with tool name, enabled status, and metadata
        """
        from agents.models import ProjectToolConfig

        overrides = {
            config.tool_name: config
            for config in ProjectToolConfig.objects.filter(project=project)
        }

        result = []
        for name, definition in self._tools.items():
            # Determine enabled status
            if name in overrides:
                is_enabled = overrides[name].is_enabled
                config_overrides = overrides[name].config_overrides
            else:
                is_enabled = definition.default_enabled
                config_overrides = {}

            # Check if API key is available
            api_key_available = True
            if definition.requires_api_key:
                api_key_available = bool(os.getenv(definition.requires_api_key))

            result.append(
                {
                    "name": name,
                    "description": definition.description,
                    "category": definition.category,
                    "is_enabled": is_enabled,
                    "default_enabled": definition.default_enabled,
                    "requires_api_key": definition.requires_api_key,
                    "api_key_available": api_key_available,
                    "supported_contexts": definition.supported_contexts,
                    "config_overrides": config_overrides,
                }
            )

        return result

    def _create_tool(
        self,
        definition: ToolDefinition,
        config: dict[str, Any],
        project: "Project | None" = None,
    ) -> Tool | None:
        """
        Create a tool instance with configuration.

        Args:
            definition: Tool definition from registry
            config: Configuration overrides for the tool
            project: Project context for tools that need it

        Returns:
            Tool instance, or None if the factory returns None
            (e.g., when a tool requires project context but none is provided)
        """
        if definition.factory:
            return definition.factory(project=project, **config)
        return definition.tool_class(**config) if config else definition.tool_class()
