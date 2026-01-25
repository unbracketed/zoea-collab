"""
Signals for indexing platform messages into the file search store.

Platform message indexing is performed as background tasks via Django-Q2 to avoid
blocking the webhook response cycle. Tasks are queued on transaction commit to ensure
the message is fully persisted before indexing.
"""

from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import MessageStatus, PlatformMessage


@receiver(post_save, sender=PlatformMessage)
def index_platform_message_on_save(sender, instance: PlatformMessage, **kwargs) -> None:
    """
    Queue platform message for background indexing after save.

    Only indexes messages that:
    - Have status="processing" (dispatched to event system)
    - Have a project assigned
    - Haven't been flagged to skip indexing
    """
    if getattr(instance, "_skip_file_search", False):
        return

    # Only index messages that are being processed (not ignored/failed)
    if instance.status != MessageStatus.PROCESSING:
        return

    # Require a project for indexing (needed for project-scoped store)
    if not instance.project_id:
        return

    def _queue():
        from file_search.tasks import queue_platform_message_indexing

        queue_platform_message_indexing(instance.id)

    transaction.on_commit(_queue)
