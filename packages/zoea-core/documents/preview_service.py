"""Helpers for generating and caching document previews."""

from __future__ import annotations

import hashlib
import html
import io
import logging
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from django.core.files.base import ContentFile
from django.utils import timezone
from PIL import Image as PILImage

logger = logging.getLogger(__name__)

from .models import (
    CSV,
    D2Diagram,
    Document,
    DocumentPreview,
    ExcalidrawDiagram,
    Image,
    Markdown,
    MermaidDiagram,
    PDF,
    ReactFlowDiagram,
    TextDocument,
    YooptaDocument,
)

# Target thumbnail size (width, height)
THUMBNAIL_SIZE = (320, 200)
SNIPPET_LENGTH = 500


@dataclass
class PreviewArtifact:
    file_bytes: bytes | None = None
    file_ext: str = "webp"
    width: int | None = None
    height: int | None = None
    html: str | None = None
    metadata: dict[str, Any] | None = None


def compute_content_hash(document: Document) -> str:
    """Compute a stable hash for the document's previewable content."""
    if hasattr(document, "image_file") and getattr(document, "image_file"):
        document.image_file.open("rb")
        try:
            data = document.image_file.read()
        finally:
            document.image_file.close()
        return hashlib.sha256(data).hexdigest()

    if hasattr(document, "pdf_file") and getattr(document, "pdf_file"):
        document.pdf_file.open("rb")
        try:
            data = document.pdf_file.read()
        finally:
            document.pdf_file.close()
        return hashlib.sha256(data).hexdigest()

    if hasattr(document, "content"):
        payload = (document.content or "") + f"|{document.updated_at.isoformat()}"
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    # Fallback to updated_at to avoid churn
    return hashlib.sha256(str(document.updated_at.timestamp()).encode("utf-8")).hexdigest()


def ensure_preview(document: Document, *, preview_kind: str = "thumbnail", force: bool = False) -> DocumentPreview:
    """Fetch or (re)generate a preview for the document."""
    content_hash = compute_content_hash(document)
    preview = DocumentPreview.objects.filter(document=document, preview_kind=preview_kind).first()

    if (
        preview
        and not force
        and preview.content_hash == content_hash
        and preview.status == DocumentPreview.Status.READY
    ):
        return preview

    if preview is None:
        preview = DocumentPreview(
            document=document,
            organization=document.organization,
            project=document.project,
            preview_kind=preview_kind,
        )

    preview.status = DocumentPreview.Status.PROCESSING
    preview.target_hash = content_hash
    preview.save()

    try:
        artifact = render_preview(document, preview_kind=preview_kind)
        _persist_artifact(preview, artifact, content_hash)
    except Exception as exc:
        preview.mark_failed(str(exc))

    return preview


def render_preview(document: Document, *, preview_kind: str = "thumbnail") -> PreviewArtifact:
    """Render a preview artifact for the provided document."""
    if isinstance(document, Image):
        return _render_image(document)
    if isinstance(document, Markdown):
        return _render_text(document.content or "")
    if isinstance(document, CSV):
        return _render_text(document.content or "")
    if isinstance(document, PDF):
        return _render_pdf(document)
    if isinstance(document, D2Diagram):
        return _render_d2_diagram(document)
    if isinstance(document, MermaidDiagram):
        return _render_mermaid_diagram(document)
    if isinstance(document, ExcalidrawDiagram):
        return _render_excalidraw_diagram(document)
    if isinstance(document, ReactFlowDiagram):
        return _render_text(document.content or "")
    if isinstance(document, YooptaDocument):
        # Use get_text_content() to extract human-readable text from Yoopta JSON
        return _render_text(document.get_text_content())
    if isinstance(document, TextDocument):
        return _render_text(document.content or "")

    return _render_text(document.name)


def _render_image(document: Image) -> PreviewArtifact:
    """Generate thumbnail for image documents."""
    if not document.image_file:
        raise ValueError("Image document has no image file attached")

    document.image_file.open("rb")
    try:
        with PILImage.open(document.image_file) as img:
            img = img.convert("RGB")
            preview_img = _resize_and_crop(img, THUMBNAIL_SIZE)
            buffer = io.BytesIO()
            preview_img.save(buffer, format="WEBP", quality=90)
            file_bytes = buffer.getvalue()
            width, height = preview_img.size
    finally:
        document.image_file.close()

    metadata = {"original_width": getattr(document, "width", None), "original_height": getattr(document, "height", None)}
    return PreviewArtifact(
        file_bytes=file_bytes,
        file_ext="webp",
        width=width,
        height=height,
        metadata=metadata,
    )


def _render_pdf(document: PDF) -> PreviewArtifact:
    """Generate thumbnail from PDF first page."""
    import fitz  # PyMuPDF

    if not document.pdf_file:
        raise ValueError("PDF document has no file attached")

    document.pdf_file.open("rb")
    try:
        pdf_bytes = document.pdf_file.read()
        with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
            if len(doc) == 0:
                return _render_text("(empty PDF)")

            # Render first page at 2x resolution for quality
            page = doc[0]
            mat = fitz.Matrix(2.0, 2.0)  # 2x zoom
            pix = page.get_pixmap(matrix=mat)

            # Convert to PIL Image for consistent processing
            img = PILImage.frombytes("RGB", [pix.width, pix.height], pix.samples)
            preview_img = _resize_and_crop(img, THUMBNAIL_SIZE)
            buffer = io.BytesIO()
            preview_img.save(buffer, format="WEBP", quality=90)
            file_bytes = buffer.getvalue()
            width, height = preview_img.size
    finally:
        document.pdf_file.close()

    metadata = {
        "page_count": document.page_count,
        "source_type": "pdf",
    }
    return PreviewArtifact(
        file_bytes=file_bytes,
        file_ext="webp",
        width=width,
        height=height,
        metadata=metadata,
    )


def _resize_and_crop(image: PILImage.Image, size: tuple[int, int]) -> PILImage.Image:
    """Resize image maintaining aspect ratio then center crop to target size."""
    target_width, target_height = size
    image_ratio = image.width / image.height
    target_ratio = target_width / target_height

    if image_ratio > target_ratio:
        # image is wider than target
        new_height = target_height
        new_width = int(new_height * image_ratio)
    else:
        new_width = target_width
        new_height = int(new_width / image_ratio)

    resized = image.resize((new_width, new_height), PILImage.LANCZOS)

    left = (new_width - target_width) / 2
    top = (new_height - target_height) / 2
    right = left + target_width
    bottom = top + target_height
    return resized.crop((left, top, right, bottom))


def _render_text(text: str) -> PreviewArtifact:
    """Render simple HTML snippet for text-based content."""
    snippet = (text or "").strip()[:SNIPPET_LENGTH]
    html_snippet = f"<pre class='doc-preview-snippet'>{html.escape(snippet)}</pre>"
    return PreviewArtifact(
        html=html_snippet,
        metadata={"text_snippet": snippet},
    )


def _render_d2_diagram(document: D2Diagram) -> PreviewArtifact:
    """Render D2 diagram to SVG using the d2 CLI."""
    content = document.content or ""
    if not content.strip():
        return _render_text("(empty diagram)")

    # Check if d2 CLI is available
    d2_path = shutil.which("d2")
    if not d2_path:
        logger.warning("d2 CLI not found, falling back to text preview")
        return _render_text(content)

    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            input_path = Path(tmpdir) / "diagram.d2"
            output_path = Path(tmpdir) / "diagram.svg"

            # Write D2 source to temp file
            input_path.write_text(content, encoding="utf-8")

            # Run d2 CLI to generate SVG
            # --theme 200 = Dark Mauve (matches frontend default)
            # --layout dagre = consistent with frontend
            result = subprocess.run(
                [
                    d2_path,
                    "--theme", "200",
                    "--layout", "dagre",
                    str(input_path),
                    str(output_path),
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.returncode != 0:
                logger.warning(f"d2 CLI failed: {result.stderr}")
                return _render_text(content)

            if not output_path.exists():
                logger.warning("d2 did not produce output file")
                return _render_text(content)

            svg_bytes = output_path.read_bytes()

            return PreviewArtifact(
                file_bytes=svg_bytes,
                file_ext="svg",
                metadata={"format": "svg", "source_lines": len(content.splitlines())},
            )

    except subprocess.TimeoutExpired:
        logger.warning("d2 CLI timed out")
        return _render_text(content)
    except Exception as exc:
        logger.warning(f"D2 preview generation failed: {exc}")
        return _render_text(content)


def _render_mermaid_diagram(document: MermaidDiagram) -> PreviewArtifact:
    """Render Mermaid diagram preview as HTML for client-side rendering.

    Returns an HTML snippet with the Mermaid source wrapped in a pre element
    with class 'mermaid'. The frontend can use mermaid.js to render this
    into an SVG diagram.
    """
    content = document.content or ""
    if not content.strip():
        return _render_text("(empty diagram)")

    # Escape the content for safe HTML embedding
    escaped_content = html.escape(content)

    # Return HTML that can be rendered by mermaid.js on the client
    html_snippet = f'<pre class="mermaid">{escaped_content}</pre>'

    return PreviewArtifact(
        html=html_snippet,
        metadata={
            "format": "mermaid",
            "source_lines": len(content.splitlines()),
            "text_snippet": content[:SNIPPET_LENGTH],
        },
    )


def _render_excalidraw_diagram(document: ExcalidrawDiagram) -> PreviewArtifact:
    """Render Excalidraw diagram to SVG using Node.js export script.

    Uses the @excalidraw/utils library via a Node.js script to generate
    an SVG representation of the diagram.
    """
    import json

    content = document.content or ""
    if not content.strip():
        return _render_text("(empty diagram)")

    # Validate JSON
    try:
        data = json.loads(content)
        elements = data.get("elements", [])
        if not elements:
            return _render_text("(empty diagram)")
    except json.JSONDecodeError:
        return _render_text(content[:SNIPPET_LENGTH])

    # Find the export script - it's in packages/zoea-studio/scripts directory
    # Path from zoea-core: parent.parent = packages/, then zoea-studio/scripts
    packages_dir = Path(__file__).resolve().parent.parent.parent
    script_path = packages_dir / "zoea-studio" / "scripts" / "export-excalidraw.mjs"

    if not script_path.exists():
        logger.warning(f"Excalidraw export script not found at {script_path}")
        return _render_excalidraw_text_preview(data)

    # Check if node is available
    node_path = shutil.which("node")
    if not node_path:
        logger.warning("Node.js not found, falling back to text preview")
        return _render_excalidraw_text_preview(data)

    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            input_path = Path(tmpdir) / "diagram.json"
            output_path = Path(tmpdir) / "diagram.svg"

            # Write Excalidraw JSON to temp file
            input_path.write_text(content, encoding="utf-8")

            # Run Node.js export script
            # Need to run from zoea-studio directory so node_modules is accessible
            studio_dir = packages_dir / "zoea-studio"
            result = subprocess.run(
                [
                    node_path,
                    str(script_path),
                    str(input_path),
                    str(output_path),
                ],
                capture_output=True,
                text=True,
                timeout=30,
                cwd=str(studio_dir),
            )

            if result.returncode != 0:
                logger.warning(f"Excalidraw export failed: {result.stderr}")
                return _render_excalidraw_text_preview(data)

            if not output_path.exists():
                logger.warning("Excalidraw export did not produce output file")
                return _render_excalidraw_text_preview(data)

            svg_bytes = output_path.read_bytes()

            return PreviewArtifact(
                file_bytes=svg_bytes,
                file_ext="svg",
                metadata={
                    "format": "excalidraw",
                    "element_count": len(elements),
                },
            )

    except subprocess.TimeoutExpired:
        logger.warning("Excalidraw export timed out")
        return _render_excalidraw_text_preview(data)
    except Exception as exc:
        logger.warning(f"Excalidraw preview generation failed: {exc}")
        return _render_excalidraw_text_preview(data)


def _render_excalidraw_text_preview(data: dict) -> PreviewArtifact:
    """Generate a text-based preview for Excalidraw when SVG export fails."""
    elements = data.get("elements", [])
    element_count = len(elements)

    # Count element types
    type_counts = {}
    for el in elements:
        el_type = el.get("type", "unknown")
        type_counts[el_type] = type_counts.get(el_type, 0) + 1

    # Build summary text
    lines = [f"Excalidraw diagram ({element_count} elements)"]
    for el_type, count in sorted(type_counts.items()):
        lines.append(f"  {el_type}: {count}")

    summary = "\n".join(lines)
    html_snippet = f"<pre class='doc-preview-snippet'>{html.escape(summary)}</pre>"

    return PreviewArtifact(
        html=html_snippet,
        metadata={
            "format": "excalidraw",
            "element_count": element_count,
            "element_types": type_counts,
            "text_snippet": summary,
        },
    )


def _persist_artifact(preview: DocumentPreview, artifact: PreviewArtifact, content_hash: str) -> None:
    """Persist rendered artifact onto the preview row."""
    if artifact.file_bytes:
        filename = f"{preview.document_id}_{preview.preview_kind}.{artifact.file_ext or 'webp'}"
        preview.preview_file.save(filename, ContentFile(artifact.file_bytes), save=False)
        preview.file_size = len(artifact.file_bytes)

    preview.preview_html = artifact.html or ""
    preview.metadata = artifact.metadata or {}
    preview.width = artifact.width
    preview.height = artifact.height
    preview.content_hash = content_hash
    preview.status = DocumentPreview.Status.READY
    preview.generated_at = timezone.now()
    preview.error_message = ""
    preview.save()


def serialize_preview(preview: Optional[DocumentPreview], request=None) -> dict[str, Any] | None:
    """Return a JSON-safe representation of a preview row."""
    if not preview:
        return None

    url = None
    if preview.preview_file:
        url = preview.preview_file.url
        if request:
            url = request.build_absolute_uri(url)

    return {
        "kind": preview.preview_kind,
        "status": preview.status,
        "url": url,
        "html": preview.preview_html or None,
        "width": preview.width,
        "height": preview.height,
        "metadata": preview.metadata or {},
        "generated_at": preview.generated_at,
        "error": preview.error_message or None,
    }


def get_preview_data(document: Document, *, request=None, force: bool = False) -> dict[str, Any] | None:
    """Ensure a preview exists for the document and return serialized data."""
    preview = ensure_preview(document, preview_kind="thumbnail", force=force)
    return serialize_preview(preview, request=request)
