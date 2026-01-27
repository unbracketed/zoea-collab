from django.db import models
from organizations.models import Organization


class Account(Organization):
    """
    Multi-table inheritance approach to add custom fields to Organization.
    Each Account represents a company/team that can have multiple users.

    This extends the base Organization model from django-organizations with
    Zoea Collab-specific fields for subscription management and settings.
    """

    SUBSCRIPTION_CHOICES = [
        ('free', 'Free'),
        ('pro', 'Pro'),
        ('enterprise', 'Enterprise'),
    ]

    subscription_plan = models.CharField(
        max_length=50,
        default='free',
        choices=SUBSCRIPTION_CHOICES,
        help_text="The subscription tier for this account"
    )
    billing_email = models.EmailField(
        blank=True,
        null=True,
        help_text="Email address for billing and invoicing"
    )
    max_users = models.IntegerField(
        default=5,
        help_text="Maximum number of users allowed in this account"
    )
    settings = models.JSONField(
        default=dict,
        blank=True,
        help_text="Custom settings and preferences for this account"
    )

    class Meta:
        verbose_name = "Account"
        verbose_name_plural = "Accounts"

    def __str__(self):
        return f"{self.name} ({self.get_subscription_plan_display()})"

    def is_at_user_limit(self):
        """Check if the account has reached its maximum user limit."""
        return self.users.count() >= self.max_users

    def can_add_user(self):
        """Check if a new user can be added to this account."""
        return not self.is_at_user_limit()
