"""
LLM Provider implementations.

This package contains concrete implementations of the LLMProvider
interface for different services.

Available providers:
- openai: OpenAI API (GPT-4, GPT-4o, etc.)
- gemini: Google Gemini API
- local: Local models via OpenAI-compatible API (Ollama, LM Studio)
"""

# Import providers to trigger registration
# Each import is wrapped in try/except to allow graceful degradation
# when a provider's dependencies are not installed.

try:
    from .openai import OpenAIProvider
except ImportError:
    OpenAIProvider = None  # type: ignore

try:
    from .gemini import GeminiProvider
except ImportError:
    GeminiProvider = None  # type: ignore

try:
    from .local import LocalModelProvider
except ImportError:
    LocalModelProvider = None  # type: ignore

__all__ = ["OpenAIProvider", "GeminiProvider", "LocalModelProvider"]
