"""
Signals for indexing chat messages into the file search store.

Chat message indexing is performed as background tasks via Django-Q2 to avoid
blocking the response cycle. Tasks are queued on transaction commit to ensure
the message is fully persisted before indexing.
"""

from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Message


@receiver(post_save, sender=Message)
def index_chat_message_on_save(sender, instance: Message, created: bool, **kwargs) -> None:
    """Queue chat message for background indexing after creation."""
    if getattr(instance, "_skip_file_search", False):
        return
    if not created:
        return
    if getattr(instance, "email_message_id", None):
        return

    def _queue():
        from file_search.tasks import queue_chat_message_indexing

        queue_chat_message_indexing(instance.id)

    transaction.on_commit(_queue)
