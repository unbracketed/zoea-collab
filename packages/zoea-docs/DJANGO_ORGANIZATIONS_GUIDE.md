# Django Organizations Guide

This guide establishes best practices for using django-organizations throughout the Zoea Studio project. **All developers must follow these patterns when building new features.**

## Overview

Every Django user in Zoea Studio is part of an Organization via an Account. This provides:
- Multi-tenant architecture out of the box
- Clear user-organization relationships
- Built-in invitation and membership management
- Flexible permission and access control

## Core Concepts

### Model Structure

```
Organization (Company/Team)
  └── OrganizationUser (Membership)
      └── User (Django User)

OrganizationOwner (Special type of OrganizationUser)
```

**Key Principle:** Users are linked to Organizations through the explicit `OrganizationUser` model, not via direct many-to-many relationships.

## Best Practices

### 1. Model Inheritance Strategy

Choose the right inheritance approach based on your needs:

**Proxy Models** (Minimal Customization):
```python
class Account(Organization):
    class Meta:
        proxy = True
```
Use when: Only customizing admin interface, no additional fields needed

**Multi-Table Inheritance** (Adding Fields):
```python
class Account(Organization):
    subscription_plan = models.CharField(max_length=50)
    billing_email = models.EmailField()
```
Use when: Adding fields to organizations while keeping base model features
⚠️ **Warning:** Only one custom organization model per app

**Abstract Models** (Complete Customization):
```python
from organizations.base import OrganizationBase

class Account(OrganizationBase):
    # Your custom fields
    pass
```
Use when: Need complete control over implementation

**Base Models** (Minimal Requirements):
Use when: Default implementations don't fit your needs

### 2. User-Organization Relationships

**❌ Don't:** Expose many-to-many user relationships directly
```python
# Avoid this pattern
organization.users.all()
```

**✅ Do:** Manage users through OrganizationUser
```python
# Correct pattern
organization.organization_users.all()
organization.users.through.objects.filter(organization=org)
```

**Why:** This accounts for invitation workflows and provides better admin experience.

### 3. Resource Association

**Linking Resources to Organizations:**
```python
class ChatMessage(models.Model):
    organization = models.ForeignKey('organizations.Organization', on_delete=models.CASCADE)
    content = models.TextField()
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
```

**For Third-Party Models:**
Create explicit linking models with uniqueness constraints:
```python
class OrganizationResource(models.Model):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE)
    resource = models.ForeignKey(ThirdPartyModel, on_delete=models.CASCADE)

    class Meta:
        unique_together = ('organization', 'resource')
```

### 4. Access Control & Security

**❌ Don't:** Rely solely on view-level checks
```python
# Fragile approach
def my_view(request):
    if not request.user.organization_set.exists():
        return HttpResponseForbidden()
```

**✅ Do:** Use custom querysets and managers
```python
class ChatMessageQuerySet(models.QuerySet):
    def for_organization(self, organization):
        return self.filter(organization=organization)

    def for_user(self, user):
        return self.filter(
            organization__organization_users__user=user
        )

class ChatMessage(models.Model):
    objects = ChatMessageQuerySet.as_manager()
    # ...

# In views
messages = ChatMessage.objects.for_user(request.user)
```

**Key Principle:** "Relying on the filters from related managers whenever possible reduces the room for mistakes."

### 5. Invitation Workflow

**Custom Forms for Invitations:**
```python
from organizations.forms import OrganizationUserForm

class CustomInvitationForm(OrganizationUserForm):
    def save(self, commit=True):
        # Handle both OrganizationUser creation
        # and User model updates
        instance = super().save(commit=False)
        # Additional logic here
        if commit:
            instance.save()
        return instance
```

**Generate Registration Links:**
Use the invitation backend to create email-based onboarding with unique tokens.

### 6. Admin Customization

**When using proxy models:**
```python
from django.contrib import admin
from organizations.models import Organization, OrganizationUser, OrganizationOwner

# Unregister defaults
admin.site.unregister(Organization)
admin.site.unregister(OrganizationUser)
admin.site.unregister(OrganizationOwner)

# Register custom implementations
@admin.register(Account)
class AccountAdmin(admin.ModelAdmin):
    # Custom admin implementation
    pass
```

## Common Patterns for Zoea Studio

### Pattern: Scoping Chat Messages to Organization
```python
# Model
class ChatMessage(models.Model):
    organization = models.ForeignKey('organizations.Organization', on_delete=models.CASCADE)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    content = models.TextField()

# View/API
from organizations.utils import get_organization_from_user

@router.post("/chat")
def chat(request, data: ChatRequest):
    # Get user's active organization
    org = get_organization_from_user(request.user)

    # Create message scoped to organization
    message = ChatMessage.objects.create(
        organization=org,
        created_by=request.user,
        content=data.message
    )
    return {"status": "success"}
```

### Pattern: Multi-Tenant Diagram Data
```python
class DiagramData(models.Model):
    organization = models.ForeignKey('organizations.Organization', on_delete=models.CASCADE)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    conversation_history = models.TextField()

    objects = DiagramDataQuerySet.as_manager()

    class Meta:
        ordering = ['-created_at']

# Always filter by user's organization
diagrams = DiagramData.objects.for_user(request.user)
```

### Pattern: Organization-Scoped Agent Context
```python
# Pass organization context to agents
service = ChatAgentService()
org = get_organization_from_user(request.user)

instructions = f"""
You are assisting {request.user.get_full_name()}
from {org.name}.
Context: {org.get_context_data()}
"""

agent = service.create_agent(
    name="chat_agent",
    instructions=instructions
)
```

## Critical Gotchas ⚠️

1. **One Organization Model Per App:** Each app can only define one organization model set with abstract/base inheritance

2. **Email Address Immutability:** Make email addresses read-only post-invitation to prevent synchronization issues

3. **Abstract Model Dependencies:** Abstract models include timestamps, slug fields - don't forget to migrate these

4. **Base Model Requirements:** Base models require manual implementation of features

5. **Permission Testing:** Always test permission checks thoroughly - queryset filtering prevents data leaks better than view decorators

## Implementation Checklist

When adding new features to Zoea Studio:

- [ ] Does this resource belong to an organization? → Add `organization` ForeignKey
- [ ] Does this need user access control? → Implement custom queryset with `for_user()` method
- [ ] Are you filtering data in a view? → Move filtering logic to manager/queryset
- [ ] Does this involve user invitations? → Use invitation backend with tokens
- [ ] Are you testing permissions? → Test via queryset filtering, not just view checks

## References

- [Django Organizations Cookbook](https://django-organizations.readthedocs.io/en/latest/cookbook.html)
- [Django Organizations Documentation](https://django-organizations.readthedocs.io/)

## Version History

- 2025-11-09: Initial guide created for Zoea Studio project
