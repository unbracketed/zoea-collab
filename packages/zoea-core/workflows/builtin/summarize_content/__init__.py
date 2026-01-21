"""
summarize_content workflow module.

Summarizes content from various sources (document, folder, clipboard)
and produces a MarkdownDocument output.
"""

from .flow import build_flow

__all__ = ["build_flow"]
