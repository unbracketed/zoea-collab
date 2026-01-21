from django.db import models


class OrganizationScopedQuerySet(models.QuerySet):
    """
    Base queryset for organization-scoped resources.

    This queryset provides standard filtering methods for any model that
    has an 'organization' ForeignKey field. Use this as the basis for
    custom managers on multi-tenant models.

    Example usage:
        class ChatMessage(models.Model):
            organization = models.ForeignKey('organizations.Organization', on_delete=models.CASCADE)
            content = models.TextField()

            objects = OrganizationScopedQuerySet.as_manager()

        # In views/APIs
        messages = ChatMessage.objects.for_user(request.user)
    """

    def for_user(self, user):
        """
        Filter resources to those accessible by the given user.

        Returns only resources that belong to organizations where the user
        is a member (via OrganizationUser relationship).

        Args:
            user: Django User instance

        Returns:
            Filtered queryset containing only accessible resources
        """
        return self.filter(
            organization__organization_users__user=user
        ).distinct()

    def for_organization(self, organization):
        """
        Filter resources to a specific organization.

        Args:
            organization: Organization instance or Account instance

        Returns:
            Filtered queryset for the specified organization
        """
        return self.filter(organization=organization)

    def for_organization_id(self, organization_id):
        """
        Filter resources to a specific organization by ID.

        Args:
            organization_id: Primary key of the organization

        Returns:
            Filtered queryset for the specified organization
        """
        return self.filter(organization_id=organization_id)
