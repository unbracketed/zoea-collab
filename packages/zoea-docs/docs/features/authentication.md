# User Authentication and Registration

Zoea Collab provides a comprehensive authentication system with user registration, email verification, and secure login. New users are automatically set up with their own organization, project, workspace, and clipboard.

## Overview

The authentication system provides:

- **User Registration**: Create new accounts with email verification
- **Email Verification**: Mandatory email confirmation before login
- **Secure Login**: Username or email-based authentication
- **Auto-Initialization**: Automatic setup of organization, project, workspace, and clipboard for new users
- **Multi-Tenant Isolation**: Each user gets their own isolated organization

## Quick Start

### Registering a New Account

1. Navigate to the registration page (click "Sign up" from the login page)
2. Fill in the registration form:
   - Username (minimum 3 characters)
   - Email address
   - Password (minimum 8 characters)
   - Confirm password
3. Click "Sign Up"
4. Check your email for a verification link
5. Click the verification link in your email
6. You can now log in with your credentials

### Logging In

1. Navigate to the login page
2. Enter your username or email
3. Enter your password
4. Click "Log In"

## Registration Process Details

### What Happens When You Register

When you create a new account, Zoea Collab automatically:

1. **Creates your user account** with your chosen username and email
2. **Sends a verification email** to confirm your email address
3. **Creates an organization** named "{username}'s Organization"
4. **Sets you as the organization owner** with full administrative privileges
5. **Creates a default project** for your organization
6. **Creates a default workspace** within that project
7. **Creates a default clipboard** for managing content

All of this happens automatically - you don't need to do anything except verify your email.

### Email Verification

Email verification is **mandatory** in Zoea Collab. This ensures that:

- You have access to the email address you provided
- You can receive important notifications about your account
- Your account is secure and verified

**Verification Link Expiration**: Email verification links expire after 3 days. If your link expires, you can request a new one.

### Resending Verification Email

If you didn't receive the verification email or it expired:

1. On the login page, look for the "Resend verification email" option
2. Enter your email address
3. Check your inbox for a new verification email

Or use the API directly:

```bash
curl -X POST http://localhost:8000/api/auth/resend-verification \
  -H "Content-Type: application/json" \
  -d '{"email":"your-email@example.com"}'
```

## API Endpoints

Zoea Collab provides REST API endpoints for authentication operations.

### Check Authentication Status

**Endpoint**: `GET /api/auth/check`

**Authentication**: Not required

**Description**: Check if the current session is authenticated and get user information.

**Response**:
```json
{
  "authenticated": true,
  "username": "alice",
  "organization": "Alice's Organization"
}
```

**Example**:
```bash
curl http://localhost:8000/api/auth/check
```

### Register a New User

**Endpoint**: `POST /api/auth/signup`

**Authentication**: Not required

**Request Body**:
```json
{
  "username": "alice",
  "email": "alice@example.com",
  "password1": "SecurePassword123",
  "password2": "SecurePassword123"
}
```

**Response**:
```json
{
  "success": true,
  "message": "Registration successful. Please check your email to verify your account.",
  "username": "alice",
  "email": "alice@example.com"
}
```

**Validation Rules**:
- Username: 1-150 characters, unique
- Email: Valid email format, unique
- Password: Minimum 8 characters, must match confirmation

**Example**:
```bash
curl -X POST http://localhost:8000/api/auth/signup \
  -H "Content-Type: application/json" \
  -d '{
    "username": "alice",
    "email": "alice@example.com",
    "password1": "SecurePassword123",
    "password2": "SecurePassword123"
  }'
```

### Verify Email Address

**Endpoint**: `POST /api/auth/verify-email`

**Authentication**: Not required

**Request Body**:
```json
{
  "key": "abc123def456..."
}
```

**Response**:
```json
{
  "success": true,
  "message": "Email verified successfully. You can now log in."
}
```

**Example**:
```bash
curl -X POST http://localhost:8000/api/auth/verify-email \
  -H "Content-Type: application/json" \
  -d '{"key":"abc123def456..."}'
```

### Resend Verification Email

**Endpoint**: `POST /api/auth/resend-verification`

**Authentication**: Not required

**Request Body**:
```json
{
  "email": "alice@example.com"
}
```

**Response**:
```json
{
  "success": true,
  "message": "Verification email sent. Please check your inbox."
}
```

**Example**:
```bash
curl -X POST http://localhost:8000/api/auth/resend-verification \
  -H "Content-Type: application/json" \
  -d '{"email":"alice@example.com"}'
```

### Log In

**Endpoint**: `POST /api/auth/login`

**Authentication**: Not required

**Request Body**:
```json
{
  "username": "alice",
  "password": "SecurePassword123"
}
```

**Response**:
```json
{
  "success": true,
  "message": "Login successful",
  "username": "alice"
}
```

**Example**:
```bash
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "username": "alice",
    "password": "SecurePassword123"
  }'
```

### Log Out

**Endpoint**: `POST /api/auth/logout`

**Authentication**: Required

**Response**:
```json
{
  "success": true,
  "message": "Logout successful"
}
```

**Example**:
```bash
curl -X POST http://localhost:8000/api/auth/logout \
  -H "Cookie: sessionid=your-session-id"
```

## Command-Line Interface

Zoea Collab provides a CLI command for creating users, useful for development, testing, and administrative tasks.

### Create User via CLI

**Command**: `zoea users create`

**Options**:
- `--username, -u`: Username for the new user
- `--email, -e`: Email address
- `--password, -p`: Password
- `--org-name, -o`: Custom organization name (defaults to "{username}'s Organization")
- `--subscription, -s`: Subscription plan (free, pro, enterprise) - default: free
- `--max-users, -m`: Maximum users in organization - default: 5
- `--skip-email-verification`: Mark email as verified immediately (for development)
- `--force`: Skip confirmation prompts (non-interactive mode)
- `--format, -f`: Output format (table or json)

### Interactive Mode

Run without options to be prompted for each field:

```bash
zoea users create
```

You'll be prompted for:
- Username
- Email
- Password (hidden input)
- Password confirmation

### Non-Interactive Mode

Provide all options via command line:

```bash
zoea users create \
  --username alice \
  --email alice@example.com \
  --password SecurePass123 \
  --org-name "Alice's Company" \
  --subscription pro \
  --max-users 10 \
  --skip-email-verification \
  --force
```

### Development Quick Start

For quick development setup:

```bash
zoea users create \
  --username dev \
  --email dev@localhost \
  --password dev \
  --skip-email-verification \
  --force
```

### JSON Output

Get structured output for scripting:

```bash
zoea users create \
  --username alice \
  --email alice@example.com \
  --password SecurePass123 \
  --skip-email-verification \
  --force \
  --format json | jq .
```

**Output**:
```json
{
  "user": {
    "id": 1,
    "username": "alice",
    "email": "alice@example.com",
    "email_verified": true
  },
  "organization": {
    "id": 1,
    "name": "Alice's Company",
    "slug": "alices-company",
    "subscription_plan": "pro",
    "max_users": 10
  },
  "project": {
    "id": 1,
    "name": "Alice's Company - Default Project",
    "working_directory": "/path/to/projects/alices-company/demo-docs"
  },
  "workspace": {
    "id": 1,
    "name": "Alice's Company Workspace"
  },
  "clipboard": {
    "id": 1,
    "name": "Alice's Company Workspace Clipboard"
  }
}
```

## Troubleshooting

### I didn't receive the verification email

**Possible causes**:

1. **Email is in spam folder**: Check your spam/junk folder
2. **Email service is slow**: Wait a few minutes and check again
3. **Wrong email address**: Make sure you entered the correct email

**Solutions**:

- Use the "Resend verification email" feature
- Check your email provider's spam settings
- Try a different email address if the current one is incorrect

### My verification link expired

Verification links expire after 3 days for security reasons.

**Solution**: Request a new verification email using the resend endpoint or the resend feature in the UI.

### I can't log in even after verifying my email

**Possible causes**:

1. **Email not actually verified**: Check that you clicked the verification link
2. **Wrong password**: Make sure you're entering the correct password
3. **Wrong username**: Try using your email address to log in instead

**Solutions**:

- Try logging in with your email instead of username
- Use the password reset feature if you forgot your password
- Check the verification status via the admin panel

### I get "User already exists" error

**Cause**: The username or email is already registered.

**Solutions**:

- Choose a different username
- Use a different email address
- If you already have an account, use the login page instead
- Contact an administrator if you believe this is an error

### Development: Email backend not configured

In development, Zoea Collab uses the console email backend, which prints emails to the server console instead of sending them.

**To see verification emails in development**:

1. Check the terminal where you ran `mise run dev-backend`
2. Look for email output starting with "Subject:" and "From:"
3. Copy the verification URL from the console output
4. Navigate to that URL in your browser

## Security Considerations

### Password Requirements

- Minimum 8 characters
- Must match confirmation
- Django's built-in password validation applies (checks for common passwords, similarity to username, etc.)

### Email Verification

- Mandatory for all new users
- Links expire after 3 days
- Only one verification email per user at a time
- Already-verified emails cannot be re-verified

### Session Security

- Sessions are HTTP-only cookies
- CSRF protection on all state-changing operations
- Logout requires POST request (not GET) to prevent CSRF attacks

### Data Privacy

- Passwords are hashed using Django's default PBKDF2 algorithm
- Email addresses are unique and validated
- No user information is leaked in error messages (e.g., "Invalid credentials" instead of "User not found")

## Next Steps

After registering and logging in:

1. **Explore your workspace**: Navigate to your default workspace
2. **Create documents**: Start creating documents in your project
3. **Invite team members**: Add users to your organization (subscription permitting)
4. **Configure settings**: Customize your organization and project settings

## Related Documentation

- [Multi-Tenant Architecture](../architecture/multi-tenant.md) - Learn about organizations and isolation
- [CLI Reference](cli.md) - Complete CLI command documentation
- [Development Guide](../development/authentication-setup.md) - For developers implementing authentication
