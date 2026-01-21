"""
Pydantic schemas for authentication API.
"""

from typing import Optional
from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    """Request schema for user login."""

    username: str = Field(..., min_length=1, description="Username")
    password: str = Field(..., min_length=1, description="Password")


class LoginResponse(BaseModel):
    """Response schema for successful login."""

    success: bool = Field(..., description="Whether login was successful")
    message: str = Field(..., description="Response message")
    username: Optional[str] = Field(None, description="Username of logged-in user")


class LogoutResponse(BaseModel):
    """Response schema for logout."""

    success: bool = Field(..., description="Whether logout was successful")
    message: str = Field(..., description="Response message")


class AuthCheckResponse(BaseModel):
    """Response schema for authentication check."""

    authenticated: bool = Field(..., description="Whether user is authenticated")
    username: Optional[str] = Field(None, description="Username if authenticated")
    organization: Optional[str] = Field(None, description="Organization name if available")


class SignupRequest(BaseModel):
    """Request schema for user registration."""

    username: str = Field(..., min_length=1, max_length=150, description="Username")
    email: str = Field(..., description="Email address")
    password1: str = Field(..., min_length=8, description="Password")
    password2: str = Field(..., min_length=8, description="Password confirmation")


class SignupResponse(BaseModel):
    """Response schema for successful registration."""

    success: bool = Field(..., description="Whether signup was successful")
    message: str = Field(..., description="Response message")
    username: str = Field(..., description="Username of registered user")
    email: str = Field(..., description="Email address")


class VerifyEmailRequest(BaseModel):
    """Request schema for email verification."""

    key: str = Field(..., min_length=1, description="Email verification key/token")


class VerifyEmailResponse(BaseModel):
    """Response schema for email verification."""

    success: bool = Field(..., description="Whether verification was successful")
    message: str = Field(..., description="Response message")


class ResendVerificationRequest(BaseModel):
    """Request schema for resending verification email."""

    email: str = Field(..., description="Email address to resend verification to")


class ResendVerificationResponse(BaseModel):
    """Response schema for resending verification email."""

    success: bool = Field(..., description="Whether email was sent")
    message: str = Field(..., description="Response message")
