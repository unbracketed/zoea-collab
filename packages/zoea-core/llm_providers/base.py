"""
Abstract base class for LLM providers.
"""

from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator, Generator

from .types import ChatMessage, ChatResponse, LLMConfig, ModelInfo, ProviderInfo, StreamChunk


class LLMProvider(ABC):
    """
    Abstract interface for LLM providers.

    Each provider implementation handles authentication, model listing,
    and chat completion for a specific service (OpenAI, Gemini, etc.).
    """

    def __init__(self, config: LLMConfig | None = None):
        """
        Initialize the provider.

        Args:
            config: Optional configuration with API key and settings.
        """
        self.config = config

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Return the provider identifier (e.g., 'openai', 'gemini', 'ollama')."""
        pass

    @property
    @abstractmethod
    def display_name(self) -> str:
        """Return human-readable provider name."""
        pass

    @abstractmethod
    def get_info(self) -> ProviderInfo:
        """Return information about this provider."""
        pass

    # -------------------------------------------------------------------------
    # Model Discovery
    # -------------------------------------------------------------------------

    @abstractmethod
    def list_models(self) -> list[ModelInfo]:
        """
        Return available models for this provider.

        Returns:
            List of ModelInfo objects describing available models.
        """
        pass

    def get_model(self, model_id: str) -> ModelInfo | None:
        """
        Get information about a specific model.

        Args:
            model_id: The model identifier.

        Returns:
            ModelInfo if found, None otherwise.
        """
        for model in self.list_models():
            if model.model_id == model_id:
                return model
        return None

    # -------------------------------------------------------------------------
    # Authentication
    # -------------------------------------------------------------------------

    @abstractmethod
    def validate_credentials(self, api_key: str | None = None) -> bool:
        """
        Validate API credentials.

        Args:
            api_key: Optional API key to validate. If not provided,
                    uses the key from config.

        Returns:
            True if credentials are valid, False otherwise.
        """
        pass

    # -------------------------------------------------------------------------
    # Chat Completion
    # -------------------------------------------------------------------------

    @abstractmethod
    def chat(
        self,
        messages: list[ChatMessage],
        model_id: str | None = None,
        **kwargs,
    ) -> ChatResponse:
        """
        Perform a synchronous chat completion.

        Args:
            messages: List of chat messages.
            model_id: Model to use. If not provided, uses config default.
            **kwargs: Additional provider-specific parameters.

        Returns:
            ChatResponse with the completion.
        """
        pass

    @abstractmethod
    async def chat_async(
        self,
        messages: list[ChatMessage],
        model_id: str | None = None,
        **kwargs,
    ) -> ChatResponse:
        """
        Perform an asynchronous chat completion.

        Args:
            messages: List of chat messages.
            model_id: Model to use. If not provided, uses config default.
            **kwargs: Additional provider-specific parameters.

        Returns:
            ChatResponse with the completion.
        """
        pass

    def chat_stream(
        self,
        messages: list[ChatMessage],
        model_id: str | None = None,
        **kwargs,
    ) -> Generator[StreamChunk, None, None]:
        """
        Stream a chat completion synchronously.

        Args:
            messages: List of chat messages.
            model_id: Model to use. If not provided, uses config default.
            **kwargs: Additional provider-specific parameters.

        Yields:
            StreamChunk objects as they arrive.
        """
        raise NotImplementedError(f"{self.provider_name} does not support sync streaming")

    async def chat_stream_async(
        self,
        messages: list[ChatMessage],
        model_id: str | None = None,
        **kwargs,
    ) -> AsyncGenerator[StreamChunk, None]:
        """
        Stream a chat completion asynchronously.

        Args:
            messages: List of chat messages.
            model_id: Model to use. If not provided, uses config default.
            **kwargs: Additional provider-specific parameters.

        Yields:
            StreamChunk objects as they arrive.
        """
        raise NotImplementedError(f"{self.provider_name} does not support async streaming")
        yield  # Make this a generator

    # -------------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------------

    def _get_api_key(self, api_key: str | None = None) -> str | None:
        """Get API key from argument or config."""
        return api_key or (self.config.api_key if self.config else None)

    def _get_model_id(self, model_id: str | None = None) -> str:
        """Get model ID from argument or config."""
        if model_id:
            return model_id
        if self.config and self.config.model_id:
            return self.config.model_id
        raise ValueError("No model_id provided and no default configured")
