"""
LLM Provider Interface - Unified interface for LLM backends.

This module provides an abstraction layer for LLM operations, allowing
different providers (OpenAI, Gemini, local models, etc.) to be used
interchangeably through a common interface.

Example usage:
    from llm_providers import LLMProviderRegistry, resolve_llm_config, ChatMessage

    # Get configured provider
    config = resolve_llm_config(project)
    provider = LLMProviderRegistry.get(config.provider, config=config)

    # Chat
    messages = [
        ChatMessage(role="system", content="You are a helpful assistant."),
        ChatMessage(role="user", content="Hello!"),
    ]
    response = await provider.chat_async(messages)
    print(response.content)

    # List available models
    for model in provider.list_models():
        print(f"{model.model_id}: {model.display_name}")
"""

from .base import LLMProvider
from .config import get_provider_api_key, resolve_llm_config
from .exceptions import (
    APIError,
    AuthenticationError,
    ConfigurationError,
    LLMProviderError,
    ModelNotFoundError,
    ProviderNotFoundError,
    RateLimitError,
    StreamingError,
)
from .registry import LLMProviderRegistry
from .types import (
    ChatMessage,
    ChatResponse,
    LLMConfig,
    MessageRole,
    ModelInfo,
    ProviderInfo,
    StreamChunk,
)

# Import providers to trigger registration
from . import providers  # noqa: F401

__all__ = [
    # Core classes
    "LLMProvider",
    "LLMProviderRegistry",
    # Config
    "resolve_llm_config",
    "get_provider_api_key",
    # Types
    "ChatMessage",
    "ChatResponse",
    "LLMConfig",
    "MessageRole",
    "ModelInfo",
    "ProviderInfo",
    "StreamChunk",
    # Exceptions
    "LLMProviderError",
    "ProviderNotFoundError",
    "ModelNotFoundError",
    "AuthenticationError",
    "RateLimitError",
    "APIError",
    "ConfigurationError",
    "StreamingError",
]
