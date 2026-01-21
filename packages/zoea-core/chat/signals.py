"""
Signals for indexing chat messages into the file search store.
"""

from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Message


@receiver(post_save, sender=Message)
def index_chat_message_on_save(sender, instance: Message, created: bool, **kwargs) -> None:
    if getattr(instance, "_skip_file_search", False):
        return
    if not created:
        return
    if getattr(instance, "email_message_id", None):
        return

    def _index():
        from file_search.indexing import index_chat_message

        index_chat_message(instance)

    transaction.on_commit(_index)
