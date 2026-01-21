"""
Web Search Tool for smolagents.

Provides web search capabilities using DuckDuckGo Search (DDGS).
This tool allows agents to search the web for current information.
"""

import logging
import time
from typing import Optional

from smolagents import Tool

logger = logging.getLogger(__name__)


class WebSearchTool(Tool):
    """
    Web search tool using DuckDuckGo.

    Wraps the DDGS library to provide web search capabilities
    for smolagents-based agents with telemetry support.

    Example:
        tool = WebSearchTool()
        result = tool.forward("latest Python news")
    """

    name = "web_search"
    description = """Performs a web search and returns the top results.
Use this tool to find current information, research topics, or verify facts.
Returns formatted search results with titles, URLs, and snippets."""

    inputs = {
        "query": {
            "type": "string",
            "description": "The search query to perform",
        },
        "max_results": {
            "type": "integer",
            "description": "Maximum number of results to return (default: 5)",
            "nullable": True,
        },
    }
    output_type = "string"

    def __init__(
        self,
        max_results: int = 5,
        rate_limit: float = 1.0,
        **kwargs,
    ):
        """
        Initialize the web search tool.

        Args:
            max_results: Default maximum number of results to return
            rate_limit: Minimum seconds between requests (for rate limiting)
        """
        super().__init__(**kwargs)
        self.max_results = max_results
        self.rate_limit = rate_limit
        self._ddgs = None
        self._last_request_time = 0.0
        self.telemetry = {
            "calls": 0,
            "errors": 0,
            "last_duration_s": None,
        }

    def _get_ddgs(self):
        """Lazy initialization of DDGS client."""
        if self._ddgs is None:
            try:
                from ddgs import DDGS

                self._ddgs = DDGS()
            except ImportError:
                raise ImportError("Install ddgs package: uv add ddgs")
        return self._ddgs

    def _rate_limit_wait(self):
        """Enforce rate limiting between requests."""
        elapsed = time.time() - self._last_request_time
        if elapsed < self.rate_limit:
            time.sleep(self.rate_limit - elapsed)
        self._last_request_time = time.time()

    def forward(self, query: str, max_results: Optional[int] = None) -> str:
        """
        Execute web search.

        Args:
            query: Search query
            max_results: Maximum number of results (defaults to instance setting)

        Returns:
            Formatted string with search results
        """
        self.telemetry["calls"] += 1
        start = time.perf_counter()

        try:
            self._rate_limit_wait()
            ddgs = self._get_ddgs()

            results = list(
                ddgs.text(
                    query,
                    max_results=max_results or self.max_results,
                )
            )

            if not results:
                return "No search results found. Try a different query."

            # Format results
            formatted = ["## Web Search Results\n"]
            for i, result in enumerate(results, 1):
                title = result.get("title", "No title")
                href = result.get("href", "")
                body = result.get("body", "")
                formatted.append(f"### [{i}] {title}\n" f"URL: {href}\n" f"{body}\n")

            self.telemetry["last_duration_s"] = time.perf_counter() - start
            return "\n".join(formatted)

        except Exception as e:
            self.telemetry["errors"] += 1
            logger.error(f"Web search error: {e}")
            return f"Search error: {e!s}"
