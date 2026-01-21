"""
Image captioning service for Image documents.
"""

from __future__ import annotations

import base64
import logging
from pathlib import Path

from django.conf import settings
from openai import OpenAI

from llm_providers import get_provider_api_key

from .models import Image, ImageCaption

logger = logging.getLogger(__name__)

DEFAULT_PROMPT = (
    "Write a concise, descriptive caption for search indexing. "
    "Include any visible text, diagrams, labels, or notable objects."
)


def get_or_create_image_caption(
    image: Image,
    *,
    provider: str | None = None,
    model: str | None = None,
    force: bool = False,
) -> str | None:
    """
    Fetch or generate a caption for an Image document.

    Args:
        image: Image document instance.
        provider: Optional provider override (default from settings).
        model: Optional model override (default from settings).
        force: If True, regenerate even if a caption exists.
    """
    provider = (provider or getattr(settings, "IMAGE_CAPTION_PROVIDER", "openai")).lower()
    model = model or getattr(settings, "IMAGE_CAPTION_MODEL", "gpt-4o")

    if provider != "openai":
        logger.warning("Image caption provider '%s' is not supported", provider)
        return None

    existing = ImageCaption.objects.filter(
        image=image,
        provider=provider,
        model=model,
    ).first()

    if existing and not force and existing.updated_at >= image.updated_at:
        return existing.caption

    if not image.image_file:
        return None

    api_key = get_provider_api_key("openai", image.project)
    if not api_key:
        logger.warning("No OpenAI API key available for image captioning")
        return existing.caption if existing else None

    caption = _generate_openai_caption(
        image.image_file.path,
        api_key=api_key,
        model=model,
        prompt=getattr(settings, "IMAGE_CAPTION_PROMPT", None) or DEFAULT_PROMPT,
    )
    if not caption:
        return existing.caption if existing else None

    if existing:
        existing.caption = caption
        existing.save(update_fields=["caption", "updated_at"])
        return existing.caption

    new_caption = ImageCaption.objects.create(
        image=image,
        provider=provider,
        model=model,
        caption=caption,
    )
    return new_caption.caption


def _generate_openai_caption(image_path: str, *, api_key: str, model: str, prompt: str) -> str | None:
    """Call OpenAI vision model to caption the image."""
    path = Path(image_path)
    if not path.exists():
        logger.warning("Image path does not exist: %s", image_path)
        return None

    suffix = path.suffix.lower()
    mime_types = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".gif": "image/gif",
        ".webp": "image/webp",
    }
    mime_type = mime_types.get(suffix, "image/jpeg")

    try:
        with path.open("rb") as handle:
            image_data = base64.b64encode(handle.read()).decode("utf-8")

        client = OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:{mime_type};base64,{image_data}"},
                        },
                    ],
                }
            ],
            max_tokens=400,
        )
        return response.choices[0].message.content.strip()
    except Exception as exc:  # noqa: BLE001 - external call
        logger.warning("Image captioning failed: %s", exc)
        return None
