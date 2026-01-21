"""Lightweight value objects for transformation chaining.

This module provides simple dataclasses that capture just the essential fields
needed for transformations, avoiding the need to instantiate full Django ORM
models (which can violate constraints, trigger signals, or require tenant context).

Use these when chaining transformations where the intermediate format is a
content type that has a transformer registered.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional


@dataclass(frozen=True)
class MarkdownPayload:
    """Lightweight container for markdown content.

    Use this instead of creating unsaved Markdown model instances when
    chaining transformations (e.g., Conversation → Markdown → Outline).

    Attributes:
        content: The markdown text content
        title: Optional title/heading
        metadata: Optional metadata dict
    """

    content: str
    title: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class TextPayload:
    """Generic text content payload.

    Use for plain text transformations or when the specific format doesn't matter.

    Attributes:
        content: The text content
        format: Optional format hint (e.g., "plain", "html")
        metadata: Optional metadata dict
    """

    content: str
    format: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ConversationPayload:
    """Lightweight container for conversation data.

    Use when you need to pass conversation-like data through transformations
    without creating a full Conversation model instance.

    Attributes:
        messages: List of (role, content, timestamp) tuples
        title: Optional conversation title
        agent_name: Optional agent identifier
        metadata: Optional metadata dict
    """

    messages: list[tuple[str, str, Optional[datetime]]]  # (role, content, timestamp)
    title: Optional[str] = None
    agent_name: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class DiagramPayload:
    """Lightweight container for diagram data.

    Use for passing diagram structures between transformations.

    Attributes:
        nodes: List of node data dicts
        edges: List of edge/relationship data dicts
        layout: Optional layout information
        metadata: Optional metadata dict
    """

    nodes: list[dict[str, Any]]
    edges: list[dict[str, Any]]
    layout: Optional[dict[str, Any]] = None
    metadata: dict[str, Any] = field(default_factory=dict)


__all__ = [
    "MarkdownPayload",
    "TextPayload",
    "ConversationPayload",
    "DiagramPayload",
]
