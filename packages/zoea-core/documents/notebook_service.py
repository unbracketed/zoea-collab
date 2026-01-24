"""Business logic helpers for notebook (DocumentCollection) operations.

This module provides high-level APIs for managing DocumentCollection instances
of type NOTEBOOK, including activation, item management, and export functionality.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.utils import timezone

from transformations import OutputFormat, has_transformer, transform
from transformations.value_objects import MarkdownPayload

from .models import (
    CollectionItemDirection,
    CollectionItemSourceChannel,
    CollectionType,
    DocumentCollection,
    DocumentCollectionItem,
    VirtualCollectionNode,
)

logger = logging.getLogger(__name__)


# =============================================================================
# Notepad Metadata Keys (for Yoopta draft storage)
# =============================================================================

NOTEPAD_METADATA_KEY = "notepad"
NOTEPAD_METADATA_CONTENT_KEY = "content"


# =============================================================================
# Service Data Classes
# =============================================================================


@dataclass
class NotebookOperationResult:
    """Result structure returned by notebook service operations."""

    notebook: DocumentCollection
    item: DocumentCollectionItem | None = None
    metadata: dict[str, Any] | None = None


# =============================================================================
# Notebook Service
# =============================================================================


class NotebookService:
    """High-level API for notebook creation and item operations.

    Handles DocumentCollection instances of type NOTEBOOK, providing
    deque-style item management and activation semantics.
    """

    def __init__(self, *, actor):
        """Initialize the service with an acting user.

        Args:
            actor: The user performing the operations.
        """
        self.actor = actor

    def get_or_create_active(self, project) -> DocumentCollection:
        """Fetch the active notebook for a project/user or create one.

        Args:
            project: The project to scope the notebook to.

        Returns:
            The active DocumentCollection of type NOTEBOOK.
        """
        notebook = (
            DocumentCollection.objects.filter(project=project)
            .for_owner(self.actor)
            .notebooks()
            .active()
            .first()
        )
        if notebook:
            return notebook

        return DocumentCollection.objects.create(
            organization=project.organization,
            project=project,
            owner=self.actor,
            collection_type=CollectionType.NOTEBOOK,
            name=f"{project.name} Notebook",
            is_active=True,
            activated_at=timezone.now(),
            created_by=self.actor,
        )

    @transaction.atomic
    def activate(self, notebook: DocumentCollection) -> DocumentCollection:
        """Activate the provided notebook, deactivating prior ones.

        Args:
            notebook: The notebook to activate.

        Returns:
            The activated notebook.
        """
        # Deactivate other notebooks for this user in this project
        (
            DocumentCollection.objects.filter(project=notebook.project)
            .for_owner(notebook.owner)
            .notebooks()
            .filter(is_active=True)
            .exclude(id=notebook.id)
            .update(is_active=False, is_recent=True)
        )

        notebook.activate()
        notebook.save(update_fields=["is_active", "is_recent", "activated_at"])
        return notebook

    @transaction.atomic
    def add_item(
        self,
        *,
        notebook: DocumentCollection,
        direction: str = None,
        content_object=None,
        content_type=None,
        object_id: str | None = None,
        virtual_node: VirtualCollectionNode | None = None,
        source_channel: str | None = None,
        source_metadata: dict[str, Any] | None = None,
        preview: dict[str, Any] | None = None,
    ) -> NotebookOperationResult:
        """Insert a new item into the notebook at the given direction.

        Args:
            notebook: The notebook to add the item to.
            direction: 'left' or 'right' (default: right).
            content_object: Django model instance to reference.
            content_type: ContentType for the referenced object.
            object_id: ID of the referenced object.
            virtual_node: VirtualCollectionNode for transient items.
            source_channel: Origin hint (conversation, document, etc.).
            source_metadata: Additional source-specific metadata.
            preview: Custom preview data for UI rendering.

        Returns:
            NotebookOperationResult with the notebook and created item.
        """
        direction = direction or CollectionItemDirection.RIGHT
        source_channel = source_channel or CollectionItemSourceChannel.UNKNOWN

        if content_object is not None:
            content_type = ContentType.objects.get_for_model(content_object)
            object_id = str(content_object.pk)

        if object_id is not None:
            object_id = str(object_id)

        reserved_position = notebook.reserve_position(direction)
        notebook.save(update_fields=["sequence_head", "sequence_tail"])

        item = DocumentCollectionItem.objects.create(
            collection=notebook,
            position=reserved_position,
            direction_added=direction,
            added_by=self.actor,
            content_type=content_type,
            object_id=object_id,
            virtual_node=virtual_node,
            source_channel=source_channel,
            source_metadata=source_metadata or {},
            preview=preview,
        )

        return NotebookOperationResult(notebook=notebook, item=item)

    def reorder_items(
        self,
        *,
        notebook: DocumentCollection,
        ordered_items: Iterable[tuple[int, int]],
    ) -> DocumentCollection:
        """Reassign explicit positions for notebook items.

        Args:
            notebook: The notebook containing the items.
            ordered_items: Iterable of (item_id, position) tuples.

        Returns:
            The notebook instance.
        """
        for item_id, position in ordered_items:
            DocumentCollectionItem.objects.filter(
                collection=notebook, id=item_id
            ).update(position=position)
        return notebook

    def remove_item(self, *, item: DocumentCollectionItem) -> None:
        """Remove an item from its notebook.

        Args:
            item: The item to remove.
        """
        item.delete()

    def clear_notebook(self, notebook: DocumentCollection) -> None:
        """Remove all items from a notebook.

        Args:
            notebook: The notebook to clear.
        """
        notebook.items.all().delete()


# =============================================================================
# Notepad Draft Helpers
# =============================================================================


def get_notepad_draft_content(notebook: DocumentCollection) -> dict[str, Any] | None:
    """Return the stored Yoopta JSON dict from notebook metadata (if present).

    Args:
        notebook: The notebook to get draft content from.

    Returns:
        The Yoopta JSON content dict, or None if no draft exists.
    """
    import json

    metadata = notebook.metadata or {}
    raw_notepad = metadata.get(NOTEPAD_METADATA_KEY)
    if not isinstance(raw_notepad, dict):
        return None

    raw_content = raw_notepad.get(NOTEPAD_METADATA_CONTENT_KEY)
    if raw_content is None:
        return None

    if isinstance(raw_content, dict):
        return raw_content

    if isinstance(raw_content, str):
        try:
            parsed = json.loads(raw_content)
        except json.JSONDecodeError:
            return None
        return parsed if isinstance(parsed, dict) else None

    return None


def set_notepad_draft_content(
    notebook: DocumentCollection,
    content: dict[str, Any] | None,
) -> DocumentCollection:
    """Set or clear the Yoopta draft content in notebook metadata.

    Args:
        notebook: The notebook to update.
        content: The Yoopta JSON content dict, or None to clear.

    Returns:
        The updated notebook instance.
    """
    metadata = notebook.metadata or {}
    raw_notepad = metadata.get(NOTEPAD_METADATA_KEY)
    notepad = raw_notepad if isinstance(raw_notepad, dict) else {}

    if content is None:
        notepad.pop(NOTEPAD_METADATA_CONTENT_KEY, None)
        if notepad:
            metadata[NOTEPAD_METADATA_KEY] = notepad
        else:
            metadata.pop(NOTEPAD_METADATA_KEY, None)
    else:
        notepad[NOTEPAD_METADATA_CONTENT_KEY] = content
        metadata[NOTEPAD_METADATA_KEY] = notepad

    notebook.metadata = metadata
    notebook.save(update_fields=["metadata"])
    return notebook


def clear_notepad_draft_content(notebook: DocumentCollection) -> DocumentCollection:
    """Clear the notepad draft content from notebook metadata.

    Args:
        notebook: The notebook to clear draft content from.

    Returns:
        The updated notebook instance.
    """
    return set_notepad_draft_content(notebook, None)


# =============================================================================
# Export Helpers
# =============================================================================


def render_notebook_to_markdown(
    notebook: DocumentCollection,
    *,
    include_metadata: bool = True,
) -> str:
    """Convert notebook items to concatenated Markdown.

    Iterates through notebook items in order, attempting to transform each
    via the transformations registry. Falls back gracefully when transformers
    are missing.

    Args:
        notebook: The notebook to export.
        include_metadata: Whether to include item metadata in output.

    Returns:
        Concatenated Markdown string with all notebook items.
    """
    items = notebook.items.select_related(
        "content_type", "virtual_node", "added_by"
    ).order_by("position")

    markdown_parts = []

    if include_metadata:
        markdown_parts.append(f"# {notebook.name}\n")
        if notebook.description:
            markdown_parts.append(f"{notebook.description}\n")
        markdown_parts.append("\n---\n\n")

    for item in items:
        try:
            item_markdown = _render_item_to_markdown(item, include_metadata)
            if item_markdown:
                markdown_parts.append(item_markdown)
                markdown_parts.append("\n\n---\n\n")
        except Exception as e:
            logger.exception(f"Failed to render notebook item {item.id} to markdown: {e}")
            fallback = _create_fallback_markdown(item)
            markdown_parts.append(fallback)
            markdown_parts.append("\n\n---\n\n")

    return "".join(markdown_parts).strip()


def _render_item_to_markdown(
    item: DocumentCollectionItem,
    include_metadata: bool,
) -> str:
    """Render a single notebook item to markdown.

    Args:
        item: The notebook item to render.
        include_metadata: Whether to include item metadata.

    Returns:
        Markdown string for this item.
    """
    parts = []
    content_object = item.content_object

    if content_object:
        content_type = type(content_object)
        if has_transformer(content_type, OutputFormat.MARKDOWN):
            result = transform(content_object, OutputFormat.MARKDOWN)
            if isinstance(result, MarkdownPayload):
                markdown_content = result.content
            else:
                markdown_content = str(result)
            parts.append(markdown_content)
        else:
            parts.append(_create_fallback_markdown(item))
    elif item.virtual_node:
        node = item.virtual_node
        if node.payload:
            payload_text = node.payload.get("text") or node.payload.get("content")
            if payload_text:
                parts.append(f"**Virtual Node: {node.node_type}**\n\n{payload_text}")
            else:
                parts.append(
                    f"**Virtual Node: {node.node_type}**\n\n```json\n"
                    f"{node.payload}\n```"
                )
        if node.preview_text:
            parts.append(node.preview_text)
    else:
        parts.append(_create_fallback_markdown(item))

    if include_metadata and (item.source_channel or item.source_metadata):
        metadata_parts = []
        if item.source_channel:
            metadata_parts.append(f"*Source: {item.get_source_channel_display()}*")
        if item.added_by:
            metadata_parts.append(f"*Added by: {item.added_by.username}*")
        if metadata_parts:
            parts.append("\n\n" + " | ".join(metadata_parts))

    return "\n\n".join(parts)


def _create_fallback_markdown(item: DocumentCollectionItem) -> str:
    """Create a fallback markdown representation when no transformer exists.

    Args:
        item: The notebook item to create fallback for.

    Returns:
        Fallback markdown string.
    """
    preview = item.source_metadata.get("preview", "")
    full_text = item.source_metadata.get("full_text", "")

    if full_text:
        return f"> {full_text}"
    elif preview:
        return f"> {preview}"
    elif item.content_type:
        model_name = item.content_type.model
        return (
            f"> *[Unsupported content type: {model_name}]*\n>\n"
            f"> *No transformer available for this content type.*"
        )
    else:
        return "> *[Empty notebook item]*"
