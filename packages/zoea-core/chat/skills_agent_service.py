"""
Skills Agent Service for executing Agent Skills.

Implements the Agent Skills Protocol by explicitly loading SKILL.md instructions
and using them to guide the agent's processing of event data.

Supports two execution modes:
1. Standard mode: Uses ToolRegistry tools with project scope
2. Harness mode: Uses SkillExecutionHarness for isolated execution with guardrails
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from asgiref.sync import sync_to_async
from smolagents import CodeAgent, LiteLLMModel, OpenAIServerModel

from agents.registry import ToolRegistry
from agents.skills.registry import SkillMetadata, SkillRegistry, SkillRegistryError
from agents.tools.base import ZoeaTool
from agents.tools.output_collections import InMemoryArtifactCollection
from llm_providers import get_provider_api_key, resolve_llm_config

if TYPE_CHECKING:
    from smolagents import Tool

    from events.harness import SkillExecutionHarness
    from projects.models import Project

logger = logging.getLogger(__name__)


@dataclass
class LoadedSkill:
    """A skill that has been loaded with its full instructions."""

    name: str
    metadata: SkillMetadata
    instructions: str  # Full SKILL.md content


@dataclass
class SkillArtifactData:
    """Artifact data produced by skill execution."""

    type: str  # "image", "code", "document", "diagram", "markdown"
    path: str
    mime_type: str | None = None
    title: str | None = None
    language: str | None = None
    content: str | None = None


@dataclass
class SkillsAgentResponse:
    """Response from the skills agent."""

    response: str
    skills_used: list[str]
    tools_called: list[str]
    steps: list[dict[str, Any]]
    telemetry: dict[str, Any]
    artifacts: list[SkillArtifactData] = field(default_factory=list)
    audit_log: dict[str, Any] | None = None  # Populated when using harness mode


class SkillsAgentService:
    """
    Agent service that explicitly loads and executes specified skills.

    Unlike ToolAgentService which has tools available for the agent to
    discover, this service:

    1. Loads full SKILL.md instructions for each specified skill
    2. Builds a comprehensive system prompt with all skill instructions
    3. Processes inputs using the skills as guidance

    This follows the Agent Skills Protocol where skills are loaded at
    activation time and their full instructions are included in context.

    Example:
        service = SkillsAgentService(
            project=project,
            skill_names=["extract-lead-data", "crm-sync"],
        )
        response = await service.process(
            event_type="email_received",
            event_data={
                "subject": "New inquiry",
                "body": "Hi, I'm interested in...",
                "sender": "john@example.com",
            },
        )
        print(response.response)
        print(f"Skills used: {response.skills_used}")
    """

    def __init__(
        self,
        *,
        project: Project | None = None,
        skill_names: list[str],
        tools: list[Tool] | None = None,
        context: str = "events",
        max_steps: int = 10,
        custom_instructions: str | None = None,
        harness: SkillExecutionHarness | None = None,
    ):
        """
        Initialize the skills agent service.

        Args:
            project: Project for LLM configuration and tool resolution
            skill_names: List of skill names to load (from SkillRegistry)
            tools: Optional explicit list of tools (overrides registry lookup)
            context: Context for tool filtering
            max_steps: Maximum steps the agent can take
            custom_instructions: Additional instructions to append to system prompt
            harness: Optional SkillExecutionHarness for isolated execution.
                     When provided, uses scoped tools with guardrails instead
                     of the standard ToolRegistry tools.
        """
        self.project = project
        self.skill_names = skill_names
        self.max_steps = max_steps
        self.custom_instructions = custom_instructions
        self.harness = harness

        # Resolve LLM configuration from project or app defaults
        self.config = resolve_llm_config(project=project)
        self.model_id = self.config.model_id
        self.provider_name = self.config.provider

        # Load skills from registry
        self.loaded_skills = self._load_skills()
        self.skills_used = [s.name for s in self.loaded_skills]

        # Get tools - either from harness, explicit list, or registry
        if harness is not None:
            # Use scoped tools from the harness
            from events.scoped_tools import create_scoped_tools

            tools = create_scoped_tools(harness)
            logger.debug(
                "Using harness with scoped tools: %s",
                [t.name for t in tools],
            )
        elif tools is None:
            # Get tools from registry
            registry = ToolRegistry.get_instance()
            tools = registry.get_enabled_tools(project, context=context)

        self.tools = tools
        self.tool_names = [t.name for t in tools]

        logger.debug(
            "SkillsAgentService initialized with provider=%s, model=%s, "
            "skills=%s, tools=%s, harness=%s",
            self.provider_name,
            self.model_id,
            self.skills_used,
            self.tool_names,
            "enabled" if harness else "disabled",
        )

        # Create shared artifact collection for tools to write to
        self._artifact_collection = InMemoryArtifactCollection()

        # Set artifact collection on tools that support it (only for non-harness mode)
        if harness is None:
            for tool in self.tools:
                if isinstance(tool, ZoeaTool):
                    tool.output_collection = self._artifact_collection

        # Create the underlying LLM model
        self.model = self._create_smolagents_model(project)

        # Build and store the system prompt
        self._system_prompt = self._build_system_prompt()

        # Create CodeAgent with tools
        self.agent = CodeAgent(
            tools=tools,
            model=self.model,
            max_steps=max_steps,
            verbosity_level=1,
        )

    def _load_skills(self) -> list[LoadedSkill]:
        """
        Load SKILL.md content for each specified skill.

        Returns:
            List of LoadedSkill objects with full instructions.

        Raises:
            SkillRegistryError: If a skill cannot be found or loaded.
        """
        registry = SkillRegistry.get_instance()
        loaded: list[LoadedSkill] = []

        for name in self.skill_names:
            metadata = registry.get_skill(name)
            if not metadata:
                logger.warning(f"Skill '{name}' not found in registry, skipping")
                continue

            try:
                instructions = registry.read_skill_file(name)
                loaded.append(
                    LoadedSkill(
                        name=name,
                        metadata=metadata,
                        instructions=instructions,
                    )
                )
                logger.debug(f"Loaded skill '{name}' ({len(instructions)} chars)")
            except SkillRegistryError as e:
                logger.warning(f"Failed to load skill '{name}': {e}")
                continue

        if not loaded:
            logger.warning(
                f"No skills loaded from requested: {self.skill_names}"
            )

        return loaded

    def _build_system_prompt(self) -> str:
        """
        Build the system prompt with loaded skill instructions.

        Follows the Agent Skills Protocol structure where each skill's
        full instructions are included in the context.
        """
        parts = [
            "You are an AI agent that processes events using specialized skills.",
            "You have been configured with the following skills to handle this event.",
            "",
            "## Loaded Skills",
            "",
        ]

        for skill in self.loaded_skills:
            parts.append(f"### Skill: {skill.name}")
            parts.append(f"**Description:** {skill.metadata.description}")
            parts.append("")
            parts.append("#### Instructions")
            parts.append("")
            parts.append(skill.instructions)
            parts.append("")
            parts.append("---")
            parts.append("")

        parts.append("## Processing Guidelines")
        parts.append("")
        parts.append(
            "1. Analyze the event data provided to determine which skills apply"
        )
        parts.append("2. Follow the skill instructions to process the data")
        parts.append(
            "3. Use available tools when needed to complete skill tasks"
        )
        parts.append(
            "4. Return structured results that can be stored as artifacts"
        )
        parts.append("")

        if self.custom_instructions:
            parts.append("## Additional Instructions")
            parts.append("")
            parts.append(self.custom_instructions)
            parts.append("")

        return "\n".join(parts)

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
            endpoint = self.config.local_endpoint or "http://localhost:11434/v1"
            return OpenAIServerModel(
                model_id=self.model_id,
                api_base=endpoint,
                api_key="not-needed",
            )

        else:
            return LiteLLMModel(model_id=f"{provider}/{self.model_id}")

    async def process(
        self,
        event_type: str,
        event_data: dict[str, Any],
        context: dict[str, Any] | None = None,
    ) -> SkillsAgentResponse:
        """
        Process event data using loaded skills.

        Args:
            event_type: Type of event (e.g., "email_received", "document_created")
            event_data: Event payload with relevant data
            context: Optional additional context (e.g., project info, user info)

        Returns:
            SkillsAgentResponse with results and telemetry
        """
        result = await sync_to_async(self._run_agent)(
            event_type, event_data, context
        )
        return result

    def _run_agent(
        self,
        event_type: str,
        event_data: dict[str, Any],
        context: dict[str, Any] | None = None,
    ) -> SkillsAgentResponse:
        """
        Run the agent synchronously.

        Args:
            event_type: Type of event
            event_data: Event payload
            context: Optional additional context

        Returns:
            SkillsAgentResponse with results and telemetry
        """
        try:
            # Clear artifact collection before each run
            self._artifact_collection.clear()

            # Build the user message with event data
            message = self._build_event_message(event_type, event_data, context)

            # Inject our system prompt into the agent
            default_prompt = self.agent.prompt_templates.get("system_prompt", "")
            self.agent.prompt_templates["system_prompt"] = (
                f"{default_prompt}\n\n{self._system_prompt}"
            )

            # Run the agent
            result = self.agent.run(message)

            # Extract telemetry
            telemetry = self._extract_telemetry(result)

            # Collect artifacts
            artifacts = self._collect_artifacts()

            # Get response text
            if hasattr(result, "content"):
                response_text = str(result.content)
            else:
                response_text = str(result)

            # Get audit log if using harness
            audit_log = None
            if self.harness is not None:
                audit_log = self.harness.get_audit_log()

            return SkillsAgentResponse(
                response=response_text,
                skills_used=self.skills_used,
                tools_called=telemetry.get("tools_called", []),
                steps=telemetry.get("steps", []),
                telemetry=telemetry,
                artifacts=artifacts,
                audit_log=audit_log,
            )

        except Exception as e:
            logger.error(f"SkillsAgentService error: {e}", exc_info=True)

            # Still capture audit log on error
            audit_log = None
            if self.harness is not None:
                audit_log = self.harness.get_audit_log()

            return SkillsAgentResponse(
                response=f"Error processing event: {str(e)}",
                skills_used=self.skills_used,
                tools_called=[],
                steps=[],
                telemetry={"error": str(e)},
                audit_log=audit_log,
            )

    def _build_event_message(
        self,
        event_type: str,
        event_data: dict[str, Any],
        context: dict[str, Any] | None = None,
    ) -> str:
        """Build the user message containing event data."""
        parts = [
            f"## Event: {event_type}",
            "",
            "### Event Data",
            "",
        ]

        # Format event data as readable key-value pairs
        for key, value in event_data.items():
            if isinstance(value, str) and len(value) > 500:
                # Truncate long strings with indication
                parts.append(f"**{key}:**")
                parts.append(f"```\n{value[:500]}...\n[truncated, {len(value)} chars total]\n```")
            elif isinstance(value, (list, dict)):
                import json
                parts.append(f"**{key}:** `{json.dumps(value)}`")
            else:
                parts.append(f"**{key}:** {value}")
            parts.append("")

        if context:
            parts.append("### Context")
            parts.append("")
            for key, value in context.items():
                parts.append(f"**{key}:** {value}")
            parts.append("")

        parts.append("---")
        parts.append("")
        parts.append(
            "Please process this event using the loaded skills. "
            "Follow the skill instructions to extract relevant information, "
            "perform any required actions, and return structured results."
        )

        return "\n".join(parts)

    def _collect_artifacts(self) -> list[SkillArtifactData]:
        """Collect artifacts from the artifact collection."""
        artifacts: list[SkillArtifactData] = []

        for artifact in self._artifact_collection.artifacts:
            artifacts.append(
                SkillArtifactData(
                    type=artifact.type,
                    path=artifact.path,
                    mime_type=artifact.mime_type,
                    title=artifact.title,
                    language=artifact.language,
                    content=artifact.content,
                )
            )

        return artifacts

    def _extract_telemetry(self, run_result: Any) -> dict[str, Any]:
        """Extract telemetry from a smolagents run result."""
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
            getattr(token_usage_obj, "dict", lambda: None)()
            if token_usage_obj
            else None
        )

        return {
            "state": state,
            "skills_loaded": self.skills_used,
            "timing": (
                getattr(timing_obj, "dict", lambda: None)()
                if timing_obj
                else None
            ),
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
