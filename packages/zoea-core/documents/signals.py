"""
Signals for document indexing into the file search store.

Document indexing is performed as background tasks via Django-Q2 to avoid
blocking the response cycle. Tasks are queued on transaction commit to ensure
the document is fully persisted before indexing.
"""

from django.db import transaction
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from .models import Document, DocumentCollectionItem


@receiver(post_save, sender=Document)
def index_document_on_save(sender, instance: Document, **kwargs) -> None:
    """Queue document for background indexing after save."""
    if getattr(instance, "_skip_file_search", False):
        return

    def _queue():
        from file_search.tasks import queue_document_indexing

        queue_document_indexing(instance.id, instance.project_id)

    transaction.on_commit(_queue)


@receiver(post_save, sender=Document)
def dispatch_document_event(sender, instance: Document, created: bool, **kwargs) -> None:
    """Dispatch DOCUMENT_CREATED or DOCUMENT_UPDATED event for configured triggers."""
    if getattr(instance, "_skip_event_dispatch", False):
        return

    def _dispatch():
        try:
            from events.dispatcher import dispatch_event
            from events.models import EventType

            event_type = EventType.DOCUMENT_CREATED if created else EventType.DOCUMENT_UPDATED

            # Build event data from document
            event_data = {
                "document_id": instance.id,
                "document_type": instance.__class__.__name__,
                "name": instance.name,
                "description": getattr(instance, "description", ""),
                "created_at": instance.created_at.isoformat() if instance.created_at else None,
                "project_id": instance.project_id,
                "folder_id": getattr(instance, "folder_id", None),
            }

            # Add content preview for text documents
            if hasattr(instance, "content"):
                content = instance.content or ""
                event_data["content_preview"] = content[:1000] if len(content) > 1000 else content

            dispatch_event(
                event_type=event_type,
                source_type="document",
                source_id=instance.id,
                event_data=event_data,
                organization=instance.organization,
                project=instance.project,
            )

        except ImportError:
            # Events app may not be installed
            pass
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Failed to dispatch document event: {e}", exc_info=True)

    transaction.on_commit(_dispatch)


@receiver(post_delete, sender=Document)
def remove_document_on_delete(sender, instance: Document, **kwargs) -> None:
    def _remove():
        from file_search.indexing import remove_document

        remove_document(instance)

    transaction.on_commit(_remove)


@receiver(post_save, sender=DocumentCollectionItem)
def reindex_document_on_collection_save(sender, instance: DocumentCollectionItem, **kwargs) -> None:
    """Queue document for reindexing when added to a collection (metadata update)."""
    if not instance.content_type_id or not instance.object_id:
        return

    model_cls = instance.content_type.model_class()
    if not model_cls or not issubclass(model_cls, Document):
        return

    def _queue_reindex():
        from file_search.tasks import queue_document_indexing

        document = model_cls.objects.filter(id=instance.object_id).first()
        if document:
            queue_document_indexing(document.id, document.project_id)

    transaction.on_commit(_queue_reindex)


@receiver(post_delete, sender=DocumentCollectionItem)
def reindex_document_on_collection_delete(sender, instance: DocumentCollectionItem, **kwargs) -> None:
    """Queue document for reindexing when removed from a collection (metadata update)."""
    if not instance.content_type_id or not instance.object_id:
        return

    model_cls = instance.content_type.model_class()
    if not model_cls or not issubclass(model_cls, Document):
        return

    def _queue_reindex():
        from file_search.tasks import queue_document_indexing

        document = model_cls.objects.filter(id=instance.object_id).first()
        if document:
            queue_document_indexing(document.id, document.project_id)

    transaction.on_commit(_queue_reindex)
