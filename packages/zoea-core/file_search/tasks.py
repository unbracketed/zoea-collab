"""
Background tasks for file search indexing.

Uses Django-Q2 for async task execution. These tasks are triggered by
Django signals (post_save/post_delete) to index content into the project's
file search store without blocking the response cycle.

Design principle: Indexing is infrastructure, not a workflow. It's deterministic
text extraction + vector storage with no LLM reasoning required.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from django.utils import timezone

if TYPE_CHECKING:
    from documents.models import Document

logger = logging.getLogger(__name__)


# =============================================================================
# Task Functions
# =============================================================================


def index_document_task(document_id: int, force: bool = False) -> dict:
    """
    Background task to index a single document into the file search store.

    Args:
        document_id: ID of the Document to index
        force: Force re-extraction of content (e.g., regenerate image captions)

    Returns:
        Dict with indexing status and details
    """
    from documents.models import Document

    try:
        document = Document.objects.select_subclasses().get(id=document_id)
    except Document.DoesNotExist:
        logger.warning(f"Document {document_id} not found for indexing")
        return {"document_id": document_id, "status": "not_found"}

    try:
        from file_search.indexing import index_document

        index_document(document, force=force)

        # Clear any previous error state
        Document.objects.filter(id=document_id).update(
            gemini_sync_error=None,
        )

        logger.info(f"Successfully indexed document {document_id}")
        return {
            "document_id": document_id,
            "status": "indexed",
            "document_type": document.get_type_name(),
        }

    except Exception as e:
        error_msg = str(e)
        logger.warning(f"Failed to index document {document_id}: {error_msg}")

        # Record the error for monitoring
        from django.db.models import F

        Document.objects.filter(id=document_id).update(
            gemini_sync_error=error_msg,
            gemini_sync_attempts=F("gemini_sync_attempts") + 1,
        )

        return {
            "document_id": document_id,
            "status": "failed",
            "error": error_msg,
        }


def index_documents_batch_task(document_ids: list[int], project_id: int) -> dict:
    """
    Background task to index a batch of documents from the same project.

    Args:
        document_ids: List of Document IDs to index
        project_id: Project ID (for validation and store initialization)

    Returns:
        Dict with batch indexing results
    """
    from documents.models import Document
    from projects.models import Project

    try:
        project = Project.objects.get(id=project_id)
    except Project.DoesNotExist:
        logger.warning(f"Project {project_id} not found for batch indexing")
        return {"project_id": project_id, "status": "project_not_found"}

    from file_search.indexing import ensure_project_store, index_documents

    try:
        ensure_project_store(project)
    except Exception as e:
        logger.warning(f"Failed to ensure store for project {project_id}: {e}")
        return {
            "project_id": project_id,
            "status": "store_initialization_failed",
            "error": str(e),
        }

    documents = list(
        Document.objects.select_subclasses().filter(
            id__in=document_ids,
            project_id=project_id,
        )
    )

    if not documents:
        return {
            "project_id": project_id,
            "document_ids": document_ids,
            "status": "no_documents_found",
        }

    try:
        index_documents(documents)

        # Clear error states for successfully indexed documents
        Document.objects.filter(id__in=document_ids).update(
            gemini_sync_error=None,
        )

        logger.info(
            f"Successfully batch-indexed {len(documents)} documents "
            f"for project {project_id}"
        )
        return {
            "project_id": project_id,
            "status": "indexed",
            "count": len(documents),
            "document_ids": [d.id for d in documents],
        }

    except Exception as e:
        error_msg = str(e)
        logger.warning(
            f"Batch indexing failed for project {project_id}: {error_msg}"
        )
        return {
            "project_id": project_id,
            "status": "failed",
            "error": error_msg,
        }


def index_chat_message_task(message_id: int) -> dict:
    """
    Background task to index a chat message into the file search store.

    Args:
        message_id: ID of the Message to index

    Returns:
        Dict with indexing status
    """
    from chat.models import Message

    try:
        message = Message.objects.select_related(
            "conversation", "conversation__project"
        ).get(id=message_id)
    except Message.DoesNotExist:
        logger.warning(f"Message {message_id} not found for indexing")
        return {"message_id": message_id, "status": "not_found"}

    if not message.conversation.project_id:
        return {"message_id": message_id, "status": "no_project"}

    try:
        from file_search.indexing import index_chat_message

        index_chat_message(message)

        logger.debug(f"Successfully indexed chat message {message_id}")
        return {"message_id": message_id, "status": "indexed"}

    except Exception as e:
        error_msg = str(e)
        logger.warning(f"Failed to index chat message {message_id}: {error_msg}")
        return {
            "message_id": message_id,
            "status": "failed",
            "error": error_msg,
        }


def index_email_message_task(email_message_id: int) -> dict:
    """
    Background task to index an email message into the file search store.

    Args:
        email_message_id: ID of the EmailMessage to index

    Returns:
        Dict with indexing status
    """
    from email_gateway.models import EmailMessage

    try:
        email_message = EmailMessage.objects.select_related(
            "email_thread", "email_thread__project"
        ).get(id=email_message_id)
    except EmailMessage.DoesNotExist:
        logger.warning(f"EmailMessage {email_message_id} not found for indexing")
        return {"email_message_id": email_message_id, "status": "not_found"}

    thread = email_message.email_thread
    if not thread or not thread.project_id:
        return {"email_message_id": email_message_id, "status": "no_project"}

    try:
        from file_search.indexing import index_email_message

        index_email_message(email_message)

        logger.debug(f"Successfully indexed email message {email_message_id}")
        return {"email_message_id": email_message_id, "status": "indexed"}

    except Exception as e:
        error_msg = str(e)
        logger.warning(
            f"Failed to index email message {email_message_id}: {error_msg}"
        )
        return {
            "email_message_id": email_message_id,
            "status": "failed",
            "error": error_msg,
        }


def index_platform_message_task(platform_message_id: int) -> dict:
    """
    Background task to index a platform message into the file search store.

    Args:
        platform_message_id: ID of the PlatformMessage to index

    Returns:
        Dict with indexing status
    """
    from platform_adapters.models import PlatformMessage

    try:
        platform_message = PlatformMessage.objects.select_related(
            "connection", "project"
        ).get(id=platform_message_id)
    except PlatformMessage.DoesNotExist:
        logger.warning(f"PlatformMessage {platform_message_id} not found for indexing")
        return {"platform_message_id": platform_message_id, "status": "not_found"}

    if not platform_message.project_id:
        return {"platform_message_id": platform_message_id, "status": "no_project"}

    try:
        from file_search.indexing import index_platform_message

        index_platform_message(platform_message)

        logger.debug(f"Successfully indexed platform message {platform_message_id}")
        return {
            "platform_message_id": platform_message_id,
            "message_id": str(platform_message.message_id),
            "status": "indexed",
        }

    except Exception as e:
        error_msg = str(e)
        logger.warning(
            f"Failed to index platform message {platform_message_id}: {error_msg}"
        )
        return {
            "platform_message_id": platform_message_id,
            "status": "failed",
            "error": error_msg,
        }


def index_project_working_directory_task(
    project_id: int,
    *,
    on_conflict: str = "skip",
    follow_symlinks: bool = False,
) -> dict:
    """
    Background task to index a project's working directory.

    Scans the project's working_directory for supported document types
    and imports them into the project's document store.

    Args:
        project_id: ID of the Project to index
        on_conflict: How to handle existing documents ("skip", "rename", "overwrite")
        follow_symlinks: Whether to follow symbolic links

    Returns:
        Dict with import summary
    """
    from pathlib import Path

    from projects.models import Project

    try:
        project = Project.objects.select_related("organization", "created_by").get(
            id=project_id
        )
    except Project.DoesNotExist:
        logger.warning(f"Project {project_id} not found for directory indexing")
        return {"project_id": project_id, "status": "not_found"}

    working_dir = project.working_directory
    if not working_dir:
        return {"project_id": project_id, "status": "no_working_directory"}

    working_path = Path(working_dir).expanduser()
    if not working_path.exists():
        logger.info(
            f"Working directory does not exist for project {project_id}: {working_dir}"
        )
        return {
            "project_id": project_id,
            "status": "directory_not_found",
            "working_directory": str(working_dir),
        }

    if not working_path.is_dir():
        return {
            "project_id": project_id,
            "status": "not_a_directory",
            "working_directory": str(working_dir),
        }

    try:
        from documents.import_service import DocumentImportService

        service = DocumentImportService(
            organization=project.organization,
            project=project,
            created_by=project.created_by,
            create_root_folder=False,  # Import directly into project root
            on_conflict=on_conflict,
        )

        summary = service.import_directory(
            str(working_path),
            follow_symlinks=follow_symlinks,
        )

        logger.info(
            f"Indexed working directory for project {project_id}: "
            f"{summary.created} created, {summary.skipped} skipped, {summary.failed} failed"
        )

        return {
            "project_id": project_id,
            "status": "indexed",
            "working_directory": str(working_dir),
            "created": summary.created,
            "updated": summary.updated,
            "skipped": summary.skipped,
            "failed": summary.failed,
            "total_files": summary.total_files,
            "total_size": summary.total_size,
            "issues": [
                {"path": i.path, "reason": i.reason, "status": i.status}
                for i in summary.issues[:10]  # Limit issues in response
            ],
        }

    except Exception as e:
        error_msg = str(e)
        logger.warning(
            f"Failed to index working directory for project {project_id}: {error_msg}"
        )
        return {
            "project_id": project_id,
            "status": "failed",
            "error": error_msg,
        }


def reindex_project_task(project_id: int, force: bool = False) -> dict:
    """
    Background task to reindex all documents in a project.

    Args:
        project_id: ID of the Project to reindex
        force: Force re-extraction of content

    Returns:
        Dict with reindex results
    """
    from documents.models import Document
    from projects.models import Project

    try:
        project = Project.objects.get(id=project_id)
    except Project.DoesNotExist:
        logger.warning(f"Project {project_id} not found for reindexing")
        return {"project_id": project_id, "status": "not_found"}

    from file_search.indexing import ensure_project_store, index_document

    try:
        ensure_project_store(project)
    except Exception as e:
        logger.warning(f"Failed to ensure store for project {project_id}: {e}")
        return {
            "project_id": project_id,
            "status": "store_initialization_failed",
            "error": str(e),
        }

    documents = Document.objects.select_subclasses().filter(project_id=project_id)

    indexed = 0
    failed = 0
    errors = []

    for document in documents:
        try:
            index_document(document, force=force)
            indexed += 1
        except Exception as e:
            failed += 1
            errors.append({"document_id": document.id, "error": str(e)})

    logger.info(
        f"Reindexed project {project_id}: {indexed} indexed, {failed} failed"
    )

    return {
        "project_id": project_id,
        "status": "completed",
        "indexed": indexed,
        "failed": failed,
        "errors": errors[:10],  # Limit error details
    }


# =============================================================================
# Task Queueing Functions
# =============================================================================


def queue_document_indexing(document_id: int, project_id: int | None = None) -> str | None:
    """
    Queue a document for background indexing.

    Args:
        document_id: ID of the Document to index
        project_id: Optional project ID (unused, for future batching)

    Returns:
        Task ID if queued, None if indexing is disabled
    """
    from django.conf import settings

    # Allow disabling background indexing via settings
    if getattr(settings, "FILE_SEARCH_DISABLE_BACKGROUND_INDEXING", False):
        # Fall back to synchronous indexing
        index_document_task(document_id)
        return None

    from django_q.tasks import async_task

    task_id = async_task(
        "file_search.tasks.index_document_task",
        document_id,
        task_name=f"index_document_{document_id}",
        timeout=300,  # 5 minute timeout for document indexing
    )

    logger.debug(f"Queued document {document_id} for indexing: task {task_id}")
    return task_id


def queue_chat_message_indexing(message_id: int) -> str | None:
    """
    Queue a chat message for background indexing.

    Args:
        message_id: ID of the Message to index

    Returns:
        Task ID if queued, None if indexing is disabled
    """
    from django.conf import settings

    if getattr(settings, "FILE_SEARCH_DISABLE_BACKGROUND_INDEXING", False):
        index_chat_message_task(message_id)
        return None

    from django_q.tasks import async_task

    task_id = async_task(
        "file_search.tasks.index_chat_message_task",
        message_id,
        task_name=f"index_chat_message_{message_id}",
        timeout=60,  # 1 minute timeout for message indexing
    )

    logger.debug(f"Queued chat message {message_id} for indexing: task {task_id}")
    return task_id


def queue_email_message_indexing(email_message_id: int) -> str | None:
    """
    Queue an email message for background indexing.

    Args:
        email_message_id: ID of the EmailMessage to index

    Returns:
        Task ID if queued, None if indexing is disabled
    """
    from django.conf import settings

    if getattr(settings, "FILE_SEARCH_DISABLE_BACKGROUND_INDEXING", False):
        index_email_message_task(email_message_id)
        return None

    from django_q.tasks import async_task

    task_id = async_task(
        "file_search.tasks.index_email_message_task",
        email_message_id,
        task_name=f"index_email_message_{email_message_id}",
        timeout=60,  # 1 minute timeout for email indexing
    )

    logger.debug(
        f"Queued email message {email_message_id} for indexing: task {task_id}"
    )
    return task_id


def queue_platform_message_indexing(platform_message_id: int) -> str | None:
    """
    Queue a platform message for background indexing.

    Args:
        platform_message_id: ID of the PlatformMessage to index

    Returns:
        Task ID if queued, None if indexing is disabled
    """
    from django.conf import settings

    if getattr(settings, "FILE_SEARCH_DISABLE_BACKGROUND_INDEXING", False):
        index_platform_message_task(platform_message_id)
        return None

    from django_q.tasks import async_task

    task_id = async_task(
        "file_search.tasks.index_platform_message_task",
        platform_message_id,
        task_name=f"index_platform_message_{platform_message_id}",
        timeout=60,  # 1 minute timeout for platform message indexing
    )

    logger.debug(
        f"Queued platform message {platform_message_id} for indexing: task {task_id}"
    )
    return task_id


def queue_project_reindex(project_id: int, force: bool = False) -> str | None:
    """
    Queue a full project reindex as a background task.

    Args:
        project_id: ID of the Project to reindex
        force: Force re-extraction of content

    Returns:
        Task ID if queued
    """
    from django_q.tasks import async_task

    task_id = async_task(
        "file_search.tasks.reindex_project_task",
        project_id,
        force=force,
        task_name=f"reindex_project_{project_id}",
        timeout=1800,  # 30 minute timeout for full project reindex
    )

    logger.info(f"Queued project {project_id} for reindexing: task {task_id}")
    return task_id


def queue_project_working_directory_indexing(
    project_id: int,
    *,
    on_conflict: str = "skip",
    follow_symlinks: bool = False,
) -> str | None:
    """
    Queue a project's working directory for background indexing.

    Args:
        project_id: ID of the Project to index
        on_conflict: How to handle existing documents ("skip", "rename", "overwrite")
        follow_symlinks: Whether to follow symbolic links

    Returns:
        Task ID if queued, None if indexing is disabled
    """
    from django.conf import settings

    if getattr(settings, "FILE_SEARCH_DISABLE_BACKGROUND_INDEXING", False):
        index_project_working_directory_task(
            project_id, on_conflict=on_conflict, follow_symlinks=follow_symlinks
        )
        return None

    from django_q.tasks import async_task

    task_id = async_task(
        "file_search.tasks.index_project_working_directory_task",
        project_id,
        on_conflict=on_conflict,
        follow_symlinks=follow_symlinks,
        task_name=f"index_project_directory_{project_id}",
        timeout=600,  # 10 minute timeout for directory indexing
    )

    logger.info(
        f"Queued project {project_id} working directory for indexing: task {task_id}"
    )
    return task_id


def queue_batch_document_indexing(
    document_ids: list[int], project_id: int
) -> str | None:
    """
    Queue a batch of documents for indexing.

    Args:
        document_ids: List of Document IDs to index
        project_id: Project ID for the documents

    Returns:
        Task ID if queued
    """
    from django_q.tasks import async_task

    task_id = async_task(
        "file_search.tasks.index_documents_batch_task",
        document_ids,
        project_id,
        task_name=f"index_documents_batch_{project_id}_{len(document_ids)}",
        timeout=600,  # 10 minute timeout for batch indexing
    )

    logger.debug(
        f"Queued batch of {len(document_ids)} documents for project {project_id}: "
        f"task {task_id}"
    )
    return task_id
