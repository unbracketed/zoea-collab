"""
Signals for automatic Workspace creation.

This module handles creating a default Workspace when a Project is created.
"""

from django.db.models.signals import post_save
from django.dispatch import receiver

from projects.models import Project
from .models import Workspace


@receiver(post_save, sender=Project)
def create_default_workspace(sender, instance, created, **kwargs):
    """
    Create a default Workspace when a Project is created.

    This ensures every project has at least one workspace to organize content.
    The workspace is named after the project or organization.
    """
    if not created:
        return

    project = instance
    organization = project.organization
    user = project.created_by

    # Create a default workspace name
    workspace_name = f"{organization.name} Workspace"

    # Create the default workspace (root workspace with no parent)
    Workspace.objects.create(
        project=project,
        name=workspace_name,
        description=f"Default workspace for {project.name}",
        parent=None,  # Root workspace
        created_by=user
    )
