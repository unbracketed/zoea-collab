"""
Signals for automatic Project creation.

This module handles creating a default Project when an OrganizationUser is created.
"""

import os
from pathlib import Path
from django.db.models.signals import post_save
from django.dispatch import receiver
from organizations.models import OrganizationUser

from .models import Project


@receiver(post_save, sender=OrganizationUser)
def create_default_project(sender, instance, created, **kwargs):
    """
    Create a default Project when a user joins an organization for the first time.

    This ensures every user has at least one project to work with.
    The project is created with a demo-docs directory.
    """
    if not created:
        return

    user = instance.user
    organization = instance.organization

    # Check if this organization already has any projects
    # We only create a default project if this is the first user or the org has no projects
    existing_projects = Project.objects.filter(organization=organization)

    if existing_projects.exists():
        # Organization already has projects, don't create a new one
        return

    # Create a default project name based on organization
    project_name = f"{organization.name} - Default Project"

    # Create a demo-docs directory path
    # Use a safe directory structure: ~/zoea-projects/{org-slug}/demo-docs
    home_dir = Path.home()
    org_slug = organization.slug if hasattr(organization, 'slug') else organization.name.lower().replace(' ', '-')
    working_dir = home_dir / "zoea-projects" / org_slug / "demo-docs"

    # Create the default project
    Project.objects.create(
        organization=organization,
        name=project_name,
        working_directory=str(working_dir),
        description=f"Default project for {organization.name}",
        created_by=user
    )
