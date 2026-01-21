"""Output format enumerations for transformations.

This module defines all sanctioned output formats as an enum to ensure
type safety and prevent typos in registration and transformation calls.
"""

from enum import Enum


class OutputFormat(str, Enum):
    """Supported output formats for content transformations.

    Using str as the mixin allows these to be used directly in comparisons
    and serialization contexts while maintaining enum safety.
    """

    # Text-based formats
    MARKDOWN = "markdown"
    JSON = "json"
    OUTLINE = "outline"  # Hierarchical tree structure

    # Diagram formats
    REACTFLOW = "reactflow_diagram"  # React Flow compatible data structure
    D2 = "d2_diagram"  # D2 markup language

    # AI/Agent formats
    SYSTEM_MESSAGE = "system_message"  # System prompt for AI agents
    USER_PROMPT = "user_prompt"  # User-facing prompt

    # Future formats can be added here
    # XML = "xml"
    # HTML = "html"
    # LATEX = "latex"


__all__ = ["OutputFormat"]
