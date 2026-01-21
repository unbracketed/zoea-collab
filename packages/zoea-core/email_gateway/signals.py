"""
Signals for indexing email messages into the file search store.
"""

from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import EmailMessage


@receiver(post_save, sender=EmailMessage)
def index_email_message_on_save(sender, instance: EmailMessage, **kwargs) -> None:
    if getattr(instance, "_skip_file_search", False):
        return
    if instance.status != "processed":
        return

    def _index():
        from file_search.indexing import index_email_message

        index_email_message(instance)

    transaction.on_commit(_index)
