"""
Output collection implementations for tool artifact creation.

Provides concrete implementations of the OutputCollection protocol
for different contexts (in-memory, conversation, workspace, etc.).
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from .base import ToolArtifact

if TYPE_CHECKING:
    from chat.models import Conversation
    from projects.models import Workspace

logger = logging.getLogger(__name__)


class InMemoryArtifactCollection:
    """
    Simple in-memory collection for tool artifacts.

    This is the default implementation used when tools need artifact
    support but no persistent storage is required. Artifacts are stored
    in a list and can be retrieved after tool execution.

    Example:
        collection = InMemoryArtifactCollection()
        tool = MyTool(output_collection=collection)
        tool.forward(...)

        # Access artifacts created during execution
        for artifact in collection.artifacts:
            print(f"Created: {artifact.type} at {artifact.path}")
    """

    def __init__(self, context_id: str | int | None = None):
        """
        Initialize the collection.

        Args:
            context_id: Optional identifier for the context (conversation ID,
                        workspace ID, etc.). Useful for debugging.
        """
        self._artifacts: list[ToolArtifact] = []
        self.context_id = context_id

    def add_artifact(self, artifact: ToolArtifact) -> None:
        """Add an artifact to the collection."""
        self._artifacts.append(artifact)
        logger.debug(
            f"InMemoryArtifactCollection[{self.context_id}]: "
            f"Added {artifact.type} artifact at {artifact.path}"
        )

    @property
    def artifacts(self) -> list[ToolArtifact]:
        """Return all artifacts in the collection."""
        return self._artifacts

    def clear(self) -> None:
        """Clear all artifacts from the collection."""
        self._artifacts.clear()

    def __len__(self) -> int:
        """Return the number of artifacts in the collection."""
        return len(self._artifacts)

    def __iter__(self):
        """Iterate over artifacts."""
        return iter(self._artifacts)


class ConversationArtifactCollection(InMemoryArtifactCollection):
    """
    Collection that associates artifacts with a conversation.

    Extends InMemoryArtifactCollection with conversation context.
    Future versions may persist artifacts to the conversation's
    artifact collection in the database.

    Example:
        collection = ConversationArtifactCollection(conversation_id=123)
        tool = MyTool(output_collection=collection)
        tool.forward(...)

        # Artifacts are associated with conversation 123
        for artifact in collection.artifacts:
            print(f"Conversation {collection.conversation_id}: {artifact.title}")
    """

    def __init__(
        self,
        conversation_id: int | None = None,
        conversation: Conversation | None = None,
    ):
        """
        Initialize with conversation context.

        Args:
            conversation_id: ID of the conversation
            conversation: Optional Conversation instance
        """
        super().__init__(context_id=conversation_id)
        self._conversation_id = conversation_id
        self._conversation = conversation

    @property
    def conversation_id(self) -> int | None:
        """Get the conversation ID."""
        if self._conversation_id:
            return self._conversation_id
        if self._conversation:
            return self._conversation.id
        return None

    @property
    def conversation(self) -> Conversation | None:
        """Get the conversation instance, if available."""
        return self._conversation


class WorkspaceArtifactCollection(InMemoryArtifactCollection):
    """
    Collection that associates artifacts with a workspace.

    Artifacts created in this collection are associated with a workspace
    and can potentially be saved to the workspace's document library.

    Example:
        collection = WorkspaceArtifactCollection(workspace_id=456)
        tool = MyTool(output_collection=collection)
        tool.forward(...)

        # Artifacts are associated with workspace 456
        for artifact in collection.artifacts:
            if artifact.type == "image":
                # Save to workspace document library
                save_to_library(workspace_id=456, artifact=artifact)
    """

    def __init__(
        self,
        workspace_id: int | None = None,
        workspace: Workspace | None = None,
    ):
        """
        Initialize with workspace context.

        Args:
            workspace_id: ID of the workspace
            workspace: Optional Workspace instance
        """
        super().__init__(context_id=workspace_id)
        self._workspace_id = workspace_id
        self._workspace = workspace

    @property
    def workspace_id(self) -> int | None:
        """Get the workspace ID."""
        if self._workspace_id:
            return self._workspace_id
        if self._workspace:
            return self._workspace.id
        return None

    @property
    def workspace(self) -> Workspace | None:
        """Get the workspace instance, if available."""
        return self._workspace
