"""
Image Analyzer Tool for smolagents.

Uses OpenAI's vision capabilities to analyze image documents.
"""

import base64
from pathlib import Path

from django.conf import settings
from openai import OpenAI
from smolagents import Tool


class ImageAnalyzerTool(Tool):
    """
    smolagents Tool for analyzing image documents using vision models.

    This tool allows the CodeAgent to understand and describe
    image content for multimodal RAG scenarios.
    """

    name = "image_analyzer"
    description = """Analyzes an image document and returns a detailed description.
Use this tool when you need to understand the content of an image.
Provide the image path or document ID to analyze."""

    inputs = {
        "image_path": {
            "type": "string",
            "description": "Path to the image file to analyze",
        },
        "question": {
            "type": "string",
            "description": "Optional specific question about the image",
            "nullable": True,
        },
    }
    output_type = "string"

    def __init__(self, **kwargs):
        """Initialize the image analyzer with OpenAI client."""
        super().__init__(**kwargs)
        self.client = OpenAI(api_key=settings.OPENAI_API_KEY)

    def forward(self, image_path: str, question: str | None = None) -> str:
        """
        Analyze an image and return a description.

        Args:
            image_path: Path to the image file
            question: Optional specific question about the image

        Returns:
            Description or answer about the image content
        """
        try:
            # Read and encode image
            path = Path(image_path)
            if not path.exists():
                return f"Error: Image file not found at {image_path}"

            with open(path, "rb") as f:
                image_data = base64.b64encode(f.read()).decode("utf-8")

            # Determine MIME type
            suffix = path.suffix.lower()
            mime_types = {
                ".jpg": "image/jpeg",
                ".jpeg": "image/jpeg",
                ".png": "image/png",
                ".gif": "image/gif",
                ".webp": "image/webp",
            }
            mime_type = mime_types.get(suffix, "image/jpeg")

            # Build prompt
            prompt = (
                question
                or "Describe this image in detail, including any text, diagrams, or relevant information visible."
            )

            # Call OpenAI vision API
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:{mime_type};base64,{image_data}",
                                },
                            },
                        ],
                    }
                ],
                max_tokens=1000,
            )

            return response.choices[0].message.content

        except Exception as e:
            return f"Error analyzing image: {e}"
