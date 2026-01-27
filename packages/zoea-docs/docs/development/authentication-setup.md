# Authentication System Setup and Development

This guide covers the technical implementation of Zoea Collab's authentication system for developers who need to understand, modify, or extend the authentication functionality.

## Overview

Zoea Collab uses [django-allauth](https://docs.allauth.org/) for user registration and authentication, integrated with our multi-tenant organization system. The system provides:

- User registration with email verification
- Username or email-based login
- Custom account adapter for organization initialization
- Django Ninja REST API endpoints
- CLI commands for user management

## Architecture

### Technology Stack

- **django-allauth 65.13.1**: User registration and account management
- **Django 6.0**: Web framework
- **Django Ninja**: REST API framework
- **Pydantic**: Request/response schemas
- **Typer**: CLI framework

### Components

```
┌─────────────────────────────────────────────────────────────┐
│                      Frontend (React)                        │
│  ┌────────────────┐  ┌──────────────────┐  ┌──────────────┐│
│  │ Register.jsx   │  │ Login.jsx        │  │ VerifyEmail  ││
│  │                │  │                  │  │ Page.jsx     ││
│  └────────────────┘  └──────────────────┘  └──────────────┘│
└──────────────────────────┬──────────────────────────────────┘
                           │ HTTP/JSON
┌──────────────────────────▼──────────────────────────────────┐
│                   Django Ninja API Layer                     │
│  ┌────────────────────────────────────────────────────────┐ │
│  │ accounts/api.py                                        │ │
│  │  - /api/auth/signup                                    │ │
│  │  - /api/auth/verify-email                             │ │
│  │  - /api/auth/resend-verification                      │ │
│  │  - /api/auth/login                                    │ │
│  │  - /api/auth/logout                                   │ │
│  │  - /api/auth/check                                    │ │
│  └────────────────────────────────────────────────────────┘ │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│                    django-allauth Core                       │
│  ┌────────────────────────────────────────────────────────┐ │
│  │ allauth.account.forms.SignupForm                      │ │
│  │ allauth.account.models.EmailAddress                   │ │
│  │ allauth.account.models.EmailConfirmation              │ │
│  └────────────────────────────────────────────────────────┘ │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│               Custom Integration Layer                       │
│  ┌────────────────────────────────────────────────────────┐ │
│  │ accounts/adapters.py - AccountAdapter                 │ │
│  │  - Hooks into signup process                          │ │
│  │  - Calls initialize_user_organization()               │ │
│  └────────────────────────────────────────────────────────┘ │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│              Multi-Tenant Organization System                │
│  ┌────────────────────────────────────────────────────────┐ │
│  │ accounts/utils.py - initialize_user_organization()    │ │
│  │  1. Create Organization (Account)                     │ │
│  │  2. Create OrganizationUser (membership)              │ │
│  │  3. Create OrganizationOwner                          │ │
│  │  4. Signals trigger:                                  │ │
│  │     - Default Project creation                        │ │
│  │     - Default Workspace creation                      │ │
│  │     - Default Clipboard creation                      │ │
│  └────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

## Setup and Configuration

### Required Django Apps

In `backend/zoeastudio/settings.py`:

```python
INSTALLED_APPS = [
    # Django core
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.sites',  # Required by django-allauth

    # Third-party
    'allauth',
    'allauth.account',

    # Your apps
    'accounts',
    # ... other apps
]
```

### Required Middleware

```python
MIDDLEWARE = [
    # ... other middleware
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'allauth.account.middleware.AccountMiddleware',  # Must come after AuthenticationMiddleware
    # ... other middleware
]
```

### Authentication Backends

```python
AUTHENTICATION_BACKENDS = [
    # Django default backend
    'django.contrib.auth.backends.ModelBackend',
    # django-allauth backend
    'allauth.account.auth_backends.AuthenticationBackend',
]
```

### django-allauth Configuration

```python
# Sites framework (required by django-allauth)
SITE_ID = 1

# Login methods
ACCOUNT_LOGIN_METHODS = {'email', 'username'}  # Allow both username and email

# Signup fields
ACCOUNT_SIGNUP_FIELDS = ['email*', 'username*', 'password1*', 'password2*']

# Email verification
ACCOUNT_EMAIL_VERIFICATION = 'mandatory'  # Require email verification
ACCOUNT_UNIQUE_EMAIL = True  # Ensure unique email addresses
ACCOUNT_EMAIL_CONFIRMATION_EXPIRE_DAYS = 3  # Verification link expires in 3 days
ACCOUNT_LOGIN_ON_EMAIL_CONFIRMATION = True  # Auto-login after verification

# Logout settings
ACCOUNT_LOGOUT_ON_GET = False  # Require POST for security

# Redirects
LOGIN_REDIRECT_URL = '/'
ACCOUNT_LOGOUT_REDIRECT_URL = '/'

# Custom adapter
ACCOUNT_ADAPTER = 'accounts.adapters.AccountAdapter'
```

### Email Configuration

**Development** (prints to console):
```python
if DEBUG:
    EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
```

**Production** (SMTP):
```python
else:
    EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
    EMAIL_HOST = os.getenv('EMAIL_HOST', 'smtp.gmail.com')
    EMAIL_PORT = int(os.getenv('EMAIL_PORT', 587))
    EMAIL_USE_TLS = os.getenv('EMAIL_USE_TLS', 'True') == 'True'
    EMAIL_HOST_USER = os.getenv('EMAIL_HOST_USER')
    EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD')
    DEFAULT_FROM_EMAIL = os.getenv('DEFAULT_FROM_EMAIL', 'noreply@zoea.studio')
```

### URL Configuration

In `backend/zoeastudio/urls.py`:

```python
from django.urls import path, include

urlpatterns = [
    # django-allauth URLs (not used directly by our frontend)
    path("accounts/", include("allauth.account.urls")),

    # Our custom API
    path("api/auth/", include("accounts.api")),

    # ... other URLs
]
```

## Implementation Details

### Custom Account Adapter

The `AccountAdapter` in `backend/accounts/adapters.py` hooks into the django-allauth signup flow:

```python
from allauth.account.adapter import DefaultAccountAdapter
from .utils import initialize_user_organization

class AccountAdapter(DefaultAccountAdapter):
    """
    Custom adapter that creates an organization for new users.
    """

    def save_user(self, request, user, form, commit=True):
        """
        Called during signup after user is created.
        """
        # Let default adapter save the user
        user = super().save_user(request, user, form, commit=commit)

        if commit:
            try:
                # Create organization, project, workspace, clipboard
                result = initialize_user_organization(user)

                logger.info(
                    f"Created organization '{result['organization'].name}' "
                    f"for user '{user.username}'"
                )

            except Exception as e:
                logger.error(
                    f"Failed to create organization for '{user.username}': {e}",
                    exc_info=True
                )
                # In production, you might want to raise here to prevent
                # incomplete signups. Currently, we log and continue.

        return user
```

### Organization Initialization

The `initialize_user_organization()` function in `backend/accounts/utils.py`:

```python
from django.db import transaction
from organizations.models import Organization, OrganizationUser, OrganizationOwner

@transaction.atomic
def initialize_user_organization(user):
    """
    Create an organization for a new user with default resources.

    This function:
    1. Creates an Organization (Account)
    2. Creates OrganizationUser membership (admin role)
    3. Creates OrganizationOwner record
    4. Signals trigger automatic creation of:
       - Default Project
       - Default Workspace
       - Default Clipboard

    Args:
        user: Django User instance

    Returns:
        dict with created objects
    """
    # Create organization
    org = Organization.objects.create(
        name=f"{user.username}'s Organization",
        slug=slugify(f"{user.username}s-organization"),
    )

    # Add user as admin member
    org_user = OrganizationUser.objects.create(
        organization=org,
        user=user,
        role='admin'
    )

    # Set as owner
    owner = OrganizationOwner.objects.create(
        organization=org,
        organization_user=org_user
    )

    # Signals will create:
    # - Project (via create_default_project signal)
    # - Workspace (via create_default_workspace signal)
    # - Clipboard (via create_default_clipboard signal)

    return {
        'organization': org,
        'membership': org_user,
        'owner': owner
    }
```

### API Endpoints Implementation

#### Signup Endpoint

```python
@router.post("/signup", response=SignupResponse, auth=None)
async def auth_signup(request, payload: SignupRequest):
    """
    Register a new user with email verification.
    """
    @sync_to_async
    def _create_user():
        # Prepare form data
        form_data = {
            'username': payload.username,
            'email': payload.email,
            'password1': payload.password1,
            'password2': payload.password2,
        }

        # Validate with django-allauth SignupForm
        form = SignupForm(data=form_data)

        if not form.is_valid():
            # Extract and format errors
            errors = []
            for field, field_errors in form.errors.items():
                for error in field_errors:
                    errors.append(f"{field}: {error}")
            raise HttpError(400, "; ".join(errors))

        # Save user (triggers AccountAdapter.save_user)
        with transaction.atomic():
            user = form.save(request)

            # Send verification email
            email_address = get_address_for_user(user)
            if email_address:
                send_verification_email_to_address(
                    request, email_address, signup=True
                )

            return user

    user = await _create_user()

    return SignupResponse(
        success=True,
        message="Registration successful. Please check your email.",
        username=user.username,
        email=user.email,
    )
```

#### Email Verification Endpoint

```python
@router.post("/verify-email", response=VerifyEmailResponse, auth=None)
async def verify_email(request, payload: VerifyEmailRequest):
    """
    Verify email with confirmation key.
    """
    @sync_to_async
    def _verify_email():
        try:
            # Try database-backed confirmation first
            confirmation = EmailConfirmation.objects.get(
                key=payload.key.lower()
            )

            if confirmation.email_address.verified:
                return {
                    'success': True,
                    'message': 'Email already verified.',
                }

            # Confirm the email
            confirmation.confirm(request)

            return {
                'success': True,
                'message': 'Email verified successfully. You can now log in.',
            }

        except EmailConfirmation.DoesNotExist:
            # Try HMAC-based confirmation (doesn't expire)
            confirmation = EmailConfirmationHMAC.from_key(payload.key)
            if confirmation:
                # ... similar verification logic
                pass
            else:
                raise HttpError(400, "Invalid or expired verification key.")

    result = await _verify_email()
    return VerifyEmailResponse(**result)
```

### Pydantic Schemas

In `backend/accounts/schemas.py`:

```python
from pydantic import BaseModel, Field

class SignupRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=150)
    email: str = Field(...)
    password1: str = Field(..., min_length=8)
    password2: str = Field(..., min_length=8)

class SignupResponse(BaseModel):
    success: bool
    message: str
    username: str
    email: str

class VerifyEmailRequest(BaseModel):
    key: str = Field(..., min_length=1)

class VerifyEmailResponse(BaseModel):
    success: bool
    message: str
```

## Database Migrations

The authentication system requires migrations from:

1. **django.contrib.sites**: For the sites framework
2. **allauth.account**: For user accounts and email verification
3. **Your custom apps**: For organizations, projects, workspaces

### Running Migrations

```bash
cd backend
uv run python manage.py migrate
```

### Required Migrations

- `sites.0001_initial` - Sites framework
- `sites.0002_alter_domain_unique` - Domain uniqueness
- `account.0001_initial` through `account.0009_emailaddress_unique_primary_email` - django-allauth

### Site Configuration

After migrations, configure the Site model:

```bash
uv run python manage.py shell
```

```python
from django.contrib.sites.models import Site

site = Site.objects.get(id=1)
site.domain = 'localhost:8000'  # Development
site.name = 'Zoea Collab (Development)'
site.save()

# For production:
# site.domain = 'yourdomain.com'
# site.name = 'Zoea Collab'
```

## Development Workflow

### Skipping Email Verification

For development and testing, you can skip email verification using the CLI:

```bash
zoea users create \
  --username testuser \
  --email test@localhost \
  --password test123 \
  --skip-email-verification \
  --force
```

This creates an `EmailAddress` record with `verified=True`.

### Viewing Verification Emails

In development mode, emails are printed to the console where you ran the Django server.

Look for output like:

```
Subject: [Zoea Collab (Development)] Please Confirm Your Email Address
From: noreply@zoea.studio
To: testuser@example.com

Hello from Zoea Collab (Development)!

Please confirm your email address by clicking on the link below:

http://localhost:8000/accounts/confirm-email/abc123def456...
```

### Testing Registration Flow

1. Start the development server:
   ```bash
   mise run dev-backend
   ```

2. Register a user via API:
   ```bash
   curl -X POST http://localhost:8000/api/auth/signup \
     -H "Content-Type: application/json" \
     -d '{
       "username": "testuser",
       "email": "test@example.com",
       "password1": "SecurePass123",
       "password2": "SecurePass123"
     }'
   ```

3. Check the server console for the verification email

4. Extract the verification key from the email URL

5. Verify the email:
   ```bash
   curl -X POST http://localhost:8000/api/auth/verify-email \
     -H "Content-Type: application/json" \
     -d '{"key":"abc123def456..."}'
   ```

6. Verify the organization was created:
   ```bash
   zoea projects list
   ```

## Testing

### Backend Tests

Run the comprehensive test suite:

```bash
cd backend
uv run pytest accounts/test_registration.py -v
```

### Test Coverage

The test suite covers:

- **User Registration** (6 tests)
  - User creation
  - Email verification sending
  - Field validation
  - Password validation
  - Duplicate username prevention

- **Organization Integration** (5 tests)
  - Organization creation
  - Project/workspace creation via signals
  - Owner assignment
  - Subscription configuration
  - Multiple user isolation

- **Email Verification** (2 tests)
  - Verification link functionality
  - Login prevention before verification

- **Edge Cases** (2 tests)
  - Full name handling
  - Graceful error handling

### Frontend Tests

Run Playwright E2E tests:

```bash
cd frontend
npm run test:e2e -- tests/e2e/registration.spec.js
```

Tests cover:
- Registration form display
- Client-side validation
- Form submission
- Email verification flow
- Resend verification

## Troubleshooting

### Email Verification Not Working

**Problem**: Users not receiving verification emails in production.

**Solutions**:

1. Check SMTP configuration in environment variables
2. Verify `EMAIL_HOST_USER` and `EMAIL_HOST_PASSWORD` are set
3. Check email provider's sending limits
4. Review Django logs for SMTP errors
5. Test SMTP connection:
   ```python
   from django.core.mail import send_mail
   send_mail(
       'Test',
       'Test message',
       'noreply@yourdomain.com',
       ['test@example.com'],
   )
   ```

### Organization Not Created

**Problem**: User registered but no organization exists.

**Solutions**:

1. Check Django logs for exceptions in `AccountAdapter.save_user()`
2. Verify signals are connected:
   ```bash
   uv run python manage.py shell
   ```
   ```python
   from django.db.models import signals
   from accounts.models import Organization
   print(signals.post_save.has_listeners(Organization))
   ```
3. Run organization creation manually:
   ```python
   from accounts.utils import initialize_user_organization
   from django.contrib.auth import get_user_model

   User = get_user_model()
   user = User.objects.get(username='username')
   result = initialize_user_organization(user)
   ```

### Import Errors in CLI

**Problem**: `ModuleNotFoundError` when running `zoea users create`.

**Solution**: The CLI's `django_context.py` adds the backend directory to Python path. If you still see import errors:

1. Verify you're in the project root directory
2. Check that `backend/` exists
3. Ensure Django apps are in `backend/`
4. Review `backend/cli/utils/django_context.py`

### Duplicate Email Errors

**Problem**: Getting "email already exists" for unverified users.

**Cause**: `ACCOUNT_UNIQUE_EMAIL = True` prevents duplicate emails even for unverified accounts.

**Solutions**:

1. Use resend verification instead of re-registering
2. Delete the unverified user via Django admin
3. Implement cleanup for old unverified accounts

## Security Considerations

### Password Security

- Django's `PBKDF2PasswordHasher` is used by default
- Passwords hashed with 600,000 iterations (Django 6.0 default)
- Never log or display passwords
- Use `getpass.getpass()` for CLI password input

### Email Verification Security

- Verification keys are cryptographically secure random tokens
- Links expire after 3 days
- HMAC-based fallback prevents replay attacks
- Already-verified emails cannot be re-verified

### CSRF Protection

- All state-changing endpoints require CSRF tokens
- Django Ninja handles CSRF automatically for session auth
- Logout requires POST (not GET) to prevent CSRF

### Session Security

- HTTP-only cookies (JavaScript cannot access)
- SameSite=Lax prevents CSRF attacks
- Secure flag in production (HTTPS only)

## Customization

### Custom Email Templates

Override django-allauth email templates:

1. Create `backend/templates/account/email/`
2. Copy templates from django-allauth
3. Customize HTML/text versions

### Custom Signup Fields

Add additional fields to signup:

1. Update `SignupRequest` schema
2. Override `AccountAdapter.save_user()` to handle extra fields
3. Update frontend registration form

### Custom Organization Naming

Modify organization name format in `initialize_user_organization()`:

```python
# Default
name = f"{user.username}'s Organization"

# Custom based on full name
if user.first_name and user.last_name:
    name = f"{user.first_name} {user.last_name}'s Organization"
else:
    name = f"{user.username}'s Organization"
```

## Related Files

### Backend

- `backend/accounts/api.py` - API endpoints
- `backend/accounts/schemas.py` - Pydantic schemas
- `backend/accounts/adapters.py` - Custom django-allauth adapter
- `backend/accounts/utils.py` - Organization initialization
- `backend/accounts/test_registration.py` - Test suite
- `backend/cli/commands/users.py` - CLI commands
- `backend/zoeastudio/settings.py` - Configuration

### Frontend

- `frontend/src/components/Register.jsx` - Registration form
- `frontend/src/pages/VerifyEmailPage.jsx` - Email verification page
- `frontend/src/services/api.js` - API client
- `frontend/tests/e2e/registration.spec.js` - E2E tests

## Further Reading

- [django-allauth Documentation](https://docs.allauth.org/)
- [Django Authentication System](https://docs.djangoproject.com/en/6.0/topics/auth/)
- [Multi-Tenant Architecture](../architecture/multi-tenant.md)
- [Django Ninja Documentation](https://django-ninja.rest-framework.com/)
