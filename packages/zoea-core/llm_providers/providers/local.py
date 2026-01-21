"""
Local Model LLM Provider implementation.

Supports local models via OpenAI-compatible APIs:
- Ollama (http://localhost:11434)
- LM Studio (http://localhost:1234)
- vLLM (http://localhost:8000)
- Any other OpenAI-compatible local server
"""

import logging
from collections.abc import AsyncGenerator, Generator
from typing import Any
from urllib.parse import urlparse

from django.conf import settings

from ..base import LLMProvider
from ..exceptions import APIError, ConfigurationError
from ..registry import LLMProviderRegistry
from ..types import (
    ChatMessage,
    ChatResponse,
    LLMConfig,
    ModelInfo,
    ProviderInfo,
    StreamChunk,
)

logger = logging.getLogger(__name__)

# Default local endpoints for common providers
DEFAULT_ENDPOINTS = {
    "ollama": "http://localhost:11434",
    "lmstudio": "http://localhost:1234",
    "vllm": "http://localhost:8000",
}

# Some well-known local models (for display purposes)
COMMON_LOCAL_MODELS = [
    ModelInfo(
        model_id="llama3.2",
        display_name="Llama 3.2",
        provider="local",
        description="Meta's Llama 3.2 model",
        context_window=128000,
        supports_vision=False,
        supports_tools=True,
        supports_streaming=True,
    ),
    ModelInfo(
        model_id="llama3.2:3b",
        display_name="Llama 3.2 3B",
        provider="local",
        description="Llama 3.2 3B variant",
        context_window=128000,
        supports_vision=False,
        supports_tools=True,
        supports_streaming=True,
    ),
    ModelInfo(
        model_id="mistral",
        display_name="Mistral",
        provider="local",
        description="Mistral AI's base model",
        context_window=32768,
        supports_vision=False,
        supports_tools=True,
        supports_streaming=True,
    ),
    ModelInfo(
        model_id="codellama",
        display_name="Code Llama",
        provider="local",
        description="Meta's code-focused Llama model",
        context_window=16384,
        supports_vision=False,
        supports_tools=False,
        supports_streaming=True,
    ),
    ModelInfo(
        model_id="gemma2",
        display_name="Gemma 2",
        provider="local",
        description="Google's Gemma 2 model",
        context_window=8192,
        supports_vision=False,
        supports_tools=True,
        supports_streaming=True,
    ),
    ModelInfo(
        model_id="qwen2.5",
        display_name="Qwen 2.5",
        provider="local",
        description="Alibaba's Qwen 2.5 model",
        context_window=32768,
        supports_vision=False,
        supports_tools=True,
        supports_streaming=True,
    ),
]


def validate_local_endpoint(endpoint: str) -> bool:
    """
    Validate that an endpoint is safe to use for local models.

    Prevents SSRF by ensuring the endpoint points to localhost or
    private network addresses.

    Args:
        endpoint: The endpoint URL to validate

    Returns:
        True if the endpoint is safe, False otherwise
    """
    try:
        parsed = urlparse(endpoint)

        # Must have scheme and netloc
        if not parsed.scheme or not parsed.netloc:
            return False

        # Only allow http/https
        if parsed.scheme not in ("http", "https"):
            return False

        # Extract host (without port)
        host = parsed.hostname or ""

        # Allow localhost variants
        localhost_names = {"localhost", "127.0.0.1", "::1", "[::1]"}
        if host.lower() in localhost_names:
            return True

        # Allow private network ranges (RFC 1918)
        # 10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16
        if host.startswith("10."):
            return True
        if host.startswith("192.168."):
            return True
        if host.startswith("172."):
            # 172.16.x.x - 172.31.x.x
            try:
                second_octet = int(host.split(".")[1])
                if 16 <= second_octet <= 31:
                    return True
            except (ValueError, IndexError):
                pass

        # Allow Docker internal hostnames
        docker_hosts = {"host.docker.internal", "gateway.docker.internal"}
        if host.lower() in docker_hosts:
            return True

        return False

    except Exception:
        return False


class LocalModelProvider(LLMProvider):
    """
    Local model provider using OpenAI-compatible API.

    Supports Ollama, LM Studio, vLLM, and any other OpenAI-compatible
    local inference server. Models are discovered dynamically from the
    running server.
    """

    def __init__(self, config: LLMConfig | None = None):
        """Initialize local model provider."""
        super().__init__(config)
        self._client = None
        self._async_client = None

        # Validate endpoint if provided
        if config and config.api_base:
            if not validate_local_endpoint(config.api_base):
                raise ConfigurationError(
                    f"Invalid local endpoint: {config.api_base}. "
                    "Only localhost and private network addresses are allowed."
                )

    @property
    def provider_name(self) -> str:
        return "local"

    @property
    def display_name(self) -> str:
        return "Local Model"

    def get_info(self) -> ProviderInfo:
        return ProviderInfo(
            name=self.provider_name,
            display_name=self.display_name,
            requires_api_key=False,
            supports_custom_endpoint=True,
            available_models=self.list_models(),
        )

    # -------------------------------------------------------------------------
    # Endpoint Management
    # -------------------------------------------------------------------------

    def _get_base_url(self) -> str:
        """Get the base URL for the local server."""
        # Priority: config > settings > default
        if self.config and self.config.api_base:
            return self.config.api_base

        endpoint = getattr(settings, "LOCAL_MODEL_ENDPOINT", None)
        if endpoint:
            return endpoint

        return DEFAULT_ENDPOINTS["ollama"]

    def _get_api_url(self) -> str:
        """Get the OpenAI-compatible API URL."""
        base = self._get_base_url().rstrip("/")
        # Ollama uses /v1 path, others might vary
        return f"{base}/v1"

    # -------------------------------------------------------------------------
    # Client Management
    # -------------------------------------------------------------------------

    def _get_sync_client(self):
        """Get or create sync OpenAI client for local server."""
        if self._client is None:
            try:
                from openai import OpenAI
            except ImportError as e:
                raise ImportError("openai package not installed") from e

            self._client = OpenAI(
                base_url=self._get_api_url(),
                api_key="not-needed",  # Local servers typically don't need keys
            )
        return self._client

    def _get_async_client(self):
        """Get or create async OpenAI client for local server."""
        if self._async_client is None:
            try:
                from openai import AsyncOpenAI
            except ImportError as e:
                raise ImportError("openai package not installed") from e

            self._async_client = AsyncOpenAI(
                base_url=self._get_api_url(),
                api_key="not-needed",
            )
        return self._async_client

    # -------------------------------------------------------------------------
    # Model Discovery
    # -------------------------------------------------------------------------

    def list_models(self) -> list[ModelInfo]:
        """
        Return a list of common local models.

        For dynamic discovery, use list_models_from_api().
        """
        return COMMON_LOCAL_MODELS.copy()

    def list_models_from_api(self) -> list[ModelInfo]:
        """
        Fetch available models from the local server.

        This queries the running local server for available models.
        Returns common models list if the server is not reachable.
        """
        try:
            client = self._get_sync_client()
            response = client.models.list()

            models = []
            for model in response.data:
                # Check if we have predefined info
                known = self.get_model(model.id)
                if known:
                    models.append(known)
                else:
                    models.append(
                        ModelInfo(
                            model_id=model.id,
                            display_name=model.id,
                            provider=self.provider_name,
                            description=f"Local model: {model.id}",
                            supports_streaming=True,
                        )
                    )
            return models if models else self.list_models()
        except Exception as e:
            logger.debug(f"Failed to list models from local server: {e}")
            return self.list_models()

    # -------------------------------------------------------------------------
    # Server Health
    # -------------------------------------------------------------------------

    def is_available(self) -> bool:
        """Check if the local server is reachable."""
        try:
            client = self._get_sync_client()
            client.models.list()
            return True
        except Exception:
            return False

    def validate_credentials(self, api_key: str | None = None) -> bool:
        """
        Validate that the local server is reachable.

        For local models, we validate connectivity rather than credentials.
        """
        return self.is_available()

    # -------------------------------------------------------------------------
    # Chat Completion
    # -------------------------------------------------------------------------

    def _convert_messages(self, messages: list[ChatMessage]) -> list[dict[str, Any]]:
        """Convert ChatMessage objects to OpenAI format."""
        result = []
        for msg in messages:
            role = msg.role.value if hasattr(msg.role, "value") else str(msg.role)
            entry: dict[str, Any] = {"role": role, "content": msg.content}
            if msg.name:
                entry["name"] = msg.name
            if msg.tool_calls:
                entry["tool_calls"] = msg.tool_calls
            if msg.tool_call_id:
                entry["tool_call_id"] = msg.tool_call_id
            result.append(entry)
        return result

    def chat(
        self,
        messages: list[ChatMessage],
        model_id: str | None = None,
        **kwargs,
    ) -> ChatResponse:
        """Perform synchronous chat completion."""
        client = self._get_sync_client()
        model = self._get_model_id(model_id)
        openai_messages = self._convert_messages(messages)

        # Build request params
        params: dict[str, Any] = {
            "model": model,
            "messages": openai_messages,
        }

        # Add optional parameters
        if "temperature" in kwargs:
            params["temperature"] = kwargs["temperature"]
        if "max_tokens" in kwargs:
            params["max_tokens"] = kwargs["max_tokens"]
        if "top_p" in kwargs:
            params["top_p"] = kwargs["top_p"]
        if "stop" in kwargs:
            params["stop"] = kwargs["stop"]

        try:
            response = client.chat.completions.create(**params)

            return ChatResponse(
                content=response.choices[0].message.content or "",
                model=response.model,
                provider=self.provider_name,
                usage={
                    "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
                    "completion_tokens": response.usage.completion_tokens if response.usage else 0,
                    "total_tokens": response.usage.total_tokens if response.usage else 0,
                },
                finish_reason=response.choices[0].finish_reason,
                raw_response=response.model_dump() if hasattr(response, "model_dump") else None,
            )
        except Exception as e:
            logger.error(f"Local model chat error: {e}")
            raise APIError(f"Local model chat failed: {e}") from e

    async def chat_async(
        self,
        messages: list[ChatMessage],
        model_id: str | None = None,
        **kwargs,
    ) -> ChatResponse:
        """Perform asynchronous chat completion."""
        client = self._get_async_client()
        model = self._get_model_id(model_id)
        openai_messages = self._convert_messages(messages)

        # Build request params
        params: dict[str, Any] = {
            "model": model,
            "messages": openai_messages,
        }

        # Add optional parameters
        if "temperature" in kwargs:
            params["temperature"] = kwargs["temperature"]
        if "max_tokens" in kwargs:
            params["max_tokens"] = kwargs["max_tokens"]
        if "top_p" in kwargs:
            params["top_p"] = kwargs["top_p"]
        if "stop" in kwargs:
            params["stop"] = kwargs["stop"]

        try:
            response = await client.chat.completions.create(**params)

            return ChatResponse(
                content=response.choices[0].message.content or "",
                model=response.model,
                provider=self.provider_name,
                usage={
                    "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
                    "completion_tokens": response.usage.completion_tokens if response.usage else 0,
                    "total_tokens": response.usage.total_tokens if response.usage else 0,
                },
                finish_reason=response.choices[0].finish_reason,
                raw_response=response.model_dump() if hasattr(response, "model_dump") else None,
            )
        except Exception as e:
            logger.error(f"Local model async chat error: {e}")
            raise APIError(f"Local model chat failed: {e}") from e

    # -------------------------------------------------------------------------
    # Streaming
    # -------------------------------------------------------------------------

    def chat_stream(
        self,
        messages: list[ChatMessage],
        model_id: str | None = None,
        **kwargs,
    ) -> Generator[StreamChunk, None, None]:
        """Stream chat completion responses."""
        client = self._get_sync_client()
        model = self._get_model_id(model_id)
        openai_messages = self._convert_messages(messages)

        params: dict[str, Any] = {
            "model": model,
            "messages": openai_messages,
            "stream": True,
        }

        if "temperature" in kwargs:
            params["temperature"] = kwargs["temperature"]
        if "max_tokens" in kwargs:
            params["max_tokens"] = kwargs["max_tokens"]

        try:
            stream = client.chat.completions.create(**params)

            for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield StreamChunk(
                        content=chunk.choices[0].delta.content,
                        model=chunk.model,
                        provider=self.provider_name,
                        finish_reason=chunk.choices[0].finish_reason,
                    )
        except Exception as e:
            logger.error(f"Local model stream error: {e}")
            raise APIError(f"Local model stream failed: {e}") from e

    async def chat_stream_async(
        self,
        messages: list[ChatMessage],
        model_id: str | None = None,
        **kwargs,
    ) -> AsyncGenerator[StreamChunk, None]:
        """Stream chat completion responses asynchronously."""
        client = self._get_async_client()
        model = self._get_model_id(model_id)
        openai_messages = self._convert_messages(messages)

        params: dict[str, Any] = {
            "model": model,
            "messages": openai_messages,
            "stream": True,
        }

        if "temperature" in kwargs:
            params["temperature"] = kwargs["temperature"]
        if "max_tokens" in kwargs:
            params["max_tokens"] = kwargs["max_tokens"]

        try:
            stream = await client.chat.completions.create(**params)

            async for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield StreamChunk(
                        content=chunk.choices[0].delta.content,
                        model=chunk.model,
                        provider=self.provider_name,
                        finish_reason=chunk.choices[0].finish_reason,
                    )
        except Exception as e:
            logger.error(f"Local model async stream error: {e}")
            raise APIError(f"Local model async stream failed: {e}") from e


# Register with registry
LLMProviderRegistry.register("local", LocalModelProvider)
