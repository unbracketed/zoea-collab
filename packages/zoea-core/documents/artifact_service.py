"""Business logic helpers for artifact (DocumentCollection) operations.

This module provides high-level APIs for managing DocumentCollection instances
of type ARTIFACT, including lazy creation and item management for Conversations
and WorkflowRuns.

Artifacts are automatically collected outputs from conversations (code blocks,
generated files) and workflow runs (documents, diagrams, etc.).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

from django.contrib.contenttypes.models import ContentType
from django.db import transaction

from .models import (
    CollectionItemDirection,
    CollectionItemSourceChannel,
    CollectionType,
    DocumentCollection,
    DocumentCollectionItem,
)

logger = logging.getLogger(__name__)


# =============================================================================
# Protocol for Artifact Owners
# =============================================================================


@runtime_checkable
class ArtifactOwner(Protocol):
    """Protocol for models that can own artifact collections.

    Both Conversation and WorkflowRun implement this protocol.
    """

    organization: Any
    workspace: Any
    artifacts: DocumentCollection | None
    artifacts_id: int | None

    def save(self, update_fields: list[str] | None = None) -> None:
        """Save the model instance."""
        ...


# =============================================================================
# Service Data Classes
# =============================================================================


@dataclass
class ArtifactOperationResult:
    """Result structure returned by artifact service operations."""

    collection: DocumentCollection
    item: DocumentCollectionItem | None = None
    metadata: dict[str, Any] | None = None


# =============================================================================
# Artifact Service
# =============================================================================


class ArtifactService:
    """High-level API for artifact collection and item operations.

    Handles DocumentCollection instances of type ARTIFACT, providing
    lazy creation and item management for conversations and workflow runs.

    Example usage:
        service = ArtifactService(actor=user)

        # Get or create artifacts for a conversation
        collection = service.get_or_create_artifacts(conversation)

        # Add a code block artifact
        result = service.add_artifact(
            collection,
            content_object=document,
            source_channel='code',
            source_metadata={'language': 'python', 'filename': 'script.py'},
        )
    """

    def __init__(self, *, actor):
        """Initialize the service with an acting user.

        Args:
            actor: The user performing the operations.
        """
        self.actor = actor

    def get_or_create_artifacts(
        self,
        owner: ArtifactOwner,
        name: str | None = None,
    ) -> DocumentCollection:
        """Get or lazily create an artifact collection for an owner.

        Works with any model that implements the ArtifactOwner protocol
        (Conversation, WorkflowRun).

        Args:
            owner: The object that owns the artifacts (Conversation or WorkflowRun).
            name: Optional name for the collection. Auto-generated if not provided.

        Returns:
            The DocumentCollection of type ARTIFACT for this owner.

        Raises:
            ValueError: If owner doesn't have required attributes.
        """
        # Return existing collection if present
        if owner.artifacts_id:
            return owner.artifacts

        # Generate name based on owner type
        if name is None:
            owner_type = type(owner).__name__
            owner_id = getattr(owner, 'id', 'unknown')
            name = f"{owner_type} Artifacts ({owner_id})"

        # Create new collection
        with transaction.atomic():
            collection = DocumentCollection.objects.create(
                organization=owner.organization,
                workspace=owner.workspace,
                collection_type=CollectionType.ARTIFACT,
                name=name,
                created_by=self.actor,
            )
            owner.artifacts = collection
            owner.save(update_fields=['artifacts'])

        logger.info(
            "Created artifact collection %d for %s %d",
            collection.id,
            type(owner).__name__,
            getattr(owner, 'id', 0),
        )
        return collection

    def add_artifact(
        self,
        collection: DocumentCollection,
        content_object: Any | None = None,
        source_channel: str = CollectionItemSourceChannel.UNKNOWN,
        source_metadata: dict[str, Any] | None = None,
        preview: dict[str, Any] | None = None,
        direction: str = CollectionItemDirection.RIGHT,
        is_pinned: bool = False,
    ) -> ArtifactOperationResult:
        """Add an artifact item to a collection.

        Args:
            collection: The artifact collection to add to.
            content_object: The Django model instance to reference (optional).
            source_channel: Where this artifact came from (code, document, etc.).
            source_metadata: Additional metadata about the artifact.
            preview: Preview data for UI rendering.
            direction: Which end of the deque to add to (left or right).
            is_pinned: Whether this artifact should be pinned.

        Returns:
            ArtifactOperationResult with the created item.

        Raises:
            ValueError: If collection is not an artifact collection.
        """
        if collection.collection_type != CollectionType.ARTIFACT:
            raise ValueError(
                f"Collection {collection.id} is not an artifact collection "
                f"(type: {collection.collection_type})"
            )

        # Get content type and object ID if content_object provided
        content_type = None
        object_id = None
        if content_object is not None:
            content_type = ContentType.objects.get_for_model(content_object)
            object_id = str(content_object.pk)

        with transaction.atomic():
            # Reserve position and create item
            position = collection.reserve_position(direction)
            item = DocumentCollectionItem.objects.create(
                collection=collection,
                position=position,
                direction_added=direction,
                added_by=self.actor,
                content_type=content_type,
                object_id=object_id,
                source_channel=source_channel,
                source_metadata=source_metadata or {},
                preview=preview,
                is_pinned=is_pinned,
            )
            collection.save(update_fields=['sequence_head', 'sequence_tail', 'updated_at'])

        logger.debug(
            "Added artifact item %d to collection %d (position=%d)",
            item.id,
            collection.id,
            position,
        )
        return ArtifactOperationResult(collection=collection, item=item)

    def remove_artifact(
        self,
        collection: DocumentCollection,
        item_id: int,
    ) -> bool:
        """Remove an artifact item from a collection.

        Args:
            collection: The artifact collection.
            item_id: ID of the item to remove.

        Returns:
            True if item was removed, False if not found.
        """
        deleted_count, _ = DocumentCollectionItem.objects.filter(
            collection=collection,
            id=item_id,
        ).delete()
        return deleted_count > 0

    def list_artifacts(
        self,
        collection: DocumentCollection,
        limit: int = 100,
    ) -> list[DocumentCollectionItem]:
        """List artifact items in a collection.

        Args:
            collection: The artifact collection.
            limit: Maximum number of items to return.

        Returns:
            List of DocumentCollectionItem instances ordered by position.
        """
        return list(
            collection.items.select_related('content_type', 'added_by')
            .order_by('position')[:limit]
        )


# =============================================================================
# Convenience Functions
# =============================================================================


def get_or_create_artifacts_for_conversation(conversation, actor) -> DocumentCollection:
    """Convenience function to get/create artifacts for a conversation.

    Args:
        conversation: The Conversation instance.
        actor: The user performing the operation.

    Returns:
        The artifact DocumentCollection.
    """
    service = ArtifactService(actor=actor)
    return service.get_or_create_artifacts(
        conversation,
        name=f"Artifacts: {conversation.get_title()[:50]}",
    )


def get_or_create_artifacts_for_workflow_run(workflow_run, actor) -> DocumentCollection:
    """Convenience function to get/create artifacts for a workflow run.

    Args:
        workflow_run: The WorkflowRun instance.
        actor: The user performing the operation.

    Returns:
        The artifact DocumentCollection.
    """
    service = ArtifactService(actor=actor)
    run_id_short = str(workflow_run.run_id)[:8]
    return service.get_or_create_artifacts(
        workflow_run,
        name=f"Workflow: {workflow_run.workflow_slug} ({run_id_short})",
    )
