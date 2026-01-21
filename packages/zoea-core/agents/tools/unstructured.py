"""
Unstructured.io API Tool for smolagents.

Uses Unstructured.io API for high-quality structured data extraction from documents.
Implements GitHub Issue #102.

References:
- https://docs.unstructured.io/api-reference/api-services/overview
"""

import json
import logging
import time
from pathlib import Path
from typing import Optional

from smolagents import Tool

logger = logging.getLogger(__name__)


class UnstructuredTool(Tool):
    """
    smolagents Tool for extracting structured data from documents using Unstructured.io.

    This tool allows agents to extract structured content from PDFs, images,
    Word documents, and other file formats using Unstructured.io's API.

    Example:
        tool = UnstructuredTool()
        result = tool.forward("/path/to/document.pdf")
    """

    name = "unstructured_extract"
    description = """Extracts structured data from documents using Unstructured.io.
Use this tool to parse PDFs, images, Word documents, and other files into structured text.
Returns extracted text with element types (titles, paragraphs, tables, etc.)."""

    inputs = {
        "file_path": {
            "type": "string",
            "description": "Path to the document file to extract data from",
        },
        "strategy": {
            "type": "string",
            "description": "Extraction strategy: 'auto', 'fast', 'hi_res', 'ocr_only' (default: auto)",
            "nullable": True,
        },
        "output_format": {
            "type": "string",
            "description": "Output format: 'text', 'json', 'markdown' (default: text)",
            "nullable": True,
        },
    }
    output_type = "string"

    VALID_STRATEGIES = ["auto", "fast", "hi_res", "ocr_only"]
    VALID_OUTPUT_FORMATS = ["text", "json", "markdown"]

    # Supported file types
    SUPPORTED_EXTENSIONS = {
        ".pdf",
        ".doc",
        ".docx",
        ".ppt",
        ".pptx",
        ".xls",
        ".xlsx",
        ".txt",
        ".html",
        ".htm",
        ".md",
        ".rst",
        ".rtf",
        ".odt",
        ".epub",
        ".png",
        ".jpg",
        ".jpeg",
        ".tiff",
        ".bmp",
        ".heic",
    }

    def __init__(
        self,
        api_key: Optional[str] = None,
        api_url: str = "https://api.unstructuredapp.io/general/v0/general",
        **kwargs,
    ):
        """
        Initialize the Unstructured.io tool.

        Args:
            api_key: Unstructured.io API key. Falls back to UNSTRUCTURED_API_KEY env var
            api_url: API endpoint URL
        """
        super().__init__(**kwargs)

        import os

        self.api_key = api_key or os.getenv("UNSTRUCTURED_API_KEY")
        if not self.api_key:
            logger.warning(
                "No Unstructured.io API key provided. "
                "Set UNSTRUCTURED_API_KEY environment variable."
            )

        self.api_url = api_url
        self.telemetry = {
            "calls": 0,
            "errors": 0,
            "documents_processed": 0,
            "last_duration_s": None,
        }

    def forward(
        self,
        file_path: str,
        strategy: Optional[str] = None,
        output_format: Optional[str] = None,
    ) -> str:
        """
        Extract structured data from a document.

        Args:
            file_path: Path to the document file
            strategy: Extraction strategy (default: auto)
            output_format: Output format (default: text)

        Returns:
            Extracted content in the specified format, or error message
        """
        self.telemetry["calls"] += 1
        start = time.perf_counter()

        # Validate inputs
        strategy = strategy or "auto"
        output_format = output_format or "text"

        if strategy not in self.VALID_STRATEGIES:
            return f"Error: Invalid strategy '{strategy}'. Valid: {self.VALID_STRATEGIES}"
        if output_format not in self.VALID_OUTPUT_FORMATS:
            return f"Error: Invalid output format '{output_format}'. Valid: {self.VALID_OUTPUT_FORMATS}"

        # Validate file
        path = Path(file_path)
        if not path.exists():
            return f"Error: File not found: {file_path}"

        if path.suffix.lower() not in self.SUPPORTED_EXTENSIONS:
            return f"Error: Unsupported file type '{path.suffix}'. Supported: {sorted(self.SUPPORTED_EXTENSIONS)}"

        if not self.api_key:
            return "Error: No Unstructured.io API key configured"

        try:
            import httpx

            # Prepare the request
            headers = {
                "unstructured-api-key": self.api_key,
                "accept": "application/json",
            }

            # Read file
            with open(path, "rb") as f:
                files = {"files": (path.name, f, self._get_mime_type(path))}
                data = {"strategy": strategy}

                # Make request
                with httpx.Client(timeout=300.0) as client:
                    response = client.post(
                        self.api_url,
                        headers=headers,
                        files=files,
                        data=data,
                    )
                    response.raise_for_status()
                    elements = response.json()

            self.telemetry["documents_processed"] += 1
            self.telemetry["last_duration_s"] = time.perf_counter() - start

            # Format output
            return self._format_output(elements, output_format)

        except httpx.HTTPStatusError as e:
            self.telemetry["errors"] += 1
            logger.error(f"Unstructured.io API error: {e}")
            return f"API error ({e.response.status_code}): {e.response.text[:200]}"
        except Exception as e:
            self.telemetry["errors"] += 1
            logger.error(f"Unstructured.io extraction error: {e}")
            return f"Error extracting data: {e}"

    def _get_mime_type(self, path: Path) -> str:
        """Get MIME type for a file."""
        mime_types = {
            ".pdf": "application/pdf",
            ".doc": "application/msword",
            ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            ".ppt": "application/vnd.ms-powerpoint",
            ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            ".xls": "application/vnd.ms-excel",
            ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            ".txt": "text/plain",
            ".html": "text/html",
            ".htm": "text/html",
            ".md": "text/markdown",
            ".rst": "text/x-rst",
            ".rtf": "application/rtf",
            ".odt": "application/vnd.oasis.opendocument.text",
            ".epub": "application/epub+zip",
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".tiff": "image/tiff",
            ".bmp": "image/bmp",
            ".heic": "image/heic",
        }
        return mime_types.get(path.suffix.lower(), "application/octet-stream")

    def _format_output(self, elements: list, output_format: str) -> str:
        """Format extracted elements into the requested format."""
        if output_format == "json":
            return json.dumps(elements, indent=2)

        if output_format == "markdown":
            return self._to_markdown(elements)

        # Default: text
        return self._to_text(elements)

    def _to_text(self, elements: list) -> str:
        """Convert elements to plain text."""
        parts = []
        for element in elements:
            text = element.get("text", "")
            if text:
                parts.append(text)
        return "\n\n".join(parts)

    def _to_markdown(self, elements: list) -> str:
        """Convert elements to markdown format."""
        parts = []
        for element in elements:
            element_type = element.get("type", "")
            text = element.get("text", "")

            if not text:
                continue

            # Format based on element type
            if element_type == "Title":
                parts.append(f"# {text}")
            elif element_type == "Header":
                parts.append(f"## {text}")
            elif element_type == "ListItem":
                parts.append(f"- {text}")
            elif element_type == "Table":
                # Tables come as text, try to preserve
                parts.append(f"```\n{text}\n```")
            elif element_type == "FigureCaption":
                parts.append(f"*{text}*")
            elif element_type == "NarrativeText":
                parts.append(text)
            else:
                parts.append(text)

        return "\n\n".join(parts)
