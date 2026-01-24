"""
summarize_content workflow module.

Summarizes content from various sources (document, folder)
and produces a MarkdownDocument output.
"""

from .graph import build_graph

__all__ = ["build_graph"]
