"""Service for extracting code blocks from conversation messages.

This module parses fenced code blocks from markdown text and creates
artifact items for each extracted code block.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

from documents.artifact_service import ArtifactService
from documents.models import CollectionItemSourceChannel

logger = logging.getLogger(__name__)

# Regex pattern for fenced code blocks
# Matches ```language\n...content...\n``` with optional language specifier
CODE_BLOCK_PATTERN = re.compile(
    r'```(\w*)\n(.*?)```',
    re.DOTALL
)

# Pattern for markdown tables (header row + separator + data rows)
# Matches lines that look like: | col1 | col2 | col3 |
MARKDOWN_TABLE_PATTERN = re.compile(
    r'((?:^[ \t]*\|.+\|[ \t]*$\n?)+)',
    re.MULTILINE
)

# Pattern to validate table structure (has header separator like |---|---|)
TABLE_SEPARATOR_PATTERN = re.compile(r'^\s*\|[-:\s|]+\|\s*$', re.MULTILINE)


@dataclass
class ExtractedCodeBlock:
    """Represents a single extracted code block."""

    language: str
    content: str
    start_pos: int
    end_pos: int


def extract_code_blocks(text: str) -> list[ExtractedCodeBlock]:
    """Extract fenced code blocks from markdown text.

    Args:
        text: The markdown text to parse.

    Returns:
        List of ExtractedCodeBlock instances.
    """
    blocks = []
    for match in CODE_BLOCK_PATTERN.finditer(text):
        language = match.group(1) or 'text'
        content = match.group(2).strip()
        if content:  # Only include non-empty code blocks
            blocks.append(ExtractedCodeBlock(
                language=language,
                content=content,
                start_pos=match.start(),
                end_pos=match.end(),
            ))
    return blocks


def extract_markdown_tables(text: str) -> list[ExtractedCodeBlock]:
    """Extract markdown tables from text.

    Finds markdown tables (rows with | delimiters) that have a proper
    header separator row (|---|---|).

    Args:
        text: The text to parse.

    Returns:
        List of ExtractedCodeBlock instances with language='markdown'.
    """
    tables = []

    for match in MARKDOWN_TABLE_PATTERN.finditer(text):
        table_text = match.group(1).strip()

        # Validate it's a proper table with header separator
        if not TABLE_SEPARATOR_PATTERN.search(table_text):
            continue

        # Skip if it's inside a code block (check for ``` before this position)
        before_text = text[:match.start()]
        open_blocks = before_text.count('```')
        if open_blocks % 2 == 1:
            # Inside a code block, skip
            continue

        # Only include tables with at least 3 rows (header, separator, data)
        rows = [r for r in table_text.split('\n') if r.strip()]
        if len(rows) >= 3:
            tables.append(ExtractedCodeBlock(
                language='markdown',
                content=table_text,
                start_pos=match.start(),
                end_pos=match.end(),
            ))

    return tables


def extract_all_content_blocks(text: str) -> list[ExtractedCodeBlock]:
    """Extract both code blocks and markdown tables from text.

    Args:
        text: The text to parse.

    Returns:
        List of ExtractedCodeBlock instances, sorted by position.
    """
    blocks = extract_code_blocks(text)
    tables = extract_markdown_tables(text)

    # Combine and sort by position
    all_blocks = blocks + tables
    all_blocks.sort(key=lambda b: b.start_pos)

    return all_blocks


def create_artifacts_from_code_blocks(
    conversation,
    message,
    actor,
) -> int:
    """Extract code blocks and markdown tables from a message and create artifacts.

    Args:
        conversation: The conversation the message belongs to.
        message: The message to extract content blocks from.
        actor: The user performing the operation.

    Returns:
        Number of artifacts created.
    """
    if message.role != 'assistant':
        return 0

    # Extract both code blocks and markdown tables
    blocks = extract_all_content_blocks(message.content)
    if not blocks:
        return 0

    service = ArtifactService(actor=actor)
    collection = service.get_or_create_artifacts(conversation)

    created_count = 0
    for i, block in enumerate(blocks):
        service.add_artifact(
            collection,
            source_channel=CollectionItemSourceChannel.CODE,
            source_metadata={
                'language': block.language,
                'code': block.content,
                'message_id': message.id,
                'block_index': i,
                'start_pos': block.start_pos,
                'end_pos': block.end_pos,
            },
        )
        created_count += 1
        logger.debug(
            "Created code block artifact for message %d (language=%s, %d chars)",
            message.id,
            block.language,
            len(block.content),
        )

    if created_count:
        logger.info(
            "Extracted %d code blocks from message %d in conversation %d",
            created_count,
            message.id,
            conversation.id,
        )

    return created_count


def create_artifacts_from_tool_outputs(
    conversation,
    message,
    tool_artifacts: list,
    actor,
) -> int:
    """Persist tool-generated artifacts to the conversation's artifact collection.

    This function takes artifacts from tool execution (images, markdown tables, etc.)
    and stores them in the conversation's artifact collection so they can be
    retrieved when the conversation is reloaded.

    Args:
        conversation: The conversation the message belongs to.
        message: The assistant message that generated these artifacts.
        tool_artifacts: List of ToolArtifactData objects from tool execution.
        actor: The user performing the operation.

    Returns:
        Number of artifacts created.
    """
    if not tool_artifacts:
        return 0

    service = ArtifactService(actor=actor)
    collection = service.get_or_create_artifacts(conversation)

    created_count = 0
    for artifact in tool_artifacts:
        # Build source metadata based on artifact type
        source_metadata = {
            'type': artifact.type,
            'path': artifact.path,
            'message_id': message.id,
        }

        # Add optional fields if present
        if artifact.mime_type:
            source_metadata['mime_type'] = artifact.mime_type
        if artifact.title:
            source_metadata['title'] = artifact.title
        if artifact.language:
            source_metadata['language'] = artifact.language
        if artifact.content:
            source_metadata['content'] = artifact.content

        service.add_artifact(
            collection,
            source_channel=CollectionItemSourceChannel.TOOL,
            source_metadata=source_metadata,
        )
        created_count += 1
        logger.debug(
            "Created tool artifact for message %d (type=%s, path=%s)",
            message.id,
            artifact.type,
            artifact.path,
        )

    if created_count:
        logger.info(
            "Persisted %d tool artifacts from message %d in conversation %d",
            created_count,
            message.id,
            conversation.id,
        )

    return created_count
