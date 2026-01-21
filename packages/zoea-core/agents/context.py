from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from documents.models import Document
    from projects.models import Project
    from workspaces.models import Workspace


class AgentType(str, Enum):
    """Available agent types."""

    CHAT = "chat"
    DOCUMENT_RAG = "document_rag"
    DEEP_RESEARCH = "deep_research"
    EXCALIDRAW = "excalidraw"


class ViewContext(str, Enum):
    """Frontend view contexts for routing."""

    CHAT = "chat"
    DOCUMENT_DETAIL = "document_detail"
    DOCUMENT_EDITOR = "document_editor"
    FOLDER_VIEW = "folder_view"
    SEARCH = "search"
    CANVAS = "canvas"
    EXCALIDRAW = "excalidraw"
    CLIPBOARD = "clipboard"


@dataclass
class AgentContext:
    """
    Request context for agent routing decisions.

    Captures all relevant information about the current request
    to determine which agent and tools to use.

    Example:
        context = AgentContext(
            project=project,
            workspace=workspace,
            view_type=ViewContext.DOCUMENT_DETAIL,
            document=document,
        )
        result = router.route(context)
    """

    # Required context
    project: "Project"
    workspace: "Workspace"

    # View context
    view_type: ViewContext = ViewContext.CHAT

    # Document context (optional)
    document: Optional["Document"] = None
    document_ids: Optional[list[int]] = None
    folder_id: Optional[int] = None
    collection_id: Optional[int] = None

    # Session context
    rag_session_id: Optional[str] = None

    # User intent hints (from frontend)
    requested_capabilities: Optional[list[str]] = field(default_factory=list)

    @property
    def document_type(self) -> Optional[str]:
        """Get the document type name if a document is set."""
        if self.document:
            # Get the most specific subclass name
            for attr in ["excalidrawdiagram", "yooptadocument", "markdown", "image"]:
                if hasattr(self.document, attr):
                    return attr.replace("diagram", "").title()
            return type(self.document).__name__
        return None

    @property
    def is_multi_document(self) -> bool:
        """Check if context includes multiple documents."""
        return bool(self.document_ids and len(self.document_ids) > 1)

    @property
    def context_type(self) -> str:
        """Return a context type string for tool filtering."""
        if self.document_type == "Excalidraw":
            return "excalidraw"
        if self.rag_session_id or self.is_multi_document:
            return "document_rag"
        if self.folder_id:
            return "folder"
        if self.collection_id:
            return "collection"
        if "deep_research" in (self.requested_capabilities or []):
            return "research"
        return "chat"


@dataclass
class AgentRouteResult:
    """Result of agent routing."""

    agent_type: AgentType
    tools: list  # List of smolagents Tool instances
    config: dict = field(default_factory=dict)
