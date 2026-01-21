"""
Webpage Summarizer Tool for fetching and summarizing web pages.

Fetches a URL, converts content to markdown, uses an LLM to generate
a summary, and saves the summary as a markdown artifact.

Implements GitHub Issue #109.
"""

import logging
import re
import time

from asgiref.sync import async_to_sync

from llm_providers import (
    ChatMessage,
    LLMProviderRegistry,
    resolve_llm_config,
)

from .base import ZoeaTool

logger = logging.getLogger(__name__)


class WebpageSummarizerTool(ZoeaTool):
    """
    Tool for fetching webpages and generating summaries.

    Fetches a URL, converts the HTML to markdown, uses an LLM to summarize
    the content, and saves the summary as a markdown artifact.

    Extends ZoeaTool to support direct artifact creation via create_artifact().

    Example:
        tool = WebpageSummarizerTool()
        result = tool.forward("https://example.com/article")
    """

    name = "summarize_webpage"
    description = (
        "PREFERRED tool for summarizing web pages. Fetches a URL, extracts the content, "
        "and uses AI to generate a well-structured summary. Always use this tool instead of "
        "visit_webpage when the user asks for a summary, overview, or key points from a URL. "
        "The summary is automatically saved as a reusable markdown artifact. "
        "Supports optional 'focus' parameter to emphasize specific aspects of the content."
    )
    inputs = {
        "url": {
            "type": "string",
            "description": "The URL of the webpage to summarize (must start with http:// or https://)",
        },
        "focus": {
            "type": "string",
            "description": "Optional focus area for the summary (e.g., 'technical details', 'main arguments')",
            "nullable": True,
        },
    }
    output_type = "string"

    # Default summarization prompt
    SUMMARY_SYSTEM_PROMPT = """You are a skilled content summarizer. Your task is to read webpage content and provide clear, concise summaries.

Guidelines:
- Extract the main topic and key points
- Preserve important facts, figures, and conclusions
- Use bullet points for multiple key points
- Keep the summary focused and readable
- If the content has a clear structure (intro, sections, conclusion), reflect that
- Aim for 200-400 words unless the content is very short"""

    SUMMARY_USER_PROMPT = """Please summarize the following webpage content:

---
{content}
---

{focus_instruction}

Provide a well-structured summary in markdown format."""

    def __init__(
        self,
        max_content_length: int = 30000,
        timeout: int = 20,
        user_agent: str | None = None,
        **kwargs,
    ):
        """
        Initialize the WebpageSummarizerTool.

        Args:
            max_content_length: Maximum characters of content to send to LLM (default 30000)
            timeout: Request timeout in seconds (default 20)
            user_agent: Custom user agent string (optional)
            **kwargs: Passed to ZoeaTool (including output_collection)
        """
        super().__init__(**kwargs)

        self.max_content_length = max_content_length
        self.timeout = timeout
        self.user_agent = user_agent or (
            "Mozilla/5.0 (compatible; ZoeaStudioBot/1.0; +https://zoea.studio)"
        )

        # Additional telemetry
        self.telemetry["pages_summarized"] = 0

    def _truncate_content(self, content: str, max_length: int) -> str:
        """Truncate content if it exceeds max length."""
        if len(content) <= max_length:
            return content
        return content[:max_length] + "\n\n[Content truncated for summarization]"

    def _clean_markdown(self, markdown: str) -> str:
        """Clean up markdown content."""
        # Remove excessive newlines (more than 2 consecutive)
        markdown = re.sub(r"\n{3,}", "\n\n", markdown)
        # Remove excessive whitespace
        markdown = re.sub(r"[ \t]+\n", "\n", markdown)
        # Strip leading/trailing whitespace
        return markdown.strip()

    def _extract_title(self, html: str) -> str | None:
        """Extract title from HTML content."""
        import re

        title_match = re.search(r"<title[^>]*>([^<]+)</title>", html, re.IGNORECASE)
        if title_match:
            return title_match.group(1).strip()
        return None

    def _fetch_webpage(self, url: str) -> tuple[str, str | None, str | None]:
        """
        Fetch webpage content and convert to markdown.

        Returns:
            Tuple of (markdown_content, title, error_message)
        """
        try:
            import requests
            from markdownify import markdownify
        except ImportError as e:
            logger.error(f"Missing dependencies for WebpageSummarizerTool: {e}")
            return "", None, "Error: Missing required packages. Please install 'markdownify' and 'requests'."

        try:
            headers = {"User-Agent": self.user_agent}
            response = requests.get(url, timeout=self.timeout, headers=headers)
            response.raise_for_status()

            # Extract title before converting to markdown
            title = self._extract_title(response.text)

            # Convert HTML to markdown
            markdown_content = markdownify(response.text)
            markdown_content = self._clean_markdown(markdown_content)

            return markdown_content, title, None

        except requests.exceptions.Timeout:
            return "", None, f"Error: Request timed out after {self.timeout} seconds."

        except requests.exceptions.ConnectionError:
            return "", None, f"Error: Could not connect to {url}."

        except requests.exceptions.HTTPError as e:
            status_code = e.response.status_code if e.response else "unknown"
            return "", None, f"Error: HTTP {status_code} from {url}."

        except Exception as e:
            logger.error(f"WebpageSummarizerTool fetch error for {url}: {e}")
            return "", None, f"Error fetching webpage: {str(e)}"

    def _summarize_content(self, content: str, focus: str | None = None) -> tuple[str, str | None]:
        """
        Use LLM to summarize the content.

        Returns:
            Tuple of (summary, error_message)
        """
        try:
            # Get LLM configuration
            config = resolve_llm_config(project=None)
            provider = LLMProviderRegistry.get(config.provider, config=config)

            # Build focus instruction
            focus_instruction = ""
            if focus:
                focus_instruction = f"Focus particularly on: {focus}"

            # Build messages
            messages = [
                ChatMessage(role="system", content=self.SUMMARY_SYSTEM_PROMPT),
                ChatMessage(
                    role="user",
                    content=self.SUMMARY_USER_PROMPT.format(
                        content=content,
                        focus_instruction=focus_instruction,
                    ),
                ),
            ]

            # Call LLM (sync wrapper for async call)
            response = async_to_sync(provider.chat_async)(messages)

            return response.content, None

        except Exception as e:
            logger.error(f"WebpageSummarizerTool LLM error: {e}")
            return "", f"Error generating summary: {str(e)}"

    def forward(self, url: str, focus: str | None = None) -> str:
        """
        Fetch a webpage, summarize it, and save as artifact.

        Args:
            url: The URL to summarize
            focus: Optional focus area for the summary

        Returns:
            Human-readable message about the result with the summary
        """
        start = time.perf_counter()

        # Validate URL
        if not url:
            return "Error: No URL provided"

        if not url.startswith(("http://", "https://")):
            return f"Error: Invalid URL '{url}'. URL must start with http:// or https://"

        # Step 1: Fetch webpage content
        content, title, error = self._fetch_webpage(url)
        if error:
            duration = time.perf_counter() - start
            self.record_call(duration, error=True)
            return error

        if not content or len(content.strip()) < 100:
            duration = time.perf_counter() - start
            self.record_call(duration, error=True)
            return f"Error: The webpage at {url} has insufficient content to summarize."

        # Step 2: Truncate content for LLM
        truncated_content = self._truncate_content(content, self.max_content_length)

        # Step 3: Generate summary using LLM
        summary, error = self._summarize_content(truncated_content, focus)
        if error:
            duration = time.perf_counter() - start
            self.record_call(duration, error=True)
            return error

        # Step 4: Format the complete summary with metadata
        page_title = title or "Untitled Page"
        full_summary = f"""# Summary: {page_title}

**Source:** {url}

---

{summary}
"""

        # Step 5: Create artifact
        artifact_title = f"Summary: {page_title[:50]}{'...' if len(page_title) > 50 else ''}"
        content_hash = hash(summary) & 0xFFFFFF
        self.create_artifact(
            type="markdown",
            path=f"_summary_{content_hash:06x}",
            mime_type="text/markdown",
            title=artifact_title,
            content=full_summary,
        )

        self.telemetry["pages_summarized"] += 1
        duration = time.perf_counter() - start
        self.record_call(duration)

        logger.info(f"WebpageSummarizerTool summarized {url} in {duration:.2f}s")

        return full_summary
