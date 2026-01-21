"""
Visit Webpage Tool for fetching and converting web pages to markdown.

Based on smolagents VisitWebpageTool, fetches a URL and converts the HTML
content to markdown for easier processing by LLMs.
"""

import logging
import re

from smolagents import Tool

from .base import TelemetryMixin, with_telemetry

logger = logging.getLogger(__name__)


class VisitWebpageTool(Tool, TelemetryMixin):
    """
    Tool for visiting webpages and extracting content as markdown.

    Fetches the HTML content from a URL and converts it to clean markdown,
    making it easier for agents to process web content.

    Example:
        tool = VisitWebpageTool()
        content = tool.forward("https://example.com")
        print(content)  # Markdown version of the page
    """

    name = "visit_webpage"
    description = (
        "Visits a webpage at the given URL and reads its content as markdown. "
        "Use this to browse webpages, read articles, documentation, or any web content. "
        "Returns the page content converted to readable markdown format."
    )
    inputs = {
        "url": {
            "type": "string",
            "description": "The URL of the webpage to visit (must start with http:// or https://)",
        }
    }
    output_type = "string"

    def __init__(
        self,
        max_output_length: int = 40000,
        timeout: int = 20,
        user_agent: str | None = None,
    ):
        """
        Initialize the VisitWebpageTool.

        Args:
            max_output_length: Maximum characters to return (default 40000)
            timeout: Request timeout in seconds (default 20)
            user_agent: Custom user agent string (optional)
        """
        super().__init__()
        TelemetryMixin.__init__(self)

        self.max_output_length = max_output_length
        self.timeout = timeout
        self.user_agent = user_agent or (
            "Mozilla/5.0 (compatible; ZoeaStudioBot/1.0; +https://zoea.studio)"
        )

    def _truncate_content(self, content: str, max_length: int) -> str:
        """Truncate content if it exceeds max length."""
        if len(content) <= max_length:
            return content
        return (
            content[:max_length]
            + f"\n\n..._Content truncated to {max_length} characters_...\n"
        )

    def _clean_markdown(self, markdown: str) -> str:
        """Clean up markdown content."""
        # Remove excessive newlines (more than 2 consecutive)
        markdown = re.sub(r"\n{3,}", "\n\n", markdown)
        # Remove excessive whitespace
        markdown = re.sub(r"[ \t]+\n", "\n", markdown)
        # Strip leading/trailing whitespace
        return markdown.strip()

    @with_telemetry
    def forward(self, url: str) -> str:
        """
        Fetch a webpage and return its content as markdown.

        Args:
            url: The URL to fetch

        Returns:
            The webpage content converted to markdown, or an error message
        """
        # Validate URL
        if not url:
            return "Error: No URL provided"

        if not url.startswith(("http://", "https://")):
            return f"Error: Invalid URL '{url}'. URL must start with http:// or https://"

        try:
            import requests
            from markdownify import markdownify
            from requests.exceptions import RequestException
        except ImportError as e:
            logger.error(f"Missing dependencies for VisitWebpageTool: {e}")
            return (
                "Error: Missing required packages. "
                "Please install 'markdownify' and 'requests'."
            )

        try:
            headers = {"User-Agent": self.user_agent}
            response = requests.get(url, timeout=self.timeout, headers=headers)
            response.raise_for_status()

            # Convert HTML to markdown
            markdown_content = markdownify(response.text)
            markdown_content = self._clean_markdown(markdown_content)

            # Truncate if necessary
            result = self._truncate_content(markdown_content, self.max_output_length)

            logger.debug(
                f"VisitWebpageTool fetched {url}: {len(result)} chars "
                f"(truncated: {len(markdown_content) > self.max_output_length})"
            )

            return result

        except requests.exceptions.Timeout:
            logger.warning(f"VisitWebpageTool timeout for {url}")
            return f"Error: Request timed out after {self.timeout} seconds. The server may be slow or unresponsive."

        except requests.exceptions.ConnectionError:
            logger.warning(f"VisitWebpageTool connection error for {url}")
            return f"Error: Could not connect to {url}. Please check the URL and try again."

        except requests.exceptions.HTTPError as e:
            status_code = e.response.status_code if e.response else "unknown"
            logger.warning(f"VisitWebpageTool HTTP error {status_code} for {url}")
            return f"Error: HTTP {status_code} - The server returned an error for {url}."

        except RequestException as e:
            logger.error(f"VisitWebpageTool request error for {url}: {e}")
            return f"Error fetching webpage: {str(e)}"

        except Exception as e:
            logger.error(f"VisitWebpageTool unexpected error for {url}: {e}")
            return f"Error: An unexpected error occurred while fetching {url}: {str(e)}"
