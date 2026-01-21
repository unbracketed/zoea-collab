"""
Custom django-allauth adapters for Zoea Studio.

This module provides custom adapters that integrate django-allauth with our
multi-tenant organization structure. When a new user signs up, we automatically
create an organization for them using our initialize_user_organization() utility.
"""

import logging
from allauth.account.adapter import DefaultAccountAdapter

from .utils import initialize_user_organization

logger = logging.getLogger(__name__)


class AccountAdapter(DefaultAccountAdapter):
    """
    Custom account adapter that creates an organization for new users.

    This adapter hooks into the django-allauth signup flow and automatically
    creates an organization (with default project and workspace) for each new user.
    """

    def save_user(self, request, user, form, commit=True):
        """
        Save a new user and create their organization.

        This method is called during the signup process, after the user has been
        created but before they're saved to the database. We use this hook to:
        1. Save the user to the database
        2. Create an organization for them
        3. Set up their default project and workspace

        Args:
            request: The HTTP request object
            user: The user instance being created
            form: The signup form
            commit: Whether to save the user to the database

        Returns:
            The saved user instance
        """
        # First, let the default adapter save the user
        user = super().save_user(request, user, form, commit=commit)

        if commit:
            try:
                # Initialize organization for the new user
                # This creates:
                # - Organization (Account) with user as owner
                # - Default project (via signals)
                # - Default workspace (via signals)
                result = initialize_user_organization(user)

                logger.info(
                    f"Successfully created organization '{result['organization'].name}' "
                    f"for new user '{user.username}'"
                )

            except Exception as e:
                logger.error(
                    f"Failed to create organization for user '{user.username}': {str(e)}",
                    exc_info=True
                )
                # Don't prevent signup if organization creation fails
                # The user can still be created, and admin can fix organization later
                # Alternatively, you could raise the exception to prevent signup:
                # raise

        return user
