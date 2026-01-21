from django.contrib import admin
from organizations.models import Organization, OrganizationUser, OrganizationOwner

from .models import Account


# Unregister default organization models
# We use our custom Account model instead
admin.site.unregister(Organization)
admin.site.unregister(OrganizationUser)
admin.site.unregister(OrganizationOwner)


class OrganizationUserInline(admin.TabularInline):
    """Inline admin for managing organization members."""
    model = OrganizationUser
    extra = 0
    fields = ['user', 'is_admin']
    raw_id_fields = ['user']


class OrganizationOwnerInline(admin.StackedInline):
    """Inline admin for managing organization owner."""
    model = OrganizationOwner
    max_num = 1
    fields = ['organization_user']


@admin.register(Account)
class AccountAdmin(admin.ModelAdmin):
    """
    Admin interface for Account (Organization) management.

    Displays key subscription and billing information, and allows
    managing organization members inline.
    """
    list_display = [
        'name',
        'subscription_plan',
        'user_count',
        'max_users',
        'created',
        'is_active'
    ]
    list_filter = ['subscription_plan', 'is_active', 'created']
    search_fields = ['name', 'billing_email', 'slug']
    readonly_fields = ['created', 'modified', 'slug']
    fieldsets = [
        ('Basic Information', {
            'fields': ['name', 'slug', 'is_active']
        }),
        ('Subscription & Billing', {
            'fields': ['subscription_plan', 'billing_email', 'max_users']
        }),
        ('Settings', {
            'fields': ['settings'],
            'classes': ['collapse']
        }),
        ('Timestamps', {
            'fields': ['created', 'modified'],
            'classes': ['collapse']
        }),
    ]
    inlines = [OrganizationUserInline, OrganizationOwnerInline]

    def user_count(self, obj):
        """Display current number of users in the organization."""
        return obj.users.count()
    user_count.short_description = "Users"

    def get_queryset(self, request):
        """Optimize queryset with prefetch_related for user counts."""
        qs = super().get_queryset(request)
        return qs.prefetch_related('users')


@admin.register(OrganizationUser)
class OrganizationUserAdmin(admin.ModelAdmin):
    """Admin interface for OrganizationUser relationships."""
    list_display = ['user', 'organization', 'is_admin', 'created']
    list_filter = ['is_admin', 'created']
    search_fields = ['user__username', 'user__email', 'organization__name']
    raw_id_fields = ['user', 'organization']


@admin.register(OrganizationOwner)
class OrganizationOwnerAdmin(admin.ModelAdmin):
    """Admin interface for OrganizationOwner relationships."""
    list_display = ['organization', 'organization_user', 'created']
    search_fields = ['organization__name', 'organization_user__user__username']
    raw_id_fields = ['organization', 'organization_user']
