# Django Organizations Implementation Plan

This document outlines the step-by-step plan for integrating django-organizations into Zoea Studio.

## Prerequisites

- [ ] Read `docs/DJANGO_ORGANIZATIONS_GUIDE.md` thoroughly
- [ ] Understand multi-tenant architecture patterns
- [ ] Review existing codebase structure

## Phase 1: Installation & Setup

### 1.1 Install django-organizations
```bash
cd backend
uv add django-organizations
```

### 1.2 Update Django Settings
Add to `backend/zoeastudio/settings.py`:
```python
INSTALLED_APPS = [
    # ... existing apps
    'organizations',
    'accounts',  # Our custom app for Account model
]
```

### 1.3 Create Accounts App
```bash
cd backend
uv run python manage.py startapp accounts
```

### 1.4 Create Account Model
In `backend/accounts/models.py`:
```python
from organizations.models import Organization, OrganizationUser, OrganizationOwner

class Account(Organization):
    """
    Multi-table inheritance approach to add custom fields to Organization.
    Each Account represents a company/team that can have multiple users.
    """
    # Custom fields for Zoea Studio
    subscription_plan = models.CharField(
        max_length=50,
        default='free',
        choices=[
            ('free', 'Free'),
            ('pro', 'Pro'),
            ('enterprise', 'Enterprise'),
        ]
    )
    billing_email = models.EmailField(blank=True, null=True)
    max_users = models.IntegerField(default=5)
    settings = models.JSONField(default=dict, blank=True)

    class Meta:
        verbose_name = "Account"
        verbose_name_plural = "Accounts"

    def __str__(self):
        return self.name
```

### 1.5 Create Custom Querysets (Future-Ready)
In `backend/accounts/managers.py`:
```python
from django.db import models

class OrganizationScopedQuerySet(models.QuerySet):
    """Base queryset for organization-scoped resources."""

    def for_user(self, user):
        """Filter resources to those accessible by the given user."""
        return self.filter(
            organization__organization_users__user=user
        )

    def for_organization(self, organization):
        """Filter resources to a specific organization."""
        return self.filter(organization=organization)
```

### 1.6 Run Migrations
```bash
cd backend
uv run python manage.py makemigrations
uv run python manage.py migrate
```

### 1.7 Update Admin Interface
In `backend/accounts/admin.py`:
```python
from django.contrib import admin
from organizations.models import Organization, OrganizationUser, OrganizationOwner
from .models import Account

# Unregister default organization models
admin.site.unregister(Organization)
admin.site.unregister(OrganizationUser)
admin.site.unregister(OrganizationOwner)

@admin.register(Account)
class AccountAdmin(admin.ModelAdmin):
    list_display = ['name', 'subscription_plan', 'created']
    list_filter = ['subscription_plan', 'created']
    search_fields = ['name', 'billing_email']
```

## Phase 2: Update Existing Models (If Applicable)

### 2.1 Identify Existing Models
Check for any models that should be scoped to organizations:
- [ ] Chat messages/conversations (if they exist)
- [ ] Diagram data (if persisted)
- [ ] Any other user-created content

### 2.2 Add Organization ForeignKey
For each identified model, add:
```python
class ChatConversation(models.Model):
    organization = models.ForeignKey(
        'organizations.Organization',
        on_delete=models.CASCADE,
        related_name='conversations'
    )
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    # ... other fields

    objects = OrganizationScopedQuerySet.as_manager()

    class Meta:
        ordering = ['-created_at']
```

### 2.3 Create Migrations
```bash
cd backend
uv run python manage.py makemigrations
# Review migration files
uv run python manage.py migrate
```

## Phase 3: Update API Layer

### 3.1 Add Organization Context Helper
In `backend/accounts/utils.py`:
```python
from organizations.models import OrganizationUser

def get_user_organization(user):
    """
    Get the active organization for a user.
    For now, returns the first organization.
    TODO: Implement organization switching in future.
    """
    try:
        org_user = OrganizationUser.objects.filter(user=user).first()
        return org_user.organization if org_user else None
    except OrganizationUser.DoesNotExist:
        return None

def require_organization(user):
    """Get organization or raise exception."""
    org = get_user_organization(user)
    if not org:
        raise ValueError("User is not associated with any organization")
    return org
```

### 3.2 Update API Endpoints
In `backend/chat/api.py`:
```python
from accounts.utils import require_organization

@router.post("/chat")
async def chat(request, data: ChatRequest):
    # Get user's organization
    organization = require_organization(request.user)

    # Scope any database queries to organization
    # conversations = ChatConversation.objects.for_user(request.user)

    # Pass organization context to agent
    instructions = f"""
    You are assisting {request.user.get_full_name()}
    from {organization.name}.
    """

    # ... rest of implementation
```

### 3.3 Update Tests
Add organization fixtures to tests:
```python
import pytest
from organizations.models import Organization, OrganizationUser

@pytest.fixture
def organization(db):
    return Organization.objects.create(name="Test Org")

@pytest.fixture
def org_user(db, organization):
    user = User.objects.create_user(username="test", email="test@example.com")
    OrganizationUser.objects.create(
        user=user,
        organization=organization
    )
    return user
```

## Phase 4: Authentication & User Management

### 4.1 Update User Registration
When creating new users, ensure they're added to an organization:
```python
def create_user_with_organization(email, password, org_name=None):
    user = User.objects.create_user(
        username=email,
        email=email,
        password=password
    )

    if org_name:
        # Add to existing organization
        org = Organization.objects.get(name=org_name)
    else:
        # Create new organization
        org = Organization.objects.create(
            name=f"{user.email}'s Organization"
        )

    OrganizationUser.objects.create(
        user=user,
        organization=org,
        is_admin=True
    )

    return user, org
```

### 4.2 Implement Invitation Workflow (Future)
- [ ] Create invitation form
- [ ] Generate unique tokens
- [ ] Send invitation emails
- [ ] Handle invitation acceptance

## Phase 5: Frontend Updates

### 5.1 Display Organization Context
Update UI to show current organization:
```jsx
// In App.jsx or Header component
function OrganizationIndicator() {
  const [organization, setOrganization] = useState(null);

  useEffect(() => {
    // Fetch current organization from API
    fetch('/api/user/organization')
      .then(res => res.json())
      .then(data => setOrganization(data));
  }, []);

  return (
    <div className="organization-badge">
      {organization?.name}
    </div>
  );
}
```

### 5.2 Add Organization Selector (Future)
For users in multiple organizations:
```jsx
function OrganizationSelector() {
  const [organizations, setOrganizations] = useState([]);
  const [current, setCurrent] = useState(null);

  // Implementation here
}
```

## Phase 6: Testing & Validation

### 6.1 Test Data Isolation
```python
def test_organization_isolation(org1, org2, user1, user2):
    """Ensure users can't access other organizations' data."""
    # Create data in org1
    conversation1 = ChatConversation.objects.create(
        organization=org1,
        created_by=user1
    )

    # User2 (in org2) should not see org1's data
    visible = ChatConversation.objects.for_user(user2)
    assert conversation1 not in visible
```

### 6.2 Test Permission Filtering
```python
def test_queryset_filtering(org_user):
    """Test that querysets properly filter by organization."""
    conversations = ChatConversation.objects.for_user(org_user)
    for conv in conversations:
        assert conv.organization in org_user.organizations_organization.all()
```

### 6.3 Manual Testing Checklist
- [ ] Create user in organization A
- [ ] Create content as user in org A
- [ ] Create user in organization B
- [ ] Verify user B cannot see org A content
- [ ] Test organization switching (if implemented)
- [ ] Test invitation workflow (if implemented)

## Phase 7: Documentation & Migration Guide

### 7.1 Update README
Document new user/organization structure

### 7.2 Create Migration Guide
For existing users/data (if applicable)

### 7.3 Update API Documentation
Document organization-scoping requirements

## Success Criteria

- [x] django-organizations installed and configured
- [ ] Account model created with migrations
- [ ] All existing models updated with organization ForeignKey
- [ ] Custom querysets implemented for access control
- [ ] API endpoints scope data by organization
- [ ] Tests verify data isolation
- [ ] Admin interface configured
- [ ] Frontend displays organization context
- [ ] Documentation complete

## Rollback Plan

If issues arise:
1. Revert migrations: `python manage.py migrate accounts zero`
2. Remove from INSTALLED_APPS
3. Restore previous codebase from git

## Next Steps After Completion

1. Implement organization switching UI
2. Add invitation workflow
3. Create organization settings page
4. Implement role-based permissions
5. Add organization analytics/usage tracking

## References

- `docs/DJANGO_ORGANIZATIONS_GUIDE.md` - Best practices
- https://django-organizations.readthedocs.io/ - Official docs
- https://django-organizations.readthedocs.io/en/latest/cookbook.html - Cookbook
