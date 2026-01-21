"""
Base classes and utilities for agent tools.

Provides common functionality for all smolagents tools in ZoeaStudio.

Key Classes:
    - ZoeaTool: Base class for Zoea tools with artifact creation capabilities
    - OutputCollection: Protocol for collections that receive tool outputs
    - TelemetryMixin: Mixin for telemetry tracking
"""

from __future__ import annotations

import json
import logging
import time
from abc import ABC
from collections.abc import Callable
from dataclasses import dataclass, field
from functools import wraps
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

from smolagents import Tool

# =============================================================================
# Artifact Output Schema for Tools
# =============================================================================
# This schema defines a standard format for tools that produce artifacts
# (images, code files, documents, etc.) that should be saved to the document
# library. Tools using this schema should set output_type = "object".

ARTIFACT_OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "result": {
            "type": "string",
            "description": "Human-readable result message",
        },
        "artifacts": {
            "type": "array",
            "description": "List of artifacts created by the tool",
            "items": {
                "type": "object",
                "properties": {
                    "type": {
                        "type": "string",
                        "enum": ["image", "code", "document", "diagram"],
                        "description": "Type of artifact",
                    },
                    "path": {
                        "type": "string",
                        "description": "File system path to the artifact",
                    },
                    "mime_type": {
                        "type": "string",
                        "description": "MIME type of the artifact (e.g., image/png)",
                    },
                    "title": {
                        "type": "string",
                        "description": "Display title for the artifact",
                    },
                    "language": {
                        "type": "string",
                        "description": "Programming language for code artifacts",
                        "nullable": True,
                    },
                },
                "required": ["type", "path"],
            },
        },
    },
    "required": ["result"],
}


def create_artifact_output(
    result: str,
    artifacts: list[dict[str, Any]] | None = None,
) -> str:
    """
    Create a JSON string output conforming to ARTIFACT_OUTPUT_SCHEMA.

    Use this helper in tools that generate artifacts to ensure consistent
    output format that can be parsed by the artifact extraction system.

    Args:
        result: Human-readable result message
        artifacts: List of artifact dictionaries with keys:
            - type: "image", "code", "document", or "diagram"
            - path: File system path to the artifact
            - mime_type: MIME type (optional but recommended)
            - title: Display title (optional)
            - language: Programming language for code (optional)

    Returns:
        JSON string that can be parsed by extract_artifacts_from_output()

    Example:
        return create_artifact_output(
            result="Image generated successfully",
            artifacts=[{
                "type": "image",
                "path": "/media/generated/img_123.png",
                "mime_type": "image/png",
                "title": "A cozy coffee shop",
            }]
        )
    """
    output = {"result": result}
    if artifacts:
        output["artifacts"] = artifacts
    return json.dumps(output)


def extract_artifacts_from_output(output: str) -> tuple[str, list[dict[str, Any]]]:
    """
    Extract artifacts from a tool output string.

    Parses tool output to extract artifact metadata if present.
    Returns the result message and list of artifacts.

    Args:
        output: Tool output string (may be JSON or plain text)

    Returns:
        Tuple of (result_message, artifacts_list)
        - If output is valid artifact JSON: extracts result and artifacts
        - If output is plain text: returns (output, [])

    Example:
        result, artifacts = extract_artifacts_from_output(tool_output)
        for artifact in artifacts:
            # Create Document from artifact["path"]
            pass
    """
    if not output or not output.strip().startswith("{"):
        return output, []

    try:
        data = json.loads(output)
        if isinstance(data, dict) and "result" in data:
            result = data.get("result", "")
            artifacts = data.get("artifacts", [])
            return result, artifacts
    except (json.JSONDecodeError, TypeError):
        pass

    return output, []

if TYPE_CHECKING:
    from django.contrib.auth.models import User

    from agents.models import ToolExecutionLog

logger = logging.getLogger(__name__)


class TelemetryMixin:
    """
    Mixin for tools that provides telemetry tracking.

    Tracks call count, errors, and timing information.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.telemetry = {
            "calls": 0,
            "errors": 0,
            "total_duration_s": 0.0,
            "last_duration_s": None,
        }

    def record_call(self, duration_s: float, error: bool = False):
        """Record a tool call for telemetry."""
        self.telemetry["calls"] += 1
        self.telemetry["total_duration_s"] += duration_s
        self.telemetry["last_duration_s"] = duration_s
        if error:
            self.telemetry["errors"] += 1


# =============================================================================
# Output Collection Protocol
# =============================================================================


@dataclass
class ToolArtifact:
    """
    Artifact created by a tool during execution.

    This is the internal representation used by OutputCollection.
    It mirrors the structure in chat/tool_agent_service.py but is defined
    here to avoid circular imports.
    """

    type: str  # "image", "code", "document", "diagram", "markdown"
    path: str  # File path or virtual path for inline content
    mime_type: str | None = None
    title: str | None = None
    language: str | None = None
    content: str | None = None  # For inline content (markdown tables, etc.)
    metadata: dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class OutputCollection(Protocol):
    """
    Protocol for collections that receive tool-generated outputs.

    Tools can be instantiated with an OutputCollection to directly create
    artifacts during execution, rather than returning artifact metadata
    in their output string.

    Implementations might store artifacts in:
    - A conversation's artifact list (ConversationArtifactCollection)
    - A workspace's documents folder (WorkspaceDocumentCollection)
    - A temporary in-memory list for testing

    Example:
        class ConversationArtifactCollection:
            def __init__(self, conversation_id: int):
                self.conversation_id = conversation_id
                self._artifacts = []

            def add_artifact(self, artifact: ToolArtifact) -> None:
                self._artifacts.append(artifact)

            @property
            def artifacts(self) -> list[ToolArtifact]:
                return self._artifacts
    """

    def add_artifact(self, artifact: ToolArtifact) -> None:
        """Add an artifact to the collection."""
        ...

    @property
    def artifacts(self) -> list[ToolArtifact]:
        """Return all artifacts in the collection."""
        ...


# =============================================================================
# ZoeaTool Base Class
# =============================================================================


class ZoeaTool(Tool, TelemetryMixin, ABC):
    """
    Base class for Zoea tools with artifact creation capabilities.

    Extends smolagents Tool with:
    - Telemetry tracking via TelemetryMixin
    - Direct artifact creation via OutputCollection
    - Standard initialization pattern

    Tools that extend ZoeaTool can create artifacts directly during execution
    by calling self.create_artifact(). This is cleaner than encoding artifact
    metadata in the return string and parsing it later.

    Example:
        class MyImageTool(ZoeaTool):
            name = "my_image_tool"
            description = "Generates images"
            inputs = {"prompt": {"type": "string", "description": "Image prompt"}}
            output_type = "string"

            def forward(self, prompt: str) -> str:
                # Generate image and save to file...
                filepath = self._generate_image(prompt)

                # Create artifact directly
                self.create_artifact(
                    type="image",
                    path=str(filepath),
                    mime_type="image/png",
                    title=f"Generated: {prompt[:30]}",
                )

                return f"Image generated: {filepath.name}"
    """

    def __init__(
        self,
        *,
        output_collection: OutputCollection | None = None,
        **kwargs,
    ):
        """
        Initialize the ZoeaTool.

        Args:
            output_collection: Optional collection for storing generated artifacts.
                If provided, tools can call create_artifact() to add artifacts
                directly to this collection during execution.
            **kwargs: Passed to parent Tool class
        """
        # Initialize Tool first (smolagents Tool.__init__)
        Tool.__init__(self, **kwargs)
        # Then initialize TelemetryMixin
        TelemetryMixin.__init__(self)
        # Store output collection
        self._output_collection = output_collection

    @property
    def output_collection(self) -> OutputCollection | None:
        """Get the output collection, if one was provided."""
        return self._output_collection

    @output_collection.setter
    def output_collection(self, collection: OutputCollection | None) -> None:
        """Set the output collection (allows updating after initialization)."""
        self._output_collection = collection

    def create_artifact(
        self,
        *,
        type: str,
        path: str,
        mime_type: str | None = None,
        title: str | None = None,
        language: str | None = None,
        content: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        """
        Create an artifact in the output collection.

        Call this method during forward() execution to register artifacts
        (images, documents, code, etc.) that should be displayed to the user
        or saved to the document library.

        Args:
            type: Artifact type ("image", "code", "document", "diagram", "markdown")
            path: File path to the artifact, or virtual path for inline content
                  (e.g., "_inline_table_abc123" for markdown tables)
            mime_type: MIME type of the artifact (e.g., "image/png")
            title: Display title for the artifact
            language: Programming language for code artifacts
            content: Inline content (for markdown tables, code snippets, etc.)
            metadata: Additional metadata to store with the artifact

        Returns:
            True if artifact was created, False if no output collection available

        Example:
            # Create an image artifact
            self.create_artifact(
                type="image",
                path="/media/generated/img_123.png",
                mime_type="image/png",
                title="A cozy coffee shop",
            )

            # Create a markdown table artifact
            self.create_artifact(
                type="markdown",
                path="_inline_table_abc123",
                mime_type="text/markdown",
                title="NBA Scores",
                content="| Team | Score |\\n|------|-------|\\n| LAL | 110 |",
            )
        """
        if self._output_collection is None:
            logger.debug(
                f"Tool {self.name}: No output collection, artifact not created"
            )
            return False

        artifact = ToolArtifact(
            type=type,
            path=path,
            mime_type=mime_type,
            title=title,
            language=language,
            content=content,
            metadata=metadata or {},
        )

        self._output_collection.add_artifact(artifact)
        logger.debug(f"Tool {self.name}: Created artifact type={type} path={path}")
        return True

    def has_output_collection(self) -> bool:
        """Check if an output collection is available."""
        return self._output_collection is not None


def log_tool_execution(
    tool_name: str,
    organization=None,
    project=None,
    workspace=None,
    user: User | None = None,
    agent_name: str = "",
    input_summary: dict[str, Any] | None = None,
    output_summary: dict[str, Any] | None = None,
    duration_ms: int | None = None,
    success: bool = True,
    error_message: str = "",
) -> ToolExecutionLog | None:
    """
    Log a tool execution to the database.

    Args:
        tool_name: Name of the tool
        organization: Organization instance
        project: Project instance
        workspace: Workspace instance
        user: User who triggered the execution
        agent_name: Name of the agent that called the tool
        input_summary: Sanitized input parameters
        output_summary: Sanitized output
        duration_ms: Execution time in milliseconds
        success: Whether execution succeeded
        error_message: Error message if failed

    Returns:
        ToolExecutionLog instance or None if logging failed
    """
    if organization is None:
        logger.warning(f"Cannot log tool execution for {tool_name}: no organization")
        return None

    try:
        from agents.models import ToolExecutionLog

        return ToolExecutionLog.objects.create(
            organization=organization,
            project=project,
            workspace=workspace,
            user=user,
            tool_name=tool_name,
            agent_name=agent_name,
            input_summary=input_summary or {},
            output_summary=output_summary or {},
            duration_ms=duration_ms,
            success=success,
            error_message=error_message,
        )
    except Exception as e:
        logger.error(f"Failed to log tool execution for {tool_name}: {e}")
        return None


def with_telemetry(func: Callable) -> Callable:
    """
    Decorator to add telemetry tracking to a tool's forward method.

    Usage:
        class MyTool(Tool, TelemetryMixin):
            @with_telemetry
            def forward(self, query: str) -> str:
                ...
    """

    @wraps(func)
    def wrapper(self, *args, **kwargs):
        start = time.perf_counter()
        error = False
        try:
            result = func(self, *args, **kwargs)
            return result
        except Exception:
            error = True
            raise
        finally:
            duration = time.perf_counter() - start
            if hasattr(self, "record_call"):
                self.record_call(duration, error=error)

    return wrapper
