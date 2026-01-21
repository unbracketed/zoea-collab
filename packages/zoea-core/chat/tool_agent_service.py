"""
Tool-enabled Chat Agent Service using smolagents.

Provides a chat agent with access to tools from the ToolRegistry,
enabling capabilities like web search, image analysis, and more.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from asgiref.sync import sync_to_async
from smolagents import CodeAgent, LiteLLMModel, OpenAIServerModel

from agents.registry import ToolRegistry
from agents.tools.base import (
    ToolArtifact,
    ZoeaTool,
    extract_artifacts_from_output,
)
from agents.tools.output_collections import InMemoryArtifactCollection
from chat.code_block_extractor import extract_markdown_tables
from llm_providers import get_provider_api_key, resolve_llm_config

if TYPE_CHECKING:
    from smolagents import Tool

    from projects.models import Project

logger = logging.getLogger(__name__)


@dataclass
class ToolArtifactData:
    """Artifact data extracted from tool output."""

    type: str  # "image", "code", "document", "diagram", "markdown"
    path: str
    mime_type: str | None = None
    title: str | None = None
    language: str | None = None
    content: str | None = None  # For inline content (markdown tables, etc.)


@dataclass
class ToolAgentResponse:
    """Response from the tool-enabled agent."""

    response: str
    tools_called: list[str]
    steps: list[dict[str, Any]]
    telemetry: dict[str, Any]
    artifacts: list[ToolArtifactData] = field(default_factory=list)


class ToolAgentService:
    """
    smolagents CodeAgent configured with tools from ToolRegistry.

    This service enables the chat agent to use registered tools like
    WebSearchTool, VisitWebpageTool, ImageAnalyzerTool, etc.

    Example:
        service = ToolAgentService(project=project)
        response = await service.chat("Search for the latest AI news")
        print(response.response)
        print(f"Tools called: {response.tools_called}")
    """

    def __init__(
        self,
        *,
        project: Project | None = None,
        tools: list[Tool] | None = None,
        context: str = "chat",
        max_steps: int = 6,
    ):
        """
        Initialize the tool-enabled agent service.

        Args:
            project: Project for LLM configuration and tool resolution
            tools: Optional explicit list of tools (overrides registry lookup)
            context: Context for tool filtering (e.g., "chat", "excalidraw")
            max_steps: Maximum steps the agent can take
        """
        self.project = project
        self.max_steps = max_steps

        # Resolve LLM configuration from project or app defaults
        self.config = resolve_llm_config(project=project)
        self.model_id = self.config.model_id
        self.provider_name = self.config.provider

        # Get tools from registry if not provided
        if tools is None:
            registry = ToolRegistry.get_instance()
            tools = registry.get_enabled_tools(project, context=context)

        self.tools = tools
        self.tool_names = [t.name for t in tools]

        logger.debug(
            "ToolAgentService initialized with provider=%s, model=%s, tools=%s",
            self.provider_name,
            self.model_id,
            self.tool_names,
        )

        # Create shared artifact collection for tools to write to
        self._artifact_collection = InMemoryArtifactCollection()

        # Set artifact collection on tools that support it (ZoeaTool instances)
        for tool in self.tools:
            if isinstance(tool, ZoeaTool):
                tool.output_collection = self._artifact_collection
                logger.debug(
                    f"Set artifact collection on ZoeaTool: {tool.name}"
                )

        # Create the underlying LLM model
        self.model = self._create_smolagents_model(project)

        # Create CodeAgent with tools
        self.agent = CodeAgent(
            tools=tools,
            model=self.model,
            max_steps=max_steps,
            verbosity_level=1,
        )

        # Track the last run result for telemetry
        self._last_run_result = None

    def _create_smolagents_model(self, project: Project | None):
        """
        Create the appropriate smolagents model based on provider configuration.

        Args:
            project: Project for API key resolution

        Returns:
            smolagents Model instance
        """
        provider = self.provider_name.lower()

        if provider == "openai":
            api_key = get_provider_api_key("openai", project=project)
            return LiteLLMModel(
                model_id=f"openai/{self.model_id}",
                api_key=api_key,
            )

        elif provider == "gemini":
            api_key = get_provider_api_key("gemini", project=project)
            return LiteLLMModel(
                model_id=f"gemini/{self.model_id}",
                api_key=api_key,
            )

        elif provider == "local":
            # Local model via OpenAI-compatible endpoint
            endpoint = self.config.local_endpoint or "http://localhost:11434/v1"
            return OpenAIServerModel(
                model_id=self.model_id,
                api_base=endpoint,
                api_key="not-needed",
            )

        else:
            # Default to LiteLLM with provider prefix
            return LiteLLMModel(model_id=f"{provider}/{self.model_id}")

    async def chat(
        self,
        message: str,
        system_prompt: str | None = None,
    ) -> ToolAgentResponse:
        """
        Send a message to the agent and get a response with tool usage.

        Args:
            message: User message to process
            system_prompt: Optional system prompt for the agent

        Returns:
            ToolAgentResponse with response text and telemetry
        """
        # Run agent synchronously (smolagents doesn't have native async)
        result = await sync_to_async(self._run_agent)(message, system_prompt)
        return result

    def _run_agent(
        self,
        message: str,
        system_prompt: str | None = None,
    ) -> ToolAgentResponse:
        """
        Run the agent synchronously.

        Args:
            message: User message to process
            system_prompt: Optional system prompt

        Returns:
            ToolAgentResponse with response and telemetry
        """
        try:
            # Clear artifact collection before each run
            self._artifact_collection.clear()

            # Append custom context to the default system prompt (don't replace it!)
            # The default prompt contains critical tool descriptions and instructions
            if system_prompt:
                default_prompt = self.agent.prompt_templates.get("system_prompt", "")
                self.agent.prompt_templates["system_prompt"] = (
                    f"{default_prompt}\n\n"
                    f"## Additional Context\n{system_prompt}"
                )

            # Run the agent
            result = self.agent.run(message)
            self._last_run_result = result

            # Extract telemetry
            telemetry = self._extract_telemetry(result)

            # Collect artifacts from:
            # 1. Direct tool creation via ZoeaTool.create_artifact()
            # 2. Legacy JSON parsing from tool outputs
            # 3. Markdown tables from tool outputs
            artifacts = self._collect_all_artifacts(result)

            # Get response text
            if hasattr(result, "content"):
                response_text = str(result.content)
            else:
                response_text = str(result)

            return ToolAgentResponse(
                response=response_text,
                tools_called=telemetry.get("tools_called", []),
                steps=telemetry.get("steps", []),
                telemetry=telemetry,
                artifacts=artifacts,
            )

        except Exception as e:
            logger.error(f"ToolAgentService error: {e}", exc_info=True)
            return ToolAgentResponse(
                response=f"I encountered an error while processing your request: {str(e)}",
                tools_called=[],
                steps=[],
                telemetry={"error": str(e)},
            )

    def _collect_all_artifacts(self, run_result: Any) -> list[ToolArtifactData]:
        """
        Collect all artifacts from multiple sources.

        Sources:
        1. Direct tool creation via ZoeaTool.create_artifact() - stored in artifact collection
        2. Legacy JSON parsing from tool outputs (ARTIFACT_OUTPUT_SCHEMA)
        3. Markdown tables from tool outputs

        Args:
            run_result: The result from agent.run()

        Returns:
            List of ToolArtifactData objects (deduplicated by path)
        """
        artifacts: list[ToolArtifactData] = []
        seen_paths: set[str] = set()

        # 1. Collect from artifact collection (ZoeaTool.create_artifact())
        for artifact in self._artifact_collection.artifacts:
            if artifact.path not in seen_paths:
                artifacts.append(
                    ToolArtifactData(
                        type=artifact.type,
                        path=artifact.path,
                        mime_type=artifact.mime_type,
                        title=artifact.title,
                        language=artifact.language,
                        content=artifact.content,
                    )
                )
                seen_paths.add(artifact.path)
                logger.debug(
                    f"Collected artifact from collection: type={artifact.type} path={artifact.path}"
                )

        # 2 & 3. Extract from step outputs (legacy JSON + markdown tables)
        step_artifacts = self._extract_artifacts_from_steps(run_result)
        for artifact in step_artifacts:
            if artifact.path not in seen_paths:
                artifacts.append(artifact)
                seen_paths.add(artifact.path)

        logger.debug(f"Total artifacts collected: {len(artifacts)}")
        return artifacts

    def _extract_artifacts_from_steps(self, run_result: Any) -> list[ToolArtifactData]:
        """
        Extract artifacts from tool outputs in the run result (legacy approach).

        Scans through all tool call outputs looking for:
        1. Structured artifact metadata (JSON with ARTIFACT_OUTPUT_SCHEMA)
        2. Markdown tables (for data display artifacts)

        Note: This is the legacy extraction method. Tools that extend ZoeaTool
        should use create_artifact() instead, which writes directly to the
        artifact collection.

        Args:
            run_result: The result from agent.run()

        Returns:
            List of ToolArtifactData objects
        """
        artifacts = []

        if run_result is None:
            return artifacts

        steps = getattr(run_result, "steps", None) or []
        logger.debug(f"Extracting artifacts from {len(steps)} steps")

        for i, step in enumerate(steps):
            # Get outputs from step - handle both dict and object formats
            tool_outputs = self._get_step_field(step, "tool_outputs", "observations")
            logger.debug(f"Step {i}: found {len(tool_outputs)} outputs to check")

            for output in tool_outputs:
                if not isinstance(output, str):
                    # Try to convert to string
                    output = str(output) if output else ""

                if not output:
                    continue

                logger.debug(f"Checking output: {output[:100]}...")

                # Try to extract JSON artifacts from the output
                result_text, artifact_list = extract_artifacts_from_output(output)

                for artifact_data in artifact_list:
                    try:
                        artifacts.append(
                            ToolArtifactData(
                                type=artifact_data.get("type", "unknown"),
                                path=artifact_data.get("path", ""),
                                mime_type=artifact_data.get("mime_type"),
                                title=artifact_data.get("title"),
                                language=artifact_data.get("language"),
                            )
                        )
                    except (KeyError, TypeError) as e:
                        logger.warning(f"Failed to parse artifact data: {e}")

                # Also extract markdown tables as artifacts
                self._extract_markdown_artifacts(output, artifacts)

        logger.debug(f"Total artifacts extracted: {len(artifacts)}")
        return artifacts

    def _get_step_field(self, step: Any, *field_names: str) -> list:
        """
        Get a field from a step, handling both dict and object formats.

        Args:
            step: Step object or dict
            field_names: Field names to try (returns first non-empty)

        Returns:
            List of outputs from the step
        """
        results = []

        for field_name in field_names:
            # Try dict access
            if isinstance(step, dict):
                value = step.get(field_name)
            else:
                # Try attribute access for object-style steps
                value = getattr(step, field_name, None)

            if value:
                if isinstance(value, list):
                    results.extend(value)
                elif isinstance(value, str):
                    results.append(value)

        return results

    def _extract_markdown_artifacts(
        self, text: str, artifacts: list[ToolArtifactData]
    ) -> None:
        """
        Extract markdown tables from text and add as artifacts.

        Args:
            text: Text content to scan for markdown tables
            artifacts: List to append artifacts to
        """
        tables = extract_markdown_tables(text)
        for table in tables:
            # Create a unique identifier for the table content
            content_hash = hash(table.content) & 0xFFFFFF  # 6 hex chars
            artifacts.append(
                ToolArtifactData(
                    type="markdown",
                    path=f"_inline_table_{content_hash:06x}",  # Virtual path for inline content
                    mime_type="text/markdown",
                    title=self._extract_table_title(text, table.start_pos),
                    language="markdown",
                    content=table.content,  # Store inline content
                )
            )

    def _extract_table_title(self, text: str, table_start: int) -> str | None:
        """
        Try to extract a title from text before the table.

        Looks for markdown headers (###) before the table position.
        """
        # Look at text before the table
        before_text = text[:table_start].strip()
        lines = before_text.split("\n")

        # Look for a header in the last few lines
        for line in reversed(lines[-5:]):
            line = line.strip()
            if line.startswith("#"):
                # Extract header text
                return line.lstrip("#").strip()

        return None

    def _extract_telemetry(self, run_result: Any) -> dict[str, Any]:
        """
        Extract telemetry from a smolagents run result.

        Args:
            run_result: The result from agent.run()

        Returns:
            Dictionary with telemetry data
        """
        if run_result is None:
            return {"state": "unknown"}

        steps = getattr(run_result, "steps", None) or []
        state = getattr(run_result, "state", "unknown")

        timing_obj = getattr(run_result, "timing", None)
        token_usage_obj = getattr(run_result, "token_usage", None)

        tools_called = []
        step_summaries = []
        error_count = 0

        for i, step in enumerate(steps):
            if not isinstance(step, dict):
                continue

            step_summary = {"step": i + 1}

            if step.get("error"):
                error_count += 1
                step_summary["error"] = str(step.get("error"))

            for tool_call in step.get("tool_calls") or []:
                try:
                    name = tool_call.get("function", {}).get("name")
                except AttributeError:
                    name = None
                if name:
                    tools_called.append(str(name))
                    step_summary["tool"] = name

            step_summaries.append(step_summary)

        token_usage = (
            getattr(token_usage_obj, "dict", lambda: None)() if token_usage_obj else None
        )

        return {
            "state": state,
            "timing": getattr(timing_obj, "dict", lambda: None)() if timing_obj else None,
            "token_usage": token_usage,
            "tools_called": tools_called,
            "steps": step_summaries,
            "step_count": len(steps),
            "error_count": error_count,
        }

    @property
    def model_used(self) -> str:
        """Return the model ID being used."""
        return self.model_id
