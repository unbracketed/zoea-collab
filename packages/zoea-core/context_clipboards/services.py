"""Business logic helpers for clipboard operations."""

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

from .models import Clipboard, ClipboardDirection, ClipboardItem, ClipboardSourceChannel

logger = logging.getLogger(__name__)


@dataclass
class ClipboardOperationResult:
    """Simple structure returned by service operations."""

    clipboard: Clipboard
    item: ClipboardItem | None = None
    metadata: dict[str, Any] | None = None


class ClipboardService:
    """High-level API handling clipboard creation and deque operations."""

    def __init__(self, *, actor):
        self.actor = actor

    def get_or_create_active(self, workspace) -> Clipboard:
        """Fetch the active clipboard for a workspace/user or create one."""

        clipboard = (
            Clipboard.objects.for_workspace(workspace)
            .for_owner(self.actor)
            .active()
            .first()
        )
        if clipboard:
            return clipboard

        return Clipboard.objects.create(
            workspace=workspace,
            owner=self.actor,
            name=f"{workspace.name} Clipboard",
            is_active=True,
            activated_at=timezone.now(),
        )

    @transaction.atomic
    def activate(self, clipboard: Clipboard) -> Clipboard:
        """Activate the provided clipboard, deactivating prior ones."""

        (
            Clipboard.objects.for_workspace(clipboard.workspace)
            .for_owner(clipboard.owner)
            .filter(is_active=True)
            .exclude(id=clipboard.id)
            .update(is_active=False, is_recent=True)
        )
        clipboard.activate()
        clipboard.save(update_fields=["is_active", "is_recent", "activated_at"])
        return clipboard

    @transaction.atomic
    def add_item(
        self,
        *,
        clipboard: Clipboard,
        direction: str,
        content_object=None,
        content_type=None,
        object_id: str | None = None,
        virtual_node=None,
        source_channel=None,
        source_metadata: dict[str, Any] | None = None,
        preview: dict[str, Any] | None = None,
    ) -> ClipboardOperationResult:
        """Insert a new clipboard item at the given direction."""

        direction = direction or ClipboardDirection.RIGHT
        source_channel = source_channel or ClipboardSourceChannel.UNKNOWN

        if content_object is not None:
            content_type = ContentType.objects.get_for_model(content_object)
            object_id = str(content_object.pk)

        if object_id is not None:
            object_id = str(object_id)

        reserved_position = clipboard.reserve_position(direction)
        clipboard.save(update_fields=["sequence_head", "sequence_tail"])
        item = ClipboardItem.objects.create(
            clipboard=clipboard,
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
        return ClipboardOperationResult(clipboard=clipboard, item=item)

    def reorder_items(
        self,
        *,
        clipboard: Clipboard,
        ordered_items: Iterable[tuple[int, int]],
    ) -> Clipboard:
        """Reassign explicit positions for clipboard items."""

        for item_id, position in ordered_items:
            ClipboardItem.objects.filter(
                clipboard=clipboard, id=item_id
            ).update(position=position)
        return clipboard

    def remove_item(self, *, item: ClipboardItem) -> None:
        item.delete()

    def clear_clipboard(self, clipboard: Clipboard) -> None:
        clipboard.items.all().delete()


def render_clipboard_to_markdown(
    clipboard: Clipboard,
    *,
    include_metadata: bool = True,
) -> str:
    """Convert clipboard items to concatenated Markdown.

    Iterates through clipboard items in order, attempting to transform each
    via the transformations registry. Falls back gracefully when transformers
    are missing.

    Args:
        clipboard: The clipboard to export
        include_metadata: Whether to include item metadata in output

    Returns:
        Concatenated Markdown string with all clipboard items
    """
    items = clipboard.items.select_related(
        "content_type", "virtual_node", "added_by"
    ).order_by("position")

    markdown_parts = []

    if include_metadata:
        # Add clipboard header
        markdown_parts.append(f"# {clipboard.name}\n")
        if clipboard.description:
            markdown_parts.append(f"{clipboard.description}\n")
        markdown_parts.append("\n---\n\n")

    for item in items:
        try:
            item_markdown = _render_clipboard_item_to_markdown(item, include_metadata)
            if item_markdown:
                markdown_parts.append(item_markdown)
                markdown_parts.append("\n\n---\n\n")
        except Exception as e:
            logger.exception(
                f"Failed to render clipboard item {item.id} to markdown: {e}"
            )
            # Include a fallback note about the failed item
            fallback = _create_fallback_markdown(item)
            markdown_parts.append(fallback)
            markdown_parts.append("\n\n---\n\n")

    return "".join(markdown_parts).strip()


def _render_clipboard_item_to_markdown(
    item: ClipboardItem,
    include_metadata: bool,
) -> str:
    """Render a single clipboard item to markdown.

    Args:
        item: The clipboard item to render
        include_metadata: Whether to include item metadata

    Returns:
        Markdown string for this item
    """
    parts = []

    # Try to get the actual content object
    content_object = item.content_object

    if content_object:
        # Check if we have a transformer for this type
        content_type = type(content_object)
        if has_transformer(content_type, OutputFormat.MARKDOWN):
            # Use the registered transformer
            result = transform(content_object, OutputFormat.MARKDOWN)
            # Handle both string results and MarkdownPayload
            if isinstance(result, MarkdownPayload):
                markdown_content = result.content
            else:
                markdown_content = str(result)
            parts.append(markdown_content)
        else:
            # No transformer - create fallback
            parts.append(_create_fallback_markdown(item))
    elif item.virtual_node:
        # Handle virtual nodes
        node = item.virtual_node
        if node.payload:
            # Try to extract text content from payload
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
        # No content object or virtual node - use source metadata
        parts.append(_create_fallback_markdown(item))

    # Optionally add metadata footer
    if include_metadata and (item.source_channel or item.source_metadata):
        metadata_parts = []
        if item.source_channel:
            metadata_parts.append(f"*Source: {item.get_source_channel_display()}*")
        if item.added_by:
            metadata_parts.append(f"*Added by: {item.added_by.username}*")
        if metadata_parts:
            parts.append("\n\n" + " | ".join(metadata_parts))

    return "\n\n".join(parts)


def _create_fallback_markdown(item: ClipboardItem) -> str:
    """Create a fallback markdown representation when no transformer exists.

    Args:
        item: The clipboard item to create fallback for

    Returns:
        Fallback markdown string
    """
    # Try to get preview text from source_metadata
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
        return "> *[Empty clipboard item]*"
