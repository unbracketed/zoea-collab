"""Transformers for Conversation objects.

This module contains all transformers that convert Conversation objects
(and ConversationPayload value objects) to various output formats.
"""

from typing import Any

from chat.models import Conversation

from ..base import TextTransformer
from ..enums import OutputFormat
from ..registry import register_transformer
from ..value_objects import ConversationPayload


@register_transformer(Conversation, OutputFormat.MARKDOWN)
class ConversationToMarkdownTransformer(TextTransformer):
    """Convert Conversation to Markdown format.

    Each message is rendered as a separate section with a header showing
    the role and timestamp. Includes conversation metadata at the top.

    IMPORTANT: This transformer performs database queries to fetch related
    messages. Ensure the Conversation instance has appropriate select_related/
    prefetch_related optimizations if used in bulk operations.
    """

    def transform(self, source: Conversation, **context: Any) -> str:
        """Transform Conversation to Markdown text.

        Args:
            source: Conversation model instance
            **context: Optional context keys:
                - organization: For tenant-aware filtering (not currently used
                  but reserved for future multi-tenant features)

        Returns:
            Markdown-formatted string representation of the conversation
        """
        lines = []

        # Add conversation title as main heading
        title = source.get_title()
        lines.append(f"# {title}\n")

        # Add metadata
        lines.append(f"**Agent:** {source.agent_name}  ")
        lines.append(f"**Created by:** {source.created_by.username}  ")
        lines.append(
            f"**Created at:** {source.created_at.strftime('%Y-%m-%d %H:%M:%S')}\n"
        )

        # Add separator
        lines.append("---\n")

        # Iterate through messages in chronological order
        # NOTE: This performs a database query. For optimal performance,
        # caller should prefetch: conversation.prefetch_related('messages')
        for message in source.messages.all():
            # Format timestamp
            timestamp = message.created_at.strftime("%Y-%m-%d %H:%M:%S")

            # Create section header with role and timestamp
            role_display = message.get_role_display()
            lines.append(f"## {role_display} - {timestamp}\n")

            # Add message content
            lines.append(f"{message.content}\n")

            # Add optional metadata if available
            metadata_parts = []
            if message.model_used:
                metadata_parts.append(f"Model: {message.model_used}")
            if message.token_count:
                metadata_parts.append(f"Tokens: {message.token_count}")

            if metadata_parts:
                lines.append(f"*{' | '.join(metadata_parts)}*\n")

            # Add separator between messages
            lines.append("---\n")

        return "\n".join(lines)


@register_transformer(ConversationPayload, OutputFormat.MARKDOWN)
class ConversationPayloadToMarkdownTransformer(TextTransformer):
    """Convert ConversationPayload to Markdown format.

    This transformer is designed for use with lightweight ConversationPayload
    value objects, avoiding the need for database queries.

    Useful for chained transformations or when working with conversation data
    that doesn't come from the database.
    """

    def transform(self, source: ConversationPayload, **context: Any) -> str:
        """Transform ConversationPayload to Markdown text.

        Args:
            source: ConversationPayload value object
            **context: Unused for this transformation

        Returns:
            Markdown-formatted string representation
        """
        lines = []

        # Add title if available
        if source.title:
            lines.append(f"# {source.title}\n")

        # Add metadata if available
        if source.agent_name:
            lines.append(f"**Agent:** {source.agent_name}  \n")

        # Add separator if we had metadata
        if source.title or source.agent_name:
            lines.append("---\n")

        # Iterate through messages
        for role, content, timestamp in source.messages:
            # Format timestamp if available
            if timestamp:
                timestamp_str = timestamp.strftime("%Y-%m-%d %H:%M:%S")
                lines.append(f"## {role} - {timestamp_str}\n")
            else:
                lines.append(f"## {role}\n")

            # Add message content
            lines.append(f"{content}\n")

            # Add separator between messages
            lines.append("---\n")

        return "\n".join(lines)


@register_transformer(Conversation, OutputFormat.JSON)
class ConversationToJSONTransformer(TextTransformer):
    """Convert Conversation to JSON-serializable dictionary.

    Produces a structured dict suitable for API responses.
    """

    def transform(self, source: Conversation, **context: Any) -> dict:
        """Transform Conversation to JSON dict.

        Args:
            source: Conversation model instance
            **context: Unused for this transformation

        Returns:
            dict with conversation and message data
        """
        return {
            "id": source.id,
            "title": source.get_title(),
            "agent_name": source.agent_name,
            "created_by": source.created_by.username,
            "created_at": source.created_at.isoformat(),
            "updated_at": source.updated_at.isoformat(),
            "messages": [
                {
                    "id": msg.id,
                    "role": msg.role,
                    "content": msg.content,
                    "created_at": msg.created_at.isoformat(),
                    "model_used": msg.model_used,
                    "token_count": msg.token_count,
                }
                for msg in source.messages.all()
            ],
        }


__all__ = [
    "ConversationToMarkdownTransformer",
    "ConversationPayloadToMarkdownTransformer",
    "ConversationToJSONTransformer",
]
