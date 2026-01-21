"""
Exception hierarchy for LLM Provider errors.
"""


class LLMProviderError(Exception):
    """Base exception for all LLM provider errors."""

    pass


class ProviderNotFoundError(LLMProviderError):
    """Raised when a requested provider is not registered."""

    pass


class ModelNotFoundError(LLMProviderError):
    """Raised when a requested model is not available."""

    pass


class AuthenticationError(LLMProviderError):
    """Raised when API key or credentials are invalid."""

    pass


class RateLimitError(LLMProviderError):
    """Raised when rate limits are exceeded."""

    pass


class APIError(LLMProviderError):
    """Raised when an API call fails."""

    def __init__(self, message: str, status_code: int | None = None, response: dict | None = None):
        super().__init__(message)
        self.status_code = status_code
        self.response = response


class ConfigurationError(LLMProviderError):
    """Raised when provider configuration is invalid."""

    pass


class StreamingError(LLMProviderError):
    """Raised when streaming fails."""

    pass
