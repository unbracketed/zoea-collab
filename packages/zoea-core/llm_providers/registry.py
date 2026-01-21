"""
Registry for LLM provider implementations.
"""

import logging
from typing import Callable

from .base import LLMProvider
from .exceptions import ProviderNotFoundError
from .types import LLMConfig

logger = logging.getLogger(__name__)


class LLMProviderRegistry:
    """
    Registry for LLM provider implementations.

    Providers register themselves when their module is imported,
    allowing dynamic discovery and configuration-based selection.

    Example:
        # Registration (typically in provider module)
        LLMProviderRegistry.register("openai", OpenAIProvider)

        # Usage
        provider = LLMProviderRegistry.get("openai", config=my_config)
        response = provider.chat(messages)
    """

    _providers: dict[str, type[LLMProvider]] = {}
    _factories: dict[str, Callable[[LLMConfig | None], LLMProvider]] = {}
    _default: str | None = None

    @classmethod
    def register(
        cls,
        name: str,
        provider_class: type[LLMProvider],
        *,
        set_default: bool = False,
        factory: Callable[[LLMConfig | None], LLMProvider] | None = None,
    ) -> None:
        """
        Register a provider implementation.

        Args:
            name: Provider identifier (e.g., 'openai', 'gemini').
            provider_class: The provider class.
            set_default: If True, set this as the default provider.
            factory: Optional custom factory function for creating instances.
        """
        cls._providers[name] = provider_class
        if factory:
            cls._factories[name] = factory

        if set_default or cls._default is None:
            cls._default = name

        logger.debug(f"Registered LLM provider: {name}")

    @classmethod
    def get(
        cls,
        name: str | None = None,
        config: LLMConfig | None = None,
    ) -> LLMProvider:
        """
        Get a provider instance by name.

        Args:
            name: Provider name. If None, uses the default provider.
            config: Optional configuration for the provider.

        Returns:
            An initialized provider instance.

        Raises:
            ProviderNotFoundError: If the provider is not registered.
        """
        name = name or cls._default

        if not name:
            raise ProviderNotFoundError("No provider specified and no default set")

        if name not in cls._providers:
            available = ", ".join(cls._providers.keys())
            raise ProviderNotFoundError(
                f"Provider '{name}' not found. Available: {available}"
            )

        # Use custom factory if provided
        if name in cls._factories:
            return cls._factories[name](config)

        # Otherwise instantiate the class directly
        return cls._providers[name](config)

    @classmethod
    def list_providers(cls) -> list[str]:
        """Return list of registered provider names."""
        return list(cls._providers.keys())

    @classmethod
    def get_default(cls) -> str | None:
        """Return the default provider name."""
        return cls._default

    @classmethod
    def set_default(cls, name: str) -> None:
        """
        Set the default provider.

        Args:
            name: Provider name to set as default.

        Raises:
            ProviderNotFoundError: If the provider is not registered.
        """
        if name not in cls._providers:
            raise ProviderNotFoundError(f"Cannot set default: provider '{name}' not registered")
        cls._default = name

    @classmethod
    def is_registered(cls, name: str) -> bool:
        """Check if a provider is registered."""
        return name in cls._providers

    @classmethod
    def clear(cls) -> None:
        """Clear all registrations (mainly for testing)."""
        cls._providers.clear()
        cls._factories.clear()
        cls._default = None
