"""
Request and response schemas for the Agents API.
"""

from typing import Any

from ninja import Schema


class ToolInfo(Schema):
    """Tool information response."""

    name: str
    description: str
    category: str
    is_enabled: bool
    default_enabled: bool
    requires_api_key: str | None = None
    api_key_available: bool = True
    supported_contexts: list[str]
    config_overrides: dict[str, Any] = {}


class ToolListResponse(Schema):
    """Response for listing tools."""

    tools: list[ToolInfo]
    project_id: int


class ToolEnableRequest(Schema):
    """Request to enable/disable a tool."""

    project_id: int


class ToolConfigUpdateRequest(Schema):
    """Request to update tool configuration."""

    project_id: int
    config: dict[str, Any]


class ToolStatusResponse(Schema):
    """Response after tool status change."""

    tool_name: str
    is_enabled: bool
    message: str


class RoutedChatRequest(Schema):
    """Request for context-aware routed chat."""

    message: str
    project_id: int
    workspace_id: int

    # Context for routing
    view_type: str = "chat"
    document_id: int | None = None
    document_ids: list[int] | None = None
    folder_id: int | None = None
    collection_id: int | None = None
    rag_session_id: str | None = None

    # Optional capabilities request
    requested_capabilities: list[str] | None = None

    # Options
    include_routing_info: bool = False


class RoutingInfo(Schema):
    """Information about how the request was routed."""

    agent_type: str
    tools_available: list[str]
    context_type: str


class ToolArtifact(Schema):
    """
    Artifact metadata extracted from tool output.

    When tools generate files (images, code, documents), they can include
    artifact metadata in their output. This schema represents that metadata
    for API responses.
    """

    type: str  # "image", "code", "document", "diagram"
    path: str  # File system path to the artifact
    mime_type: str | None = None  # MIME type (e.g., "image/png")
    title: str | None = None  # Display title
    language: str | None = None  # Programming language for code
    document_id: int | None = None  # ID if saved to Document library


class ToolExecutionResult(Schema):
    """Result of a single tool execution including any artifacts."""

    tool_name: str
    result: str
    artifacts: list[ToolArtifact] = []
    success: bool = True
    error_message: str | None = None


class RoutedChatResponse(Schema):
    """Response from routed chat."""

    response: str
    agent_type: str
    routing_info: RoutingInfo | None = None
    tool_results: list[ToolExecutionResult] = []
    artifacts: list[ToolArtifact] = []  # Aggregated artifacts from all tools
