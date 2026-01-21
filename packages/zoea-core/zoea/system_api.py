"""
System settings API endpoints.

Exposes non-sensitive system configuration to the frontend.
"""

from django.conf import settings
from django.db import connection
from ninja import Router
from pydantic import BaseModel, Field

router = Router()


class HealthResponse(BaseModel):
    """Health check response."""

    status: str = Field(..., description="Service health status")
    database: str = Field(..., description="Database connection status")


class SystemSettingsResponse(BaseModel):
    """Public system settings exposed to the frontend."""

    default_theme: str = Field(..., description="Default color theme for projects")


@router.get("/health", response=HealthResponse, tags=["system"])
def health_check(request):
    """
    Health check endpoint for Render.com and load balancers.

    Verifies the service is running and can connect to the database.
    """
    db_status = "ok"
    try:
        connection.ensure_connection()
    except Exception:
        db_status = "error"

    return HealthResponse(status="ok", database=db_status)


@router.get("/settings", response=SystemSettingsResponse)
async def get_system_settings(request):
    """
    Get public system settings.

    Returns non-sensitive configuration values that the frontend
    needs for proper initialization.
    """
    return SystemSettingsResponse(
        default_theme=getattr(settings, 'ZOEA_DEFAULT_THEME', 'ocean')
    )
