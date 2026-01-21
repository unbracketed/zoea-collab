# Backend: Create User Registration API Endpoints

## Task Summary

Successfully implemented Django Ninja API endpoints for user registration functionality, integrating with django-allauth for email verification and leveraging the existing custom adapter to automatically create organizations, projects, workspaces, and clipboards for new users.

## Files Modified

- `/Users/brian/CitrusGrove/projects/ZoeaStudio/backend/accounts/schemas.py` - Added Pydantic schemas for signup, email verification, and resend verification endpoints
- `/Users/brian/CitrusGrove/projects/ZoeaStudio/backend/accounts/api.py` - Added three new API endpoints for user registration workflow
- `/Users/brian/CitrusGrove/projects/ZoeaStudio/backend/accounts/tests.py` - Added comprehensive test suite with 13 new tests

## Files Created

None (extended existing files)

## Implementation Details

### API Endpoints Implemented

1. **POST /api/auth/signup**
   - Registers a new user with username, email, and password
   - Uses django-allauth's `SignupForm` for validation
   - Automatically creates organization structure via custom `AccountAdapter`
   - Sends email verification via allauth's internal flows
   - Returns user info with success message

2. **POST /api/auth/verify-email**
   - Verifies user's email address using confirmation key from email
   - Supports both standard `EmailConfirmation` and HMAC-based confirmation
   - Handles already-verified emails gracefully
   - Returns success status with appropriate message

3. **POST /api/auth/resend-verification**
   - Resends verification email to a user
   - Validates that email isn't already verified
   - Doesn't reveal whether email exists (security best practice)
   - Returns success status

### Key Design Decisions

1. **Django-allauth Integration**: Used django-allauth version 65.13.1's internal flows for email verification rather than deprecated utility functions. Specifically:
   - `send_verification_email_to_address()` from `allauth.account.internal.flows.email_verification`
   - `get_address_for_user()` for retrieving EmailAddress objects

2. **Async/Await Pattern**: Followed existing codebase pattern using `@sync_to_async` decorator for database operations within async endpoint functions.

3. **Error Handling**:
   - Form validation errors are extracted and formatted as semicolon-separated strings
   - `ValueError` exceptions from `form.save()` (e.g., duplicate emails) are caught and converted to HTTP 400 errors
   - Generic exceptions are logged with full traceback and return HTTP 500 errors

4. **Security Considerations**:
   - Resend verification doesn't reveal whether an email exists in the system
   - All endpoints use `auth=None` to allow unauthenticated access (necessary for registration)
   - Passwords validated by Django's built-in validators

5. **Organization Auto-Creation**: The existing `AccountAdapter.save_user()` method automatically calls `initialize_user_organization()`, which creates:
   - Organization (Account) with user as owner
   - Default project (via signals)
   - Default workspace (via signals)
   - Active clipboard (via signals)

### Integration Points

- **Forms**: Uses `allauth.account.forms.SignupForm` for validation
- **Models**: Works with `EmailAddress`, `EmailConfirmation`, and `EmailConfirmationHMAC` from django-allauth
- **Adapter**: Leverages custom `accounts.adapters.AccountAdapter` for organization creation
- **Email Backend**: Uses Django's configured email backend (console in development, SMTP in production)

## Tests Written

### Unit Tests (N/A - API tests cover functionality)

### Integration Tests

All 13 tests in `TestAuthAPIEndpoints` class:

1. **test_signup_endpoint_success** - Verifies successful user registration creates user, organization, and unverified email
2. **test_signup_endpoint_password_mismatch** - Ensures passwords must match
3. **test_signup_endpoint_duplicate_username** - Prevents duplicate usernames
4. **test_signup_endpoint_duplicate_email** - Prevents duplicate emails
5. **test_signup_endpoint_weak_password** - Validates password strength (accepts 400 or 422)
6. **test_signup_endpoint_invalid_email** - Validates email format
7. **test_verify_email_endpoint_success** - Verifies email with valid key
8. **test_verify_email_endpoint_invalid_key** - Rejects invalid verification keys
9. **test_verify_email_endpoint_already_verified** - Handles already-verified emails
10. **test_resend_verification_endpoint_success** - Resends verification email
11. **test_resend_verification_endpoint_already_verified** - Prevents resending to verified emails
12. **test_resend_verification_endpoint_nonexistent_email** - Security test - doesn't reveal email existence
13. **test_signup_creates_complete_organization_structure** - End-to-end test verifying full setup

## Test Results

```
============================= test session starts ==============================
platform darwin -- Python 3.14.2, pytest-8.4.2, pluggy-1.6.0 -- /Users/brian/CitrusGrove/projects/ZoeaStudio/backend/.venv/bin/python3
cachedir: .pytest_cache
django: version: 6.0b1, settings: zoeastudio.settings_test (from ini)
rootdir: /Users/brian/CitrusGrove/projects/ZoeaStudio/backend
configfile: pyproject.toml
plugins: asyncio-1.2.0, anyio-4.11.0, django-4.11.1, cov-7.0.0
asyncio: mode=Mode.AUTO, debug=False, asyncio_default_fixture_loop_scope=function, asyncio_default_test_loop_scope=function
collecting ... collected 33 items

accounts/tests.py::TestAccountModel::test_create_account PASSED          [  3%]
accounts/tests.py::TestAccountModel::test_account_str PASSED             [  6%]
accounts/tests.py::TestAccountModel::test_user_limit_methods PASSED      [  9%]
accounts/tests.py::TestOrganizationUtils::test_get_user_organization PASSED [ 12%]
accounts/tests.py::TestOrganizationUtils::test_get_user_organization_no_org PASSED [ 15%]
accounts/tests.py::TestOrganizationUtils::test_require_organization PASSED [ 18%]
accounts/tests.py::TestOrganizationUtils::test_require_organization_raises PASSED [ 21%]
accounts/tests.py::TestOrganizationUtils::test_get_user_organizations PASSED [ 24%]
accounts/tests.py::TestOrganizationUtils::test_is_organization_admin PASSED [ 27%]
accounts/tests.py::TestOrganizationUtils::test_is_organization_owner PASSED [ 30%]
accounts/tests.py::TestOrganizationUtils::test_can_add_user_to_organization PASSED [ 33%]
accounts/tests.py::TestOrganizationIsolation::test_users_see_only_their_organization PASSED [ 36%]
accounts/tests.py::TestOrganizationIsolation::test_user_cannot_be_admin_of_other_org PASSED [ 39%]
accounts/tests.py::TestInitializeUserOrganization::test_initialize_user_organization_creates_complete_setup PASSED [ 42%]
accounts/tests.py::TestInitializeUserOrganization::test_initialize_user_organization_with_custom_org_name PASSED [ 45%]
accounts/tests.py::TestInitializeUserOrganization::test_initialize_user_organization_with_custom_subscription PASSED [ 48%]
accounts/tests.py::TestInitializeUserOrganization::test_initialize_user_organization_uses_full_name_if_available PASSED [ 51%]
accounts/tests.py::TestInitializeUserOrganization::test_initialize_user_organization_rollback_on_error PASSED [ 54%]
accounts/tests.py::TestInitializeUserOrganization::test_initialize_user_organization_atomic_transaction PASSED [ 57%]
accounts/tests.py::TestInitializeUserOrganization::test_initialize_user_organization_multiple_users PASSED [ 60%]
accounts/tests.py::TestAuthAPIEndpoints::test_signup_endpoint_success PASSED [ 63%]
accounts/tests.py::TestAuthAPIEndpoints::test_signup_endpoint_password_mismatch PASSED [ 66%]
accounts/tests.py::TestAuthAPIEndpoints::test_signup_endpoint_duplicate_username PASSED [ 69%]
accounts/tests.py::TestAuthAPIEndpoints::test_signup_endpoint_duplicate_email PASSED [ 72%]
accounts/tests.py::TestAuthAPIEndpoints::test_signup_endpoint_weak_password PASSED [ 75%]
accounts/tests.py::TestAuthAPIEndpoints::test_signup_endpoint_invalid_email PASSED [ 78%]
accounts/tests.py::TestAuthAPIEndpoints::test_verify_email_endpoint_success PASSED [ 81%]
accounts/tests.py::TestAuthAPIEndpoints::test_verify_email_endpoint_invalid_key PASSED [ 84%]
accounts/tests.py::TestAuthAPIEndpoints::test_verify_email_endpoint_already_verified PASSED [ 87%]
accounts/tests.py::TestAuthAPIEndpoints::test_resend_verification_endpoint_success PASSED [ 90%]
accounts/tests.py::TestAuthAPIEndpoints::test_resend_verification_endpoint_already_verified PASSED [ 93%]
accounts/tests.py::TestAuthAPIEndpoints::test_resend_verification_endpoint_nonexistent_email PASSED [ 96%]
accounts/tests.py::TestAuthAPIEndpoints::test_signup_creates_complete_organization_structure PASSED [100%]

=============================== warnings summary ===============================
-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
======================= 33 passed, 95 warnings in 5.04s ========================
```

## Verification Steps

1. **Ran pytest test suite** - All 33 tests in accounts/tests.py pass, including 13 new API endpoint tests
2. **Verified imports** - All new schemas and API endpoints import successfully
3. **Ran Django system checks** - `python manage.py check --deploy` passed with only expected deployment warnings
4. **Tested signup flow**:
   - User registration creates user account
   - Organization, project, workspace, and clipboard created automatically
   - Email verification sent
   - EmailAddress record created but not verified
5. **Tested verification flow**:
   - Valid key confirms email
   - Invalid key returns 400 error
   - Already-verified emails handled gracefully
6. **Tested edge cases**:
   - Duplicate usernames rejected
   - Duplicate emails rejected
   - Weak passwords rejected (via Pydantic validation)
   - Invalid email formats rejected

## API Usage Examples

### 1. Sign Up New User

```bash
curl -X POST http://localhost:8000/api/auth/signup \
  -H "Content-Type: application/json" \
  -d '{
    "username": "alice",
    "email": "alice@example.com",
    "password1": "securepassword123",
    "password2": "securepassword123"
  }'
```

Response:
```json
{
  "success": true,
  "message": "Registration successful. Please check your email to verify your account.",
  "username": "alice",
  "email": "alice@example.com"
}
```

### 2. Verify Email

```bash
curl -X POST http://localhost:8000/api/auth/verify-email \
  -H "Content-Type: application/json" \
  -d '{
    "key": "abc123def456..."
  }'
```

Response:
```json
{
  "success": true,
  "message": "Email verified successfully. You can now log in."
}
```

### 3. Resend Verification Email

```bash
curl -X POST http://localhost:8000/api/auth/resend-verification \
  -H "Content-Type: application/json" \
  -d '{
    "email": "alice@example.com"
  }'
```

Response:
```json
{
  "success": true,
  "message": "Verification email sent. Please check your inbox."
}
```

## Notes

### Django-allauth Version Compatibility

This implementation is designed for django-allauth 65.x which uses internal flows rather than the deprecated utility functions. Key differences from older versions:

- `send_email_confirmation()` is no longer available
- Use `send_verification_email_to_address()` instead
- Email verification flows are in `allauth.account.internal.flows.email_verification`

### Email Configuration

In development, emails are printed to console. In production, configure SMTP settings in settings.py:

```python
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = os.getenv('EMAIL_HOST')
EMAIL_PORT = int(os.getenv('EMAIL_PORT', '587'))
EMAIL_USE_TLS = True
EMAIL_HOST_USER = os.getenv('EMAIL_HOST_USER')
EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD')
```

### Frontend Integration

The frontend should:

1. Call `/api/auth/signup` with user credentials
2. Show "Check your email" message on success
3. Provide link to resend verification if needed
4. Handle verification key from email URL (e.g., `/verify-email?key=...`)
5. Call `/api/auth/verify-email` with the key
6. Redirect to login page on successful verification

### CORS Configuration

The API endpoints use `auth=None` which allows cross-origin requests. Ensure CORS is properly configured in settings.py for your frontend domain.

### Future Enhancements

Potential improvements for future iterations:

1. Add social authentication (Google, GitHub, etc.)
2. Implement password reset API endpoints
3. Add rate limiting to prevent abuse
4. Add reCAPTCHA or similar anti-bot protection
5. Implement phone number verification
6. Add webhooks for registration events
