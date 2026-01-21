"""Transformers for Markdown documents.

This module contains all transformers that convert Markdown objects (and MarkdownPayload
value objects) to various output formats.
"""

import re
from typing import Any

from documents.models import Markdown

from ..base import StructuredDataTransformer, TextTransformer
from ..enums import OutputFormat
from ..registry import register_transformer
from ..value_objects import MarkdownPayload


@register_transformer(Markdown, OutputFormat.OUTLINE)
@register_transformer(MarkdownPayload, OutputFormat.OUTLINE)
class MarkdownToOutlineTransformer(StructuredDataTransformer):
    """Convert Markdown to hierarchical outline structure.

    Parses markdown headers (ATX style: # Header) to build a tree structure
    where each section contains its header level, title, content, and children.

    This transformer works with both Markdown model instances and MarkdownPayload
    value objects, making it suitable for chained transformations.
    """

    def transform(self, source: Markdown | MarkdownPayload, **context: Any) -> dict:
        """Transform Markdown to outline structure.

        Args:
            source: Markdown model instance or MarkdownPayload
            **context: Unused for this transformation

        Returns:
            dict: Tree structure with root sections and nested children
                {
                    "sections": [
                        {
                            "id": "section-1",
                            "level": 1,
                            "title": "Section Title",
                            "content": "Section text content...",
                            "parent_id": None,
                            "children": [...]
                        }
                    ]
                }
        """
        content = source.content
        if not content:
            return {"sections": []}

        # Split content into lines
        lines = content.split("\n")

        # Parse sections
        sections = []
        current_section = None
        section_counter = 0
        content_buffer = []

        # Stack to track parent sections at each level
        # Index represents header level (0 = h1, 1 = h2, etc.)
        level_stack = [None] * 6  # Support up to h6

        for line in lines:
            # Check if line is a header (ATX style: # Header)
            header_match = re.match(r"^(#{1,6})\s+(.+)$", line)

            if header_match:
                # Save previous section if exists
                if current_section is not None:
                    current_section["content"] = "\n".join(content_buffer).strip()
                    sections.append(current_section)
                    content_buffer = []

                # Parse new section
                level = len(header_match.group(1))  # Count # characters
                title = header_match.group(2).strip()
                section_counter += 1

                # Determine parent based on level stack
                parent_id = None
                if level > 1:
                    # Look for parent at previous level
                    parent_id = level_stack[level - 2]

                # Create new section
                current_section = {
                    "id": f"section-{section_counter}",
                    "level": level,
                    "title": title,
                    "content": "",
                    "parent_id": parent_id,
                    "children": [],
                }

                # Update level stack
                level_stack[level - 1] = current_section["id"]
                # Clear deeper levels
                for i in range(level, 6):
                    level_stack[i] = None
            else:
                # Accumulate content for current section
                content_buffer.append(line)

        # Save last section
        if current_section is not None:
            current_section["content"] = "\n".join(content_buffer).strip()
            sections.append(current_section)

        # Build hierarchical structure
        # Create a lookup map
        section_map = {s["id"]: s for s in sections}

        # Organize into parent-child relationships
        root_sections = []
        for section in sections:
            if section["parent_id"] is None:
                root_sections.append(section)
            else:
                # Add to parent's children
                parent = section_map.get(section["parent_id"])
                if parent:
                    parent["children"].append(section)

        return {"sections": root_sections}


@register_transformer(Markdown, OutputFormat.JSON)
@register_transformer(MarkdownPayload, OutputFormat.JSON)
class MarkdownToJSONTransformer(StructuredDataTransformer):
    """Convert Markdown to JSON-serializable dictionary.

    Produces a simple dict representation suitable for API responses.
    """

    def transform(self, source: Markdown | MarkdownPayload, **context: Any) -> dict:
        """Transform Markdown to JSON dict.

        Args:
            source: Markdown model instance or MarkdownPayload
            **context: Unused for this transformation

        Returns:
            dict with title, content, and optional metadata
        """
        result = {
            "content": source.content,
        }

        # Add title/name if available
        # MarkdownPayload uses "title", Markdown model uses "name"
        if hasattr(source, "title") and source.title:
            result["title"] = source.title
        elif hasattr(source, "name") and source.name:
            result["title"] = source.name

        # Add metadata if available
        if hasattr(source, "metadata") and source.metadata:
            result["metadata"] = source.metadata

        # Add model-specific fields if source is a Django model
        if isinstance(source, Markdown):
            result["id"] = source.id
            result["created_at"] = source.created_at.isoformat()
            result["updated_at"] = source.updated_at.isoformat()

        return result


@register_transformer(Markdown, OutputFormat.MARKDOWN)
@register_transformer(MarkdownPayload, OutputFormat.MARKDOWN)
class MarkdownToMarkdownTransformer(TextTransformer):
    """Pass-through transformer for Markdown to Markdown.

    This is useful for normalizing/standardizing markdown or for
    completing transformation pipelines where the final format is markdown.
    """

    def transform(self, source: Markdown | MarkdownPayload, **context: Any) -> str:
        """Return markdown content as-is.

        Args:
            source: Markdown model instance or MarkdownPayload
            **context: Unused for this transformation

        Returns:
            The markdown content string
        """
        return source.content


__all__ = [
    "MarkdownToOutlineTransformer",
    "MarkdownToJSONTransformer",
    "MarkdownToMarkdownTransformer",
]
