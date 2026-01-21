"""
Hugging Face Image Generation Tool for smolagents.

Uses Hugging Face's Inference API for image generation with open/free models.
Implements GitHub Issue #98.
"""

import logging
import time
from pathlib import Path

from django.conf import settings

from .base import ZoeaTool

logger = logging.getLogger(__name__)


class HuggingFaceImageGenTool(ZoeaTool):
    """
    smolagents Tool for generating images using Hugging Face Inference API.

    This tool allows agents to generate images using open-source models
    like Stable Diffusion, FLUX, etc. via the Hugging Face Inference API.

    Extends ZoeaTool to support direct artifact creation via create_artifact().

    Example:
        tool = HuggingFaceImageGenTool(output_dir="/tmp/generated_images")
        result = tool.forward("A futuristic city with flying cars")
    """

    name = "image_gen_huggingface"
    description = """Generates images from text descriptions using Hugging Face models.
Use this tool when you need to create an image using open-source AI models.
Returns a message about the generated image."""

    inputs = {
        "prompt": {
            "type": "string",
            "description": "Detailed description of the image to generate",
        },
        "negative_prompt": {
            "type": "string",
            "description": "Things to avoid in the generated image (optional)",
            "nullable": True,
        },
        "model": {
            "type": "string",
            "description": "Model ID to use (default: stabilityai/stable-diffusion-xl-base-1.0)",
            "nullable": True,
        },
    }
    output_type = "string"

    # Popular free/open models for image generation
    DEFAULT_MODEL = "stabilityai/stable-diffusion-xl-base-1.0"
    RECOMMENDED_MODELS = [
        "stabilityai/stable-diffusion-xl-base-1.0",
        "black-forest-labs/FLUX.1-schnell",
        "runwayml/stable-diffusion-v1-5",
    ]

    def __init__(
        self,
        output_dir: str | None = None,
        api_token: str | None = None,
        default_model: str | None = None,
        **kwargs,
    ):
        """
        Initialize the Hugging Face image generation tool.

        Args:
            output_dir: Directory to save generated images. Defaults to MEDIA_ROOT/generated_images
            api_token: Hugging Face API token. Falls back to HF_API_TOKEN env var
            default_model: Default model to use if not specified in forward()
            **kwargs: Passed to ZoeaTool (including output_collection)
        """
        super().__init__(**kwargs)

        # Get API token
        import os

        self.api_token = api_token or os.getenv("HF_API_TOKEN")
        if not self.api_token:
            logger.warning(
                "No Hugging Face API token provided. "
                "Set HF_API_TOKEN environment variable for authenticated access."
            )

        self.default_model = default_model or self.DEFAULT_MODEL

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
        negative_prompt: str | None = None,
        model: str | None = None,
    ) -> str:
        """
        Generate an image from a text prompt.

        Args:
            prompt: Description of the image to generate
            negative_prompt: Things to avoid in the image
            model: Model ID to use (defaults to SDXL)

        Returns:
            Human-readable message about the result
        """
        start = time.perf_counter()
        model_id = model or self.default_model

        try:
            import httpx

            # Build API URL
            api_url = f"https://api-inference.huggingface.co/models/{model_id}"

            # Build headers
            headers = {}
            if self.api_token:
                headers["Authorization"] = f"Bearer {self.api_token}"

            # Build payload
            payload = {"inputs": prompt}
            if negative_prompt:
                payload["parameters"] = {"negative_prompt": negative_prompt}

            # Make request
            with httpx.Client(timeout=120.0) as client:
                response = client.post(api_url, headers=headers, json=payload)

                # Handle model loading (503)
                if response.status_code == 503:
                    duration = time.perf_counter() - start
                    self.record_call(duration, error=True)
                    return (
                        f"Model {model_id} is loading. Please try again in a few seconds. "
                        f"Response: {response.text}"
                    )

                response.raise_for_status()

                # Check content type
                content_type = response.headers.get("content-type", "")
                if "image" not in content_type:
                    duration = time.perf_counter() - start
                    self.record_call(duration, error=True)
                    return (
                        f"Unexpected response type: {content_type}. "
                        f"Response: {response.text[:200]}"
                    )

                # Save image
                timestamp = int(time.time() * 1000)
                # Determine extension from content type
                ext = "png"
                if "jpeg" in content_type:
                    ext = "jpg"
                elif "webp" in content_type:
                    ext = "webp"

                filename = f"hf_{timestamp}.{ext}"
                filepath = self.output_dir / filename

                with open(filepath, "wb") as f:
                    f.write(response.content)

            self.telemetry["images_generated"] += 1
            duration = time.perf_counter() - start
            self.record_call(duration)

            # Determine MIME type from content type
            mime_type = "image/png"
            if "jpeg" in content_type:
                mime_type = "image/jpeg"
            elif "webp" in content_type:
                mime_type = "image/webp"

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
            logger.error(f"Hugging Face image generation error: {e}")
            return f"Error generating image: {e}"
