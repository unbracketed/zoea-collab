"""
LLM configuration resolution.

Resolves LLM settings using hierarchy: Agent/Workflow → Project → App defaults.
"""

import logging
from typing import TYPE_CHECKING, Any

from django.conf import settings

from .types import LLMConfig

if TYPE_CHECKING:
    from projects.models import Project

logger = logging.getLogger(__name__)


def resolve_llm_config(
    project: "Project | None" = None,
    agent_config: dict[str, Any] | None = None,
) -> LLMConfig:
    """
    Resolve LLM configuration from the configuration hierarchy.

    Resolution order (first wins):
    1. Agent/Workflow config (per-conversation or per-agent override)
    2. Project config (project-level settings)
    3. App defaults (Django settings)

    Args:
        project: Optional project for project-level config lookup.
        agent_config: Optional agent-level configuration dict with keys:
            - provider: Provider name
            - model: Model ID
            - api_key: API key override
            - endpoint: Custom endpoint (for local models)
            - temperature: Temperature setting
            - max_tokens: Max output tokens

    Returns:
        LLMConfig with resolved settings.

    Example:
        # Agent-level override
        config = resolve_llm_config(project, {"provider": "ollama", "model": "llama3"})

        # Project defaults
        config = resolve_llm_config(project)

        # App defaults only
        config = resolve_llm_config()
    """
    # Start with app defaults
    provider = getattr(settings, "DEFAULT_LLM_PROVIDER", "openai")
    model_id = getattr(settings, "DEFAULT_LLM_MODEL", "gpt-4o-mini")
    api_key = None
    endpoint = None
    temperature = 0.7
    max_tokens = None
    extra_params: dict[str, Any] = {}

    # Layer 2: Project config (if available)
    if project is not None:
        # Check for project-level LLM settings
        if hasattr(project, "llm_provider") and project.llm_provider:
            provider = project.llm_provider
        if hasattr(project, "llm_model_id") and project.llm_model_id:
            model_id = project.llm_model_id

        # Project-level API keys
        if provider == "openai" and hasattr(project, "openai_api_key"):
            api_key = project.openai_api_key
        elif provider == "gemini" and hasattr(project, "gemini_api_key"):
            api_key = project.gemini_api_key

        # Local model endpoint
        if hasattr(project, "local_model_endpoint") and project.local_model_endpoint:
            endpoint = project.local_model_endpoint

    # Layer 1: Agent config (highest priority)
    if agent_config:
        if agent_config.get("provider"):
            provider = agent_config["provider"]
        if agent_config.get("model"):
            model_id = agent_config["model"]
        if agent_config.get("api_key"):
            api_key = agent_config["api_key"]
        if agent_config.get("endpoint"):
            endpoint = agent_config["endpoint"]
        if agent_config.get("temperature") is not None:
            temperature = agent_config["temperature"]
        if agent_config.get("max_tokens"):
            max_tokens = agent_config["max_tokens"]

        # Pass through any extra params
        for key in agent_config:
            if key not in {"provider", "model", "api_key", "endpoint", "temperature", "max_tokens"}:
                extra_params[key] = agent_config[key]

    # Fall back to app-level API keys if not set at project/agent level
    if not api_key:
        if provider == "openai":
            api_key = getattr(settings, "OPENAI_API_KEY", None)
        elif provider == "gemini":
            api_key = getattr(settings, "GEMINI_API_KEY", None)

    # Fall back to app-level endpoint for local models
    if not endpoint and provider in ("ollama", "local", "lmstudio"):
        endpoint = getattr(settings, "LOCAL_MODEL_ENDPOINT", "http://localhost:11434")

    return LLMConfig(
        provider=provider,
        model_id=model_id,
        api_key=api_key,
        endpoint=endpoint,
        temperature=temperature,
        max_tokens=max_tokens,
        extra_params=extra_params,
    )


def get_provider_api_key(provider: str, project: "Project | None" = None) -> str | None:
    """
    Get API key for a specific provider.

    Args:
        provider: Provider name.
        project: Optional project for project-level key lookup.

    Returns:
        API key if found, None otherwise.
    """
    # Check project-level first
    if project is not None:
        if provider == "openai" and hasattr(project, "openai_api_key"):
            if project.openai_api_key:
                return project.openai_api_key
        elif provider == "gemini" and hasattr(project, "gemini_api_key"):
            if project.gemini_api_key:
                return project.gemini_api_key

    # Fall back to app-level
    if provider == "openai":
        return getattr(settings, "OPENAI_API_KEY", None)
    elif provider == "gemini":
        return getattr(settings, "GEMINI_API_KEY", None)

    return None
