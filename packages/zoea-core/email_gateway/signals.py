"""
Signals for indexing email messages into the file search store.

Email message indexing is performed as background tasks via Django-Q2 to avoid
blocking the response cycle. Tasks are queued on transaction commit to ensure
the message is fully persisted before indexing.
"""

from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import EmailMessage


@receiver(post_save, sender=EmailMessage)
def index_email_message_on_save(sender, instance: EmailMessage, **kwargs) -> None:
    """Queue email message for background indexing after processing."""
    if getattr(instance, "_skip_file_search", False):
        return
    if instance.status != "processed":
        return

    def _queue():
        from file_search.tasks import queue_email_message_indexing

        queue_email_message_indexing(instance.id)

    transaction.on_commit(_queue)
