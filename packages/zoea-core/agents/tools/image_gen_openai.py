"""
OpenAI Image Generation Tool for smolagents.

Uses OpenAI's DALL-E models (gpt-image-1) for image generation.
Implements GitHub Issue #97.
"""

import base64
import logging
import time
from pathlib import Path

from django.conf import settings
from openai import OpenAI

from .base import ZoeaTool

logger = logging.getLogger(__name__)


class OpenAIImageGenTool(ZoeaTool):
    """
    smolagents Tool for generating images using OpenAI's DALL-E models.

    This tool allows agents to generate images from text descriptions.
    Generated images are saved to a specified directory and the path is returned.

    Extends ZoeaTool to support direct artifact creation via create_artifact().

    Example:
        tool = OpenAIImageGenTool(output_dir="/tmp/generated_images")
        result = tool.forward("A serene mountain landscape at sunset")
    """

    name = "image_gen_openai"
    description = """Generates images from text descriptions using OpenAI's DALL-E.
Use this tool when you need to create an image based on a text description.
Returns a message about the generated image."""

    inputs = {
        "prompt": {
            "type": "string",
            "description": "Detailed description of the image to generate",
        },
        "size": {
            "type": "string",
            "description": (
                "Image size: '1024x1024', '1536x1024', or '1024x1536' (default: 1024x1024)"
            ),
            "nullable": True,
        },
        "quality": {
            "type": "string",
            "description": "Image quality: 'low', 'medium', or 'high' (default: medium)",
            "nullable": True,
        },
    }
    output_type = "string"

    VALID_SIZES = ["1024x1024", "1536x1024", "1024x1536"]
    VALID_QUALITIES = ["low", "medium", "high"]

    def __init__(
        self,
        output_dir: str | None = None,
        model: str = "gpt-image-1",
        **kwargs,
    ):
        """
        Initialize the OpenAI image generation tool.

        Args:
            output_dir: Directory to save generated images. Defaults to MEDIA_ROOT/generated_images
            model: OpenAI model to use (default: gpt-image-1)
            **kwargs: Passed to ZoeaTool (including output_collection)
        """
        super().__init__(**kwargs)
        self.client = OpenAI(api_key=settings.OPENAI_API_KEY)
        self._model_name = model

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
        size: str | None = None,
        quality: str | None = None,
    ) -> str:
        """
        Generate an image from a text prompt.

        Args:
            prompt: Description of the image to generate
            size: Image dimensions (default: 1024x1024)
            quality: Image quality level (default: medium)

        Returns:
            Human-readable message about the result
        """
        start = time.perf_counter()

        # Validate and set defaults
        size = size or "1024x1024"
        quality = quality or "medium"

        if size not in self.VALID_SIZES:
            return f"Error: Invalid size '{size}'. Valid sizes: {self.VALID_SIZES}"

        if quality not in self.VALID_QUALITIES:
            return f"Error: Invalid quality '{quality}'. Valid qualities: {self.VALID_QUALITIES}"

        try:
            # Call OpenAI API
            response = self.client.images.generate(
                model=self._model_name,
                prompt=prompt,
                n=1,
                size=size,
                quality=quality,
            )

            # Get image data
            image_data = response.data[0]

            # Generate unique filename
            timestamp = int(time.time() * 1000)
            filename = f"openai_{timestamp}.png"
            filepath = self.output_dir / filename

            # Save image (handle both URL and b64_json responses)
            if hasattr(image_data, "b64_json") and image_data.b64_json:
                # Decode base64 and save
                image_bytes = base64.b64decode(image_data.b64_json)
                with open(filepath, "wb") as f:
                    f.write(image_bytes)
            elif hasattr(image_data, "url") and image_data.url:
                # Download from URL
                import httpx

                with httpx.Client() as http_client:
                    img_response = http_client.get(image_data.url)
                    img_response.raise_for_status()
                    with open(filepath, "wb") as f:
                        f.write(img_response.content)
            else:
                return "Error: No image data received from OpenAI"

            self.telemetry["images_generated"] += 1
            duration = time.perf_counter() - start
            self.record_call(duration)

            # Create artifact directly via ZoeaTool method
            title = f"Generated: {prompt[:50]}{'...' if len(prompt) > 50 else ''}"
            self.create_artifact(
                type="image",
                path=str(filepath),
                mime_type="image/png",
                title=title,
            )

            return f"Image generated successfully: {filename}"

        except Exception as e:
            duration = time.perf_counter() - start
            self.record_call(duration, error=True)
            logger.error(f"OpenAI image generation error: {e}")
            return f"Error generating image: {e}"
