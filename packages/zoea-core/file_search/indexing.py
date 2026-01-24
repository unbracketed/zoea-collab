"""
Helpers for indexing Zoea content into the configured file search backend.
"""

from __future__ import annotations

import logging
from pathlib import Path

from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone

from . import FileSearchRegistry

logger = logging.getLogger(__name__)


TEXT_FILE_EXTENSIONS = {
    ".txt",
    ".md",
    ".markdown",
    ".json",
    ".yaml",
    ".yml",
    ".csv",
    ".tsv",
    ".log",
    ".py",
    ".js",
    ".ts",
    ".jsx",
    ".tsx",
    ".html",
    ".css",
    ".scss",
    ".rst",
    ".toml",
    ".ini",
}


def ensure_project_store(project, *, backend: str | None = None):
    """Ensure a project-scoped file search store exists."""
    store = FileSearchRegistry.get(backend)

    store_id = project.gemini_store_id
    if store_id:
        try:
            store_info = store.get_store(store_id)
        except Exception:
            store_info = None

        if store_info:
            return store_info

        project.gemini_store_id = None
        project.gemini_store_name = None
        project.save(update_fields=["gemini_store_id", "gemini_store_name"])

    store_name = f"{project.name} ({project.id})"
    store_info = store.create_store(store_name, ephemeral=False)
    project.gemini_store_id = store_info.store_id
    project.gemini_store_name = store_info.display_name
    project.gemini_synced_at = timezone.now()
    project.save(update_fields=["gemini_store_id", "gemini_store_name", "gemini_synced_at"])
    return store_info


def index_document(document, *, backend: str | None = None, force: bool = False) -> None:
    """Index a single Document into the project store."""
    from documents.models import Document

    if not document.project_id:
        logger.debug("Skipping document %s without project", document.id)
        return

    try:
        store = FileSearchRegistry.get(backend)
        store_info = ensure_project_store(document.project, backend=backend)

        record_id = f"doc-{document.id}"
        content = _extract_document_text(document, force_caption=force)
        if not content:
            logger.info("Document %s has no indexable text", document.id)
            return

        metadata = _build_document_metadata(document)

        _upsert_text_record(
            store,
            store_id=store_info.store_id,
            record_id=record_id,
            content=content,
            metadata=metadata,
            display_name=document.name,
        )

        Document.objects.filter(id=document.id).update(
            gemini_file_id=record_id,
            gemini_synced_at=timezone.now(),
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to index document %s: %s", document.id, exc)


def index_documents(documents, *, backend: str | None = None, force: bool = False) -> None:
    """Index a batch of Documents into the same project store."""
    documents = [doc for doc in documents if doc is not None]
    if not documents:
        return

    project = documents[0].project
    if not project:
        logger.debug("Skipping batch index; documents missing project")
        return

    try:
        store = FileSearchRegistry.get(backend)
        store_info = ensure_project_store(project, backend=backend)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to initialize file search backend: %s", exc)
        return

    for document in documents:
        if document.project_id != project.id:
            logger.warning("Skipping document %s from different project", document.id)
            continue

        try:
            record_id = f"doc-{document.id}"
            content = _extract_document_text(document, force_caption=force)
            if not content:
                continue

            metadata = _build_document_metadata(document)
            _upsert_text_record(
                store,
                store_id=store_info.store_id,
                record_id=record_id,
                content=content,
                metadata=metadata,
                display_name=document.name,
            )

            from documents.models import Document

            Document.objects.filter(id=document.id).update(
                gemini_file_id=record_id,
                gemini_synced_at=timezone.now(),
            )
        except Exception as exc:  # noqa: BLE001 - best effort batch indexing
            logger.warning("Failed to index document %s: %s", document.id, exc)


def remove_document(document, *, backend: str | None = None) -> None:
    """Remove a document record from the project store."""
    if not document.project_id:
        return

    try:
        store = FileSearchRegistry.get(backend)
        store_id = document.project.gemini_store_id
        if not store_id:
            return

        record_id = f"doc-{document.id}"
        store.remove_text_record(store_id, record_id)
    except Exception as exc:  # noqa: BLE001 - best effort cleanup
        logger.warning("Failed to remove document %s from store: %s", document.id, exc)


def index_chat_message(message, *, backend: str | None = None) -> None:
    """Index a chat message into the project store."""
    conversation = message.conversation
    if not conversation.project_id:
        return

    try:
        store = FileSearchRegistry.get(backend)
        store_info = ensure_project_store(conversation.project, backend=backend)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to initialize file search backend: %s", exc)
        return

    record_id = f"chat-{message.id}"
    content = (message.content or "").strip()
    if not content:
        return

    metadata = {
        "source_type": "chat_message",
        "message_id": str(message.id),
        "conversation_id": str(conversation.id),
        "role": message.role,
        "organization_id": str(conversation.organization_id),
        "project_id": str(conversation.project_id),
    }

    if conversation.created_by_id:
        metadata["author_id"] = str(conversation.created_by_id)

    _upsert_text_record(
        store,
        store_id=store_info.store_id,
        record_id=record_id,
        content=content,
        metadata=metadata,
        display_name=f"Conversation {conversation.id} ({message.role})",
    )


def index_email_message(email_message, *, backend: str | None = None) -> None:
    """Index an email message into the project store."""
    thread = email_message.email_thread
    if not thread or not thread.project_id:
        return

    try:
        store = FileSearchRegistry.get(backend)
        store_info = ensure_project_store(thread.project, backend=backend)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to initialize file search backend: %s", exc)
        return

    record_id = f"email-{email_message.id}"
    content = (email_message.stripped_text or email_message.body_plain or "").strip()
    if not content:
        return

    metadata = {
        "source_type": "email_message",
        "email_message_id": str(email_message.id),
        "email_thread_id": str(thread.id),
        "conversation_id": str(thread.conversation_id),
        "organization_id": str(thread.organization_id),
        "project_id": str(thread.project_id),
        "sender": email_message.sender,
        "recipient": email_message.recipient,
        "subject": email_message.subject,
    }

    _upsert_text_record(
        store,
        store_id=store_info.store_id,
        record_id=record_id,
        content=content,
        metadata=metadata,
        display_name=f"Email: {email_message.subject}",
    )


def _upsert_text_record(store, *, store_id: str, record_id: str, content: str, metadata: dict,
                        display_name: str | None = None) -> None:
    """Remove a record by ID (if supported) and re-add with updated content."""
    try:
        store.remove_text_record(store_id, record_id)
    except Exception:
        pass

    store.add_text_record(
        store_id,
        record_id=record_id,
        content=content,
        metadata=metadata,
        display_name=display_name,
    )


def _extract_document_text(document, *, force_caption: bool = False) -> str | None:
    from documents.image_caption_service import get_or_create_image_caption
    from documents.models import (
        PDF,
        FileDocument,
        Image,
        SpreadsheetDocument,
        TextDocument,
        WordDocument,
        YooptaDocument,
    )

    if isinstance(document, Image):
        return get_or_create_image_caption(document, force=force_caption)

    if isinstance(document, PDF):
        return document.get_text_content()

    if isinstance(document, YooptaDocument):
        return document.get_text_content()

    if isinstance(document, WordDocument):
        return document.get_text_content()

    if isinstance(document, SpreadsheetDocument):
        return document.get_text_content()

    if isinstance(document, TextDocument):
        return document.content or ""

    if isinstance(document, FileDocument):
        return _extract_file_document_text(document)

    if hasattr(document, "content"):
        return getattr(document, "content") or ""

    return None


def _extract_file_document_text(document) -> str | None:
    # Conversion path: text files -> decoded text, PDFs -> extracted text, others skipped.
    if not document.file:
        return None

    path = Path(document.file.path)
    suffix = path.suffix.lower()
    content_type = (document.content_type or "").lower()

    if content_type.startswith("text/") or suffix in TEXT_FILE_EXTENSIONS:
        return _read_text_file(path)

    if content_type == "application/pdf" or suffix == ".pdf":
        return _extract_pdf_text(path)

    return None


def _read_text_file(path: Path) -> str | None:
    max_bytes = int(getattr(settings, "FILE_SEARCH_MAX_TEXT_BYTES", 2 * 1024 * 1024))
    try:
        with path.open("rb") as handle:
            data = handle.read(max_bytes)
        return data.decode("utf-8", errors="ignore")
    except Exception as exc:  # noqa: BLE001
        logger.debug("Failed to read text file %s: %s", path, exc)
        return None


def _extract_pdf_text(path: Path) -> str | None:
    try:
        import fitz  # PyMuPDF
    except Exception as exc:  # noqa: BLE001
        logger.debug("PDF extraction unavailable: %s", exc)
        return None

    try:
        with fitz.open(path) as doc:
            parts = []
            for page in doc:
                parts.append(page.get_text())
            return "\n\n".join(parts)
    except Exception as exc:  # noqa: BLE001
        logger.debug("Failed to extract PDF text %s: %s", path, exc)
        return None


def _build_document_metadata(document) -> dict:
    metadata = {
        "source_type": "document",
        "document_id": str(document.id),
        "document_name": document.name,
        "document_type": document.get_type_name(),
        "organization_id": str(document.organization_id),
    }

    if document.project_id:
        metadata["project_id"] = str(document.project_id)
    if document.folder_id:
        metadata["folder_id"] = str(document.folder_id)
    if document.created_by_id:
        metadata["author_id"] = str(document.created_by_id)

    collection_metadata = _get_collection_metadata(document)
    metadata.update(collection_metadata)

    if hasattr(document, "content_type") and getattr(document, "content_type", None):
        metadata["file_content_type"] = document.content_type
    if hasattr(document, "original_filename") and getattr(document, "original_filename", None):
        metadata["original_filename"] = document.original_filename

    return metadata


def _get_collection_metadata(document) -> dict:
    from documents.models import CollectionType, DocumentCollectionItem

    doc_ct = ContentType.objects.get_for_model(document, for_concrete_model=False)
    items = (
        DocumentCollectionItem.objects.select_related("collection")
        .filter(content_type=doc_ct, object_id=str(document.id))
    )

    if not items.exists():
        return {}

    # Prefer attachments, then artifacts, then notebooks.
    priority = {
        CollectionType.ATTACHMENT: 0,
        CollectionType.ARTIFACT: 1,
        CollectionType.NOTEBOOK: 2,
    }

    item = min(
        items,
        key=lambda candidate: priority.get(candidate.collection.collection_type, 3),
    )
    collection = item.collection

    metadata = {
        "collection_id": str(collection.id),
        "collection_type": collection.collection_type,
        "collection_item_id": str(item.id),
        "source_channel": item.source_channel,
    }

    conversation_id = collection.conversations.values_list("id", flat=True).first()
    if conversation_id:
        metadata["conversation_id"] = str(conversation_id)

    email_thread_id = collection.email_threads.values_list("id", flat=True).first()
    if email_thread_id:
        metadata["email_thread_id"] = str(email_thread_id)

    execution_run_id = collection.execution_runs.values_list("id", flat=True).first()
    if execution_run_id:
        metadata["execution_run_id"] = str(execution_run_id)

    return metadata
