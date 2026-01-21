"""
Django Ninja API for authentication endpoints.
"""

import logging
from asgiref.sync import sync_to_async
from django.contrib.auth import authenticate, login, logout, get_user_model
from django.db import transaction
from ninja import Router
from ninja.errors import HttpError
from allauth.account.forms import SignupForm
from allauth.account.models import EmailAddress, EmailConfirmation, EmailConfirmationHMAC
from allauth.account.internal.flows.email_verification import (
    send_verification_email_to_address,
    get_address_for_user,
)

from .schemas import (
    AuthCheckResponse,
    LoginRequest,
    LoginResponse,
    LogoutResponse,
    SignupRequest,
    SignupResponse,
    VerifyEmailRequest,
    VerifyEmailResponse,
    ResendVerificationRequest,
    ResendVerificationResponse,
)
from .utils import aget_user_organization

router = Router()
logger = logging.getLogger(__name__)
User = get_user_model()


@router.post("/login", response=LoginResponse, auth=None)
async def auth_login(request, payload: LoginRequest):
    """
    Authenticate user and create session.

    Args:
        request: Django request object
        payload: Login credentials

    Returns:
        Login response with success status and username

    Raises:
        HttpError: If credentials are invalid
    """
    # Authenticate user (sync operation)
    @sync_to_async
    def _authenticate_and_login():
        user = authenticate(
            request, username=payload.username, password=payload.password
        )
        if user is not None:
            login(request, user)
            logger.info(f"User '{user.username}' logged in successfully")
            return user
        return None

    user = await _authenticate_and_login()

    if user is None:
        logger.warning(f"Failed login attempt for username '{payload.username}'")
        raise HttpError(401, "Invalid username or password")

    return LoginResponse(
        success=True, message="Login successful", username=user.username
    )


@router.post("/logout", response=LogoutResponse)
async def auth_logout(request):
    """
    Log out the current user and destroy session.

    Args:
        request: Django request object

    Returns:
        Logout response with success status
    """
    username = request.user.username if request.user.is_authenticated else "unknown"

    @sync_to_async
    def _logout():
        logout(request)

    await _logout()

    logger.info(f"User '{username}' logged out")

    return LogoutResponse(success=True, message="Logout successful")


@router.get("/check", response=AuthCheckResponse, auth=None)
async def auth_check(request):
    """
    Check if user is authenticated and return user info.

    This endpoint does not require authentication - it returns
    authentication status and user information if available.

    Args:
        request: Django request object

    Returns:
        Authentication status and user information
    """
    # Wrap user authentication check in sync_to_async
    @sync_to_async
    def _check_auth():
        return request.user.is_authenticated

    @sync_to_async
    def _get_username():
        return request.user.username

    is_authenticated = await _check_auth()

    if not is_authenticated:
        return AuthCheckResponse(authenticated=False, username=None, organization=None)

    # Get username
    username = await _get_username()

    # Get organization info (async)
    organization = await aget_user_organization(request.user)
    org_name = None
    if organization:
        @sync_to_async
        def _get_org_name():
            return organization.name

        org_name = await _get_org_name()

    return AuthCheckResponse(
        authenticated=True, username=username, organization=org_name
    )


@router.post("/signup", response=SignupResponse, auth=None)
async def auth_signup(request, payload: SignupRequest):
    """
    Register a new user account.

    Creates a new user with email verification. The user must verify their email
    before they can log in. An organization with default project and workspace
    is automatically created via the custom AccountAdapter.

    Args:
        request: Django request object
        payload: Signup credentials (username, email, password1, password2)

    Returns:
        Signup response with success status and user info

    Raises:
        HttpError: If validation fails or user already exists
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

        # Create and validate the signup form
        form = SignupForm(data=form_data)

        if not form.is_valid():
            # Extract error messages from form
            errors = []
            for field, field_errors in form.errors.items():
                for error in field_errors:
                    errors.append(f"{field}: {error}")
            error_message = "; ".join(errors)
            raise HttpError(400, error_message)

        # Save the user (this will trigger our custom adapter)
        # The adapter automatically creates organization/project/workspace
        with transaction.atomic():
            try:
                user = form.save(request)
            except ValueError as e:
                # form.save() raises ValueError for duplicate emails
                error_msg = str(e)
                if '@' in error_msg:  # It's an email address
                    raise HttpError(400, f"email: A user with this email already exists.")
                raise HttpError(400, str(e))

            # Send email verification
            # Get the email address object for the user
            email_address = get_address_for_user(user)
            if email_address:
                send_verification_email_to_address(request, email_address, signup=True)

            logger.info(
                f"New user registered: '{user.username}' ({user.email}). "
                f"Verification email sent."
            )

            return user

    try:
        user = await _create_user()

        return SignupResponse(
            success=True,
            message="Registration successful. Please check your email to verify your account.",
            username=user.username,
            email=user.email,
        )

    except HttpError:
        # Re-raise validation errors
        raise
    except Exception as e:
        logger.error(f"Signup failed: {str(e)}", exc_info=True)
        raise HttpError(500, "Registration failed. Please try again.")


@router.post("/verify-email", response=VerifyEmailResponse, auth=None)
async def verify_email(request, payload: VerifyEmailRequest):
    """
    Verify user's email address with confirmation key.

    Args:
        request: Django request object
        payload: Verification key from email

    Returns:
        Verification response with success status

    Raises:
        HttpError: If key is invalid or expired
    """

    @sync_to_async
    def _verify_email():
        try:
            # Try to get email confirmation by key
            email_confirmation = EmailConfirmation.objects.get(key=payload.key.lower())

            # Check if already confirmed
            email_address = email_confirmation.email_address
            if email_address.verified:
                return {
                    'success': True,
                    'message': 'Email address already verified.',
                    'user': email_address.user,
                }

            # Confirm the email
            email_confirmation.confirm(request)

            logger.info(
                f"Email verified for user '{email_address.user.username}' "
                f"({email_address.email})"
            )

            return {
                'success': True,
                'message': 'Email verified successfully. You can now log in.',
                'user': email_address.user,
            }

        except EmailConfirmation.DoesNotExist:
            # Try HMAC-based confirmation (doesn't expire)
            try:
                emailconfirmation = EmailConfirmationHMAC.from_key(payload.key)
                if emailconfirmation:
                    email_address = emailconfirmation.email_address
                    if email_address.verified:
                        return {
                            'success': True,
                            'message': 'Email address already verified.',
                            'user': email_address.user,
                        }

                    emailconfirmation.confirm(request)

                    logger.info(
                        f"Email verified (HMAC) for user '{email_address.user.username}' "
                        f"({email_address.email})"
                    )

                    return {
                        'success': True,
                        'message': 'Email verified successfully. You can now log in.',
                        'user': email_address.user,
                    }
                else:
                    raise HttpError(400, "Invalid or expired verification key.")

            except Exception:
                raise HttpError(400, "Invalid or expired verification key.")

    try:
        result = await _verify_email()
        return VerifyEmailResponse(
            success=result['success'],
            message=result['message'],
        )

    except HttpError:
        raise
    except Exception as e:
        logger.error(f"Email verification failed: {str(e)}", exc_info=True)
        raise HttpError(500, "Email verification failed. Please try again.")


@router.post("/resend-verification", response=ResendVerificationResponse, auth=None)
async def resend_verification(request, payload: ResendVerificationRequest):
    """
    Resend email verification to a user.

    Args:
        request: Django request object
        payload: Email address to resend verification to

    Returns:
        Response indicating email was sent

    Raises:
        HttpError: If user not found or email already verified
    """

    @sync_to_async
    def _resend_verification():
        try:
            # Find user by email
            user = User.objects.get(email=payload.email)

            # Check if email is already verified
            try:
                email_address = EmailAddress.objects.get(
                    user=user, email=payload.email
                )
                if email_address.verified:
                    raise HttpError(
                        400,
                        "Email address is already verified. You can log in.",
                    )
            except EmailAddress.DoesNotExist:
                # Email address record doesn't exist yet, that's okay
                pass

            # Send verification email
            # Get the email address object for the user
            email_address = get_address_for_user(user)
            if email_address:
                send_verification_email_to_address(request, email_address, signup=False)

            logger.info(
                f"Verification email resent to user '{user.username}' ({payload.email})"
            )

            return True

        except User.DoesNotExist:
            # Don't reveal whether email exists for security
            # Return success but log the attempt
            logger.warning(
                f"Verification email requested for non-existent email: {payload.email}"
            )
            return True

    try:
        await _resend_verification()

        return ResendVerificationResponse(
            success=True,
            message="Verification email sent. Please check your inbox.",
        )

    except HttpError:
        raise
    except Exception as e:
        logger.error(f"Failed to resend verification: {str(e)}", exc_info=True)
        raise HttpError(500, "Failed to send verification email. Please try again.")
