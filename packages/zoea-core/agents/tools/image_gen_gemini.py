"""
Gemini Image Generation Tool for smolagents (Nano Banana).

Uses Google's Gemini 2.0 Flash with image generation capabilities.
"Nano Banana" is the community nickname for Gemini's image generation models.
Implements GitHub Issue #96.

References:
- https://ai.google.dev/gemini-api/docs/image-generation
"""

import base64
import logging
import time
from pathlib import Path

from .base import ZoeaTool

logger = logging.getLogger(__name__)


class GeminiImageGenTool(ZoeaTool):
    """
    smolagents Tool for generating images using Google's Gemini models.

    This tool allows agents to generate images using Gemini 2.0 Flash
    (community name: "Nano Banana") via the Gemini API.

    Extends ZoeaTool to support direct artifact creation via create_artifact().

    Example:
        tool = GeminiImageGenTool(output_dir="/tmp/generated_images")
        result = tool.forward("A cozy coffee shop interior with warm lighting")
    """

    name = "image_gen_gemini"
    description = """Generates images from text descriptions using Google's Gemini (Nano Banana).
Use this tool when you need to create an image using Google's AI image generation.
Returns a message about the generated image."""

    inputs = {
        "prompt": {
            "type": "string",
            "description": "Detailed description of the image to generate",
        },
        "aspect_ratio": {
            "type": "string",
            "description": "Aspect ratio: '1:1', '16:9', '9:16', '4:3', '3:4' (default: 1:1)",
            "nullable": True,
        },
    }
    output_type = "string"

    # Model that supports image generation
    DEFAULT_MODEL = "gemini-2.0-flash-exp"
    VALID_ASPECT_RATIOS = ["1:1", "16:9", "9:16", "4:3", "3:4"]

    def __init__(
        self,
        output_dir: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
        **kwargs,
    ):
        """
        Initialize the Gemini image generation tool.

        Args:
            output_dir: Directory to save generated images. Defaults to MEDIA_ROOT/generated_images
            api_key: Gemini API key. Falls back to GEMINI_API_KEY env var
            model: Model to use (default: gemini-2.0-flash-exp)
            **kwargs: Passed to ZoeaTool (including output_collection)
        """
        super().__init__(**kwargs)

        import os

        from django.conf import settings

        self.api_key = api_key or os.getenv("GEMINI_API_KEY") or getattr(
            settings, "GEMINI_API_KEY", None
        )
        if not self.api_key:
            logger.warning(
                "No Gemini API key provided. Set GEMINI_API_KEY environment variable."
            )

        self._model_name = model or self.DEFAULT_MODEL

        # Set up output directory
        if output_dir:
            self.output_dir = Path(output_dir)
        else:
            self.output_dir = Path(settings.MEDIA_ROOT) / "generated_images"
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Additional telemetry beyond what TelemetryMixin provides
        self.telemetry["images_generated"] = 0

    def forward(
        self,
        prompt: str,
        aspect_ratio: str | None = None,
    ) -> str:
        """
        Generate an image from a text prompt.

        Args:
            prompt: Description of the image to generate
            aspect_ratio: Desired aspect ratio (default: 1:1)

        Returns:
            Human-readable message about the result
        """
        start = time.perf_counter()

        # Validate aspect ratio
        aspect_ratio = aspect_ratio or "1:1"
        if aspect_ratio not in self.VALID_ASPECT_RATIOS:
            return (
                f"Error: Invalid aspect ratio '{aspect_ratio}'. "
                f"Valid: {self.VALID_ASPECT_RATIOS}"
            )

        if not self.api_key:
            return "Error: No Gemini API key configured"

        try:
            import google.generativeai as genai
            from google.generativeai.types import GenerationConfig

            # Configure the API
            genai.configure(api_key=self.api_key)

            # Create the model with image generation config
            model = genai.GenerativeModel(
                model_name=self._model_name,
                generation_config=GenerationConfig(
                    response_modalities=["image", "text"],
                ),
            )

            # Generate image
            response = model.generate_content(
                f"Generate an image: {prompt}",
            )

            # Extract image from response
            image_data = None
            mime_type = "image/png"
            for part in response.parts:
                if hasattr(part, "inline_data") and part.inline_data:
                    if part.inline_data.mime_type.startswith("image/"):
                        image_data = part.inline_data.data
                        mime_type = part.inline_data.mime_type
                        break

            if not image_data:
                # Check if there's a text response explaining why
                text_response = ""
                for part in response.parts:
                    if hasattr(part, "text"):
                        text_response += part.text
                return f"No image generated. Model response: {text_response[:200]}"

            # Determine file extension
            ext = "png"
            if "jpeg" in mime_type:
                ext = "jpg"
            elif "webp" in mime_type:
                ext = "webp"

            # Save image
            timestamp = int(time.time() * 1000)
            filename = f"gemini_{timestamp}.{ext}"
            filepath = self.output_dir / filename

            # Decode and save
            if isinstance(image_data, str):
                image_bytes = base64.b64decode(image_data)
            else:
                image_bytes = image_data

            with open(filepath, "wb") as f:
                f.write(image_bytes)

            self.telemetry["images_generated"] += 1
            duration = time.perf_counter() - start
            self.record_call(duration)

            # Create artifact directly via ZoeaTool method
            title = f"Generated: {prompt[:50]}{'...' if len(prompt) > 50 else ''}"
            self.create_artifact(
                type="image",
                path=str(filepath),
                mime_type=mime_type,
                title=title,
            )

            return f"Image generated successfully: {filename}"

        except Exception as e:
            duration = time.perf_counter() - start
            self.record_call(duration, error=True)
            logger.error(f"Gemini image generation error: {e}")
            return f"Error generating image: {e}"


# Alias for the community nickname
NanoBananaTool = GeminiImageGenTool
