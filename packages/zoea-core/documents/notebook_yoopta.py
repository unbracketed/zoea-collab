"""Yoopta helpers for Notebooks (DocumentCollection).

Notepads are a UI concept: the canonical data model remains DocumentCollection + DocumentCollectionItem.
For V1, we support exporting a notebook to shareable Yoopta JSON without requiring
CLI/API clients to understand Yoopta's internal format.
"""

from __future__ import annotations

import copy
import uuid
from typing import Any

from django.contrib.contenttypes.models import ContentType

from .models import Document, DocumentCollection, DocumentCollectionItem
from .notebook_service import get_notepad_draft_content


YOOPTA_NOTEBOOK_ITEM_BLOCK_TYPE = "NotebookItem"
YOOPTA_NOTEBOOK_ITEM_ELEMENT_TYPE = "notebook_item"


def build_shareable_yoopta_content_for_notebook(
    notebook: DocumentCollection,
) -> dict[str, Any]:
    """Build shareable Yoopta JSON content for a notebook.

    - If a notepad draft exists in notebook.metadata, use it as the base.
    - Otherwise, synthesize Yoopta JSON from the notebook items.

    This function intentionally produces content that does not depend on private
    DocumentCollectionItem IDs to render (suitable for saving as a shared YooptaDocument).

    Args:
        notebook: The notebook to build content for.

    Returns:
        Yoopta JSON content dict suitable for YooptaDocument.content.
    """
    draft = get_notepad_draft_content(notebook)
    if draft:
        return _sanitize_for_export(notebook, draft)

    return _build_yoopta_content_from_items(notebook)


def _sanitize_for_export(
    notebook: DocumentCollection, content: dict[str, Any]
) -> dict[str, Any]:
    """Best-effort sanitize/export normalization for Yoopta JSON.

    Notepad drafts can include private item references (Yoopta embed blocks).
    When exporting to a shared YooptaDocument, we replace embedded item blocks
    with shareable content synthesized from the underlying items.

    Args:
        notebook: The notebook being exported.
        content: The raw Yoopta JSON content dict.

    Returns:
        Sanitized Yoopta JSON content dict.
    """
    if not content or not isinstance(content, dict):
        return {}

    ordered_blocks: list[dict[str, Any]] = []
    for block in content.values():
        if not isinstance(block, dict):
            continue
        ordered_blocks.append(block)

    def _block_order(block: dict[str, Any]) -> int:
        meta = block.get("meta")
        if not isinstance(meta, dict):
            return 1_000_000
        order = meta.get("order")
        return order if isinstance(order, int) else 1_000_000

    ordered_blocks.sort(key=_block_order)

    embedded_item_ids: set[int] = set()
    for block in ordered_blocks:
        item_id = _extract_notebook_item_id(block)
        if item_id is not None:
            embedded_item_ids.add(item_id)

    if not embedded_item_ids:
        return content

    items = list(
        notebook.items.select_related("content_type", "virtual_node")
        .filter(id__in=embedded_item_ids)
        .all()
    )
    items_by_id = {item.id: item for item in items}

    doc_content_type = ContentType.objects.get_for_model(Document)
    document_ids = [
        int(item.object_id)
        for item in items
        if item.content_type_id == doc_content_type.id and item.object_id
    ]

    documents_by_id: dict[int, Document] = {
        doc.id: doc
        for doc in Document.objects.select_subclasses().filter(id__in=document_ids)
    }

    sanitized_blocks: list[dict[str, Any]] = []
    next_order = 0

    for block in ordered_blocks:
        item_id = _extract_notebook_item_id(block)
        if item_id is not None:
            item = items_by_id.get(item_id)
            replacement = _shareable_blocks_for_item(
                item=item,
                documents_by_id=documents_by_id,
                start_order=next_order,
            )
            sanitized_blocks.extend(replacement)
            next_order += len(replacement)
            continue

        sanitized = copy.deepcopy(block)
        meta = sanitized.get("meta")
        if not isinstance(meta, dict):
            meta = {}
        meta["order"] = next_order
        sanitized["meta"] = meta
        sanitized_blocks.append(sanitized)
        next_order += 1

    return {
        block["id"]: block
        for block in sanitized_blocks
        if isinstance(block, dict) and block.get("id")
    }


def _extract_notebook_item_id(block: dict[str, Any]) -> int | None:
    """Extract notebook item ID from a Yoopta block if it's a notebook item embed."""
    if block.get("type") != YOOPTA_NOTEBOOK_ITEM_BLOCK_TYPE:
        return None

    value = block.get("value")
    if not isinstance(value, list):
        return None

    def _scan(node: Any) -> int | None:
        if not isinstance(node, dict):
            return None
        if node.get("type") == YOOPTA_NOTEBOOK_ITEM_ELEMENT_TYPE:
            props = node.get("props")
            if isinstance(props, dict):
                raw = props.get("notebook_item_id")
                if raw is None:
                    return None
                try:
                    return int(raw)
                except (TypeError, ValueError):
                    return None

        children = node.get("children")
        if isinstance(children, list):
            for child in children:
                found = _scan(child)
                if found is not None:
                    return found
        return None

    for node in value:
        found = _scan(node)
        if found is not None:
            return found

    return None


def _shareable_blocks_for_item(
    *,
    item: DocumentCollectionItem | None,
    documents_by_id: dict[int, Document],
    start_order: int,
) -> list[dict[str, Any]]:
    """Create shareable Yoopta blocks for a notebook item.

    Args:
        item: The notebook item to convert.
        documents_by_id: Pre-loaded documents by ID.
        start_order: Starting order index for generated blocks.

    Returns:
        List of Yoopta block dicts.
    """
    if item is None:
        return [_paragraph_block(order=start_order, text="[Notebook item]")]

    doc_content_type = ContentType.objects.get_for_model(Document)
    if item.content_type_id == doc_content_type.id and item.object_id:
        doc = documents_by_id.get(int(item.object_id))
        doc_label = doc.name if doc else f"Document #{item.object_id}"
        return [
            _paragraph_block(
                order=start_order,
                text=f"Document: {doc_label} (id: {item.object_id})",
            )
        ]

    diagram_code = (item.source_metadata or {}).get("diagram_code")
    if diagram_code:
        diagram_name = (item.source_metadata or {}).get("diagram_name") or "Diagram"
        return [
            _heading_block(
                order=start_order,
                text=f"{diagram_name}",
                level=3,
            ),
            _code_block(order=start_order + 1, code=str(diagram_code)),
        ]

    full_text = (item.source_metadata or {}).get("full_text") or (
        item.source_metadata or {}
    ).get("preview")
    if full_text:
        return [_paragraph_block(order=start_order, text=str(full_text))]

    return [_paragraph_block(order=start_order, text="[Notebook item]")]


def _build_yoopta_content_from_items(notebook: DocumentCollection) -> dict[str, Any]:
    """Build Yoopta content by synthesizing from notebook items.

    Args:
        notebook: The notebook to build content from.

    Returns:
        Yoopta JSON content dict.
    """
    items = list(
        notebook.items.select_related("content_type", "virtual_node")
        .order_by("position", "-created_at")
        .all()
    )

    doc_content_type = ContentType.objects.get_for_model(Document)
    document_ids = [
        int(item.object_id)
        for item in items
        if item.content_type_id == doc_content_type.id and item.object_id
    ]

    documents_by_id: dict[int, Document] = {
        doc.id: doc
        for doc in Document.objects.select_subclasses().filter(id__in=document_ids)
    }

    blocks: list[dict[str, Any]] = []

    blocks.append(
        _heading_block(
            order=0,
            text=notebook.name or "Notepad",
            level=1,
        )
    )

    order = 1
    for item in items:
        if item.content_type_id == doc_content_type.id and item.object_id:
            doc = documents_by_id.get(int(item.object_id))
            doc_label = doc.name if doc else f"Document #{item.object_id}"
            blocks.append(
                _paragraph_block(
                    order=order,
                    text=f"Document: {doc_label} (id: {item.object_id})",
                )
            )
            order += 1
            continue

        diagram_code = (item.source_metadata or {}).get("diagram_code")
        if diagram_code:
            diagram_name = (
                item.source_metadata or {}
            ).get("diagram_name") or "Diagram"
            blocks.append(
                _heading_block(
                    order=order,
                    text=f"{diagram_name}",
                    level=3,
                )
            )
            order += 1
            blocks.append(_code_block(order=order, code=str(diagram_code)))
            order += 1
            continue

        full_text = (item.source_metadata or {}).get("full_text") or (
            item.source_metadata or {}
        ).get("preview")
        if full_text:
            blocks.append(_paragraph_block(order=order, text=str(full_text)))
            order += 1
            continue

        # Fallback
        blocks.append(
            _paragraph_block(
                order=order,
                text=f"[Notebook item #{item.id}]",
            )
        )
        order += 1

    return {block["id"]: block for block in blocks}


# =============================================================================
# Yoopta Block Builders
# =============================================================================


def _new_id(prefix: str) -> str:
    """Generate a unique ID for Yoopta blocks."""
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


def _heading_block(*, order: int, text: str, level: int = 1) -> dict[str, Any]:
    """Create a Yoopta heading block."""
    heading_type = {
        1: ("HeadingOne", "heading-one"),
        2: ("HeadingTwo", "heading-two"),
        3: ("HeadingThree", "heading-three"),
    }.get(level, ("HeadingThree", "heading-three"))
    block_type, element_type = heading_type

    block_id = _new_id("block")
    elem_id = _new_id("elem")
    return {
        "id": block_id,
        "meta": {"order": order},
        "type": block_type,
        "value": [
            {
                "id": elem_id,
                "type": element_type,
                "children": [{"text": text}],
            }
        ],
    }


def _paragraph_block(*, order: int, text: str) -> dict[str, Any]:
    """Create a Yoopta paragraph block."""
    block_id = _new_id("block")
    elem_id = _new_id("elem")
    return {
        "id": block_id,
        "meta": {"order": order},
        "type": "Paragraph",
        "value": [
            {
                "id": elem_id,
                "type": "paragraph",
                "children": [{"text": text}],
            }
        ],
    }


def _code_block(*, order: int, code: str) -> dict[str, Any]:
    """Create a Yoopta code block."""
    block_id = _new_id("block")
    elem_id = _new_id("elem")
    return {
        "id": block_id,
        "meta": {"order": order},
        "type": "Code",
        "value": [
            {
                "id": elem_id,
                "type": "code",
                "children": [{"text": code}],
            }
        ],
    }
