"""
Signal definitions for clipboard events.

This module handles:
1. Custom clipboard signals (activated, item added/removed)
2. Auto-creation of default Clipboard when a Workspace is created
"""

from django.db.models.signals import post_save
from django.dispatch import Signal, receiver
from django.utils import timezone

from workspaces.models import Workspace

clipboard_activated = Signal()
clipboard_item_added = Signal()
clipboard_item_removed = Signal()


@receiver(post_save, sender=Workspace)
def create_default_clipboard(sender, instance, created, **kwargs):
    """
    Create a default active Clipboard when a Workspace is created.

    This ensures every workspace has at least one clipboard ready to use,
    providing a smooth onboarding experience without requiring users to
    manually create their first clipboard.

    The clipboard is created with:
    - owner: the user who created the workspace
    - is_active: True (ready to use immediately)
    - name: based on the workspace name
    """
    if not created:
        return

    workspace = instance
    user = workspace.created_by

    # Only create if there's a user (created_by can be null)
    if not user:
        return

    # Import here to avoid circular imports
    from .models import Clipboard

    # Create the default active clipboard
    Clipboard.objects.create(
        workspace=workspace,
        owner=user,
        name=f"{workspace.name} Clipboard",
        is_active=True,
        activated_at=timezone.now(),
    )
