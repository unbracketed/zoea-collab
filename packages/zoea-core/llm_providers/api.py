"""
Django Ninja API for LLM provider endpoints.
"""

from typing import Optional

from asgiref.sync import sync_to_async
from django.conf import settings
from ninja import Router, Schema
from ninja.errors import HttpError

from accounts.utils import aget_user_organization
from projects.models import Project

from .exceptions import ProviderNotFoundError
from .registry import LLMProviderRegistry

router = Router()


# -------------------------------------------------------------------------
# Schemas
# -------------------------------------------------------------------------


class ModelInfoSchema(Schema):
    """Information about a model."""

    model_id: str
    display_name: str
    provider: str
    description: Optional[str] = None
    context_window: Optional[int] = None
    max_output_tokens: Optional[int] = None
    supports_vision: bool = False
    supports_tools: bool = False
    supports_streaming: bool = True


class ProviderInfoSchema(Schema):
    """Information about a provider."""

    name: str
    display_name: str
    requires_api_key: bool = True
    supports_custom_endpoint: bool = False


class ProviderListResponse(Schema):
    """Response for listing providers."""

    providers: list[ProviderInfoSchema]
    default_provider: Optional[str] = None


class ModelsListResponse(Schema):
    """Response for listing models."""

    models: list[ModelInfoSchema]
    provider: str


class ValidateCredentialsRequest(Schema):
    """Request to validate credentials."""

    provider: str
    api_key: str


class ValidateCredentialsResponse(Schema):
    """Response for credential validation."""

    valid: bool
    provider: str
    error: Optional[str] = None


class ProjectLLMConfigRequest(Schema):
    """Request to update project LLM configuration."""

    llm_provider: Optional[str] = None
    llm_model_id: Optional[str] = None
    openai_api_key: Optional[str] = None
    gemini_api_key: Optional[str] = None
    local_model_endpoint: Optional[str] = None


class ProjectLLMConfigResponse(Schema):
    """Response with project LLM configuration."""

    project_id: int
    llm_provider: Optional[str] = None
    llm_model_id: Optional[str] = None
    has_openai_key: bool = False
    has_gemini_key: bool = False
    local_model_endpoint: Optional[str] = None
    effective_provider: str
    effective_model: str


# -------------------------------------------------------------------------
# Endpoints
# -------------------------------------------------------------------------


@router.get("/providers", response=ProviderListResponse)
async def list_providers(request):
    """
    List all registered LLM providers.

    Returns:
        List of provider info with default provider indicated.
    """
    providers = []

    for name in LLMProviderRegistry.list_providers():
        try:
            provider = LLMProviderRegistry.get(name)
            info = provider.get_info()
            providers.append(
                ProviderInfoSchema(
                    name=info.name,
                    display_name=info.display_name,
                    requires_api_key=info.requires_api_key,
                    supports_custom_endpoint=info.supports_custom_endpoint,
                )
            )
        except Exception:
            continue

    return ProviderListResponse(
        providers=providers,
        default_provider=LLMProviderRegistry.get_default(),
    )


@router.get("/providers/{provider_name}/models", response=ModelsListResponse)
async def list_provider_models(request, provider_name: str):
    """
    List available models for a specific provider.

    Args:
        provider_name: The provider to list models for.

    Returns:
        List of model info.
    """
    try:
        provider = LLMProviderRegistry.get(provider_name)
    except ProviderNotFoundError:
        raise HttpError(404, f"Provider '{provider_name}' not found")

    models = []
    for model in provider.list_models():
        models.append(
            ModelInfoSchema(
                model_id=model.model_id,
                display_name=model.display_name,
                provider=model.provider,
                description=model.description,
                context_window=model.context_window,
                max_output_tokens=model.max_output_tokens,
                supports_vision=model.supports_vision,
                supports_tools=model.supports_tools,
                supports_streaming=model.supports_streaming,
            )
        )

    return ModelsListResponse(models=models, provider=provider_name)


@router.post("/validate", response=ValidateCredentialsResponse)
async def validate_credentials(request, payload: ValidateCredentialsRequest):
    """
    Validate API credentials for a provider.

    Args:
        payload: Provider name and API key to validate.

    Returns:
        Validation result.
    """
    try:
        provider = LLMProviderRegistry.get(payload.provider)
    except ProviderNotFoundError:
        raise HttpError(404, f"Provider '{payload.provider}' not found")

    try:
        valid = provider.validate_credentials(payload.api_key)
        return ValidateCredentialsResponse(
            valid=valid,
            provider=payload.provider,
            error=None if valid else "Invalid API key",
        )
    except Exception as e:
        return ValidateCredentialsResponse(
            valid=False,
            provider=payload.provider,
            error=str(e),
        )


@router.get("/projects/{project_id}/llm-config", response=ProjectLLMConfigResponse)
async def get_project_llm_config(request, project_id: int):
    """
    Get LLM configuration for a project.

    Args:
        project_id: The project ID.

    Returns:
        Project LLM configuration with effective values.
    """
    organization = await aget_user_organization(request.user)
    if not organization:
        raise HttpError(403, "User is not associated with any organization")

    @sync_to_async
    def _get_project():
        try:
            return Project.objects.get(id=project_id, organization=organization)
        except Project.DoesNotExist:
            return None

    project = await _get_project()
    if not project:
        raise HttpError(404, "Project not found")

    # Calculate effective values
    effective_provider = project.llm_provider or getattr(
        settings, "DEFAULT_LLM_PROVIDER", "openai"
    )
    effective_model = project.llm_model_id or getattr(
        settings, "DEFAULT_LLM_MODEL", "gpt-4o-mini"
    )

    return ProjectLLMConfigResponse(
        project_id=project.id,
        llm_provider=project.llm_provider,
        llm_model_id=project.llm_model_id,
        has_openai_key=bool(project.openai_api_key),
        has_gemini_key=bool(project.gemini_api_key),
        local_model_endpoint=project.local_model_endpoint,
        effective_provider=effective_provider,
        effective_model=effective_model,
    )


@router.patch("/projects/{project_id}/llm-config", response=ProjectLLMConfigResponse)
async def update_project_llm_config(
    request, project_id: int, payload: ProjectLLMConfigRequest
):
    """
    Update LLM configuration for a project.

    Args:
        project_id: The project ID.
        payload: LLM configuration to update.

    Returns:
        Updated project LLM configuration.
    """
    organization = await aget_user_organization(request.user)
    if not organization:
        raise HttpError(403, "User is not associated with any organization")

    @sync_to_async
    def _update_project():
        try:
            project = Project.objects.get(id=project_id, organization=organization)
        except Project.DoesNotExist:
            return None

        # Update only provided fields
        update_fields = []

        if payload.llm_provider is not None:
            # Validate provider exists
            if payload.llm_provider and not LLMProviderRegistry.is_registered(
                payload.llm_provider
            ):
                raise ValueError(f"Unknown provider: {payload.llm_provider}")
            project.llm_provider = payload.llm_provider or None
            update_fields.append("llm_provider")

        if payload.llm_model_id is not None:
            project.llm_model_id = payload.llm_model_id or None
            update_fields.append("llm_model_id")

        if payload.openai_api_key is not None:
            project.openai_api_key = payload.openai_api_key or None
            update_fields.append("openai_api_key")

        if payload.gemini_api_key is not None:
            project.gemini_api_key = payload.gemini_api_key or None
            update_fields.append("gemini_api_key")

        if payload.local_model_endpoint is not None:
            project.local_model_endpoint = payload.local_model_endpoint or None
            update_fields.append("local_model_endpoint")

        if update_fields:
            project.save(update_fields=update_fields)

        return project

    try:
        project = await _update_project()
    except ValueError as e:
        raise HttpError(400, str(e))

    if not project:
        raise HttpError(404, "Project not found")

    # Calculate effective values
    effective_provider = project.llm_provider or getattr(
        settings, "DEFAULT_LLM_PROVIDER", "openai"
    )
    effective_model = project.llm_model_id or getattr(
        settings, "DEFAULT_LLM_MODEL", "gpt-4o-mini"
    )

    return ProjectLLMConfigResponse(
        project_id=project.id,
        llm_provider=project.llm_provider,
        llm_model_id=project.llm_model_id,
        has_openai_key=bool(project.openai_api_key),
        has_gemini_key=bool(project.gemini_api_key),
        local_model_endpoint=project.local_model_endpoint,
        effective_provider=effective_provider,
        effective_model=effective_model,
    )
