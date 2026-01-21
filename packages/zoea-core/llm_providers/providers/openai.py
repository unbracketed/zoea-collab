"""
OpenAI LLM Provider implementation.
"""

import logging
from collections.abc import AsyncGenerator, Generator
from typing import Any

from django.conf import settings

from ..base import LLMProvider
from ..exceptions import APIError, AuthenticationError
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

# Well-known OpenAI models with their capabilities
OPENAI_MODELS = [
    ModelInfo(
        model_id="gpt-4o",
        display_name="GPT-4o",
        provider="openai",
        description="Most capable model for complex tasks with vision support",
        context_window=128000,
        max_output_tokens=16384,
        supports_vision=True,
        supports_tools=True,
        supports_streaming=True,
    ),
    ModelInfo(
        model_id="gpt-4o-mini",
        display_name="GPT-4o Mini",
        provider="openai",
        description="Fast and affordable for focused tasks",
        context_window=128000,
        max_output_tokens=16384,
        supports_vision=True,
        supports_tools=True,
        supports_streaming=True,
    ),
    ModelInfo(
        model_id="gpt-4-turbo",
        display_name="GPT-4 Turbo",
        provider="openai",
        description="Previous generation flagship model",
        context_window=128000,
        max_output_tokens=4096,
        supports_vision=True,
        supports_tools=True,
        supports_streaming=True,
    ),
    ModelInfo(
        model_id="gpt-3.5-turbo",
        display_name="GPT-3.5 Turbo",
        provider="openai",
        description="Fast and cost-effective for simpler tasks",
        context_window=16385,
        max_output_tokens=4096,
        supports_vision=False,
        supports_tools=True,
        supports_streaming=True,
    ),
    ModelInfo(
        model_id="o1",
        display_name="o1",
        provider="openai",
        description="Reasoning model for complex problem solving",
        context_window=200000,
        max_output_tokens=100000,
        supports_vision=True,
        supports_tools=False,
        supports_streaming=True,
    ),
    ModelInfo(
        model_id="o1-mini",
        display_name="o1 Mini",
        provider="openai",
        description="Fast reasoning model",
        context_window=128000,
        max_output_tokens=65536,
        supports_vision=True,
        supports_tools=False,
        supports_streaming=True,
    ),
]


class OpenAIProvider(LLMProvider):
    """
    OpenAI API provider implementation.

    Supports all OpenAI chat models including GPT-4o, GPT-4 Turbo,
    GPT-3.5 Turbo, and o1 reasoning models.
    """

    def __init__(self, config: LLMConfig | None = None):
        """Initialize OpenAI provider."""
        super().__init__(config)
        self._client = None
        self._async_client = None

    @property
    def provider_name(self) -> str:
        return "openai"

    @property
    def display_name(self) -> str:
        return "OpenAI"

    def get_info(self) -> ProviderInfo:
        return ProviderInfo(
            name=self.provider_name,
            display_name=self.display_name,
            requires_api_key=True,
            supports_custom_endpoint=False,
            available_models=self.list_models(),
        )

    # -------------------------------------------------------------------------
    # Client Management
    # -------------------------------------------------------------------------

    def _get_sync_client(self):
        """Get or create sync OpenAI client."""
        if self._client is None:
            try:
                from openai import OpenAI
            except ImportError as e:
                raise ImportError("openai package not installed") from e

            api_key = self._get_api_key() or getattr(settings, "OPENAI_API_KEY", None)
            self._client = OpenAI(api_key=api_key)
        return self._client

    def _get_async_client(self):
        """Get or create async OpenAI client."""
        if self._async_client is None:
            try:
                from openai import AsyncOpenAI
            except ImportError as e:
                raise ImportError("openai package not installed") from e

            api_key = self._get_api_key() or getattr(settings, "OPENAI_API_KEY", None)
            self._async_client = AsyncOpenAI(api_key=api_key)
        return self._async_client

    # -------------------------------------------------------------------------
    # Model Discovery
    # -------------------------------------------------------------------------

    def list_models(self) -> list[ModelInfo]:
        """Return available OpenAI models."""
        return OPENAI_MODELS.copy()

    def list_models_from_api(self) -> list[ModelInfo]:
        """
        Fetch available models from OpenAI API.

        This queries the API directly for the most up-to-date model list.
        """
        try:
            client = self._get_sync_client()
            response = client.models.list()

            models = []
            for model in response.data:
                # Filter to chat models
                if any(
                    prefix in model.id
                    for prefix in ["gpt-4", "gpt-3.5", "o1", "chatgpt"]
                ):
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
                                supports_streaming=True,
                            )
                        )
            return models
        except Exception as e:
            logger.warning(f"Failed to list models from API: {e}")
            return self.list_models()

    # -------------------------------------------------------------------------
    # Authentication
    # -------------------------------------------------------------------------

    def validate_credentials(self, api_key: str | None = None) -> bool:
        """Validate API key by making a test request."""
        try:
            from openai import OpenAI

            key = api_key or self._get_api_key() or getattr(settings, "OPENAI_API_KEY", None)
            if not key:
                return False

            client = OpenAI(api_key=key)
            # Make a simple models list call to validate
            client.models.list()
            return True
        except Exception:
            return False

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
        if self.config:
            if self.config.temperature is not None:
                params["temperature"] = self.config.temperature
            if self.config.max_tokens:
                params["max_tokens"] = self.config.max_tokens

        # Allow kwargs to override
        params.update(kwargs)

        try:
            completion = client.chat.completions.create(**params)

            return ChatResponse(
                content=completion.choices[0].message.content or "",
                model=completion.model,
                finish_reason=completion.choices[0].finish_reason,
                usage={
                    "prompt_tokens": completion.usage.prompt_tokens,
                    "completion_tokens": completion.usage.completion_tokens,
                    "total_tokens": completion.usage.total_tokens,
                } if completion.usage else None,
                tool_calls=(
                    [tc.model_dump() for tc in completion.choices[0].message.tool_calls]
                    if completion.choices[0].message.tool_calls
                    else None
                ),
                raw_response=completion,
            )
        except Exception as e:
            error_msg = str(e)
            if "authentication" in error_msg.lower() or "api key" in error_msg.lower():
                raise AuthenticationError(f"OpenAI authentication failed: {e}") from e
            raise APIError(f"OpenAI API error: {e}") from e

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

        if self.config:
            if self.config.temperature is not None:
                params["temperature"] = self.config.temperature
            if self.config.max_tokens:
                params["max_tokens"] = self.config.max_tokens

        params.update(kwargs)

        try:
            completion = await client.chat.completions.create(**params)

            return ChatResponse(
                content=completion.choices[0].message.content or "",
                model=completion.model,
                finish_reason=completion.choices[0].finish_reason,
                usage={
                    "prompt_tokens": completion.usage.prompt_tokens,
                    "completion_tokens": completion.usage.completion_tokens,
                    "total_tokens": completion.usage.total_tokens,
                } if completion.usage else None,
                tool_calls=(
                    [tc.model_dump() for tc in completion.choices[0].message.tool_calls]
                    if completion.choices[0].message.tool_calls
                    else None
                ),
                raw_response=completion,
            )
        except Exception as e:
            error_msg = str(e)
            if "authentication" in error_msg.lower() or "api key" in error_msg.lower():
                raise AuthenticationError(f"OpenAI authentication failed: {e}") from e
            raise APIError(f"OpenAI API error: {e}") from e

    def chat_stream(
        self,
        messages: list[ChatMessage],
        model_id: str | None = None,
        **kwargs,
    ) -> Generator[StreamChunk, None, None]:
        """Stream chat completion synchronously."""
        client = self._get_sync_client()
        model = self._get_model_id(model_id)
        openai_messages = self._convert_messages(messages)

        params: dict[str, Any] = {
            "model": model,
            "messages": openai_messages,
            "stream": True,
        }

        if self.config:
            if self.config.temperature is not None:
                params["temperature"] = self.config.temperature
            if self.config.max_tokens:
                params["max_tokens"] = self.config.max_tokens

        params.update(kwargs)

        try:
            stream = client.chat.completions.create(**params)

            for chunk in stream:
                if chunk.choices:
                    choice = chunk.choices[0]
                    delta = choice.delta
                    yield StreamChunk(
                        content=delta.content if delta else None,
                        finish_reason=choice.finish_reason,
                        tool_calls=(
                            [tc.model_dump() for tc in delta.tool_calls]
                            if delta and delta.tool_calls
                            else None
                        ),
                    )
        except Exception as e:
            raise APIError(f"OpenAI streaming error: {e}") from e

    async def chat_stream_async(
        self,
        messages: list[ChatMessage],
        model_id: str | None = None,
        **kwargs,
    ) -> AsyncGenerator[StreamChunk, None]:
        """Stream chat completion asynchronously."""
        client = self._get_async_client()
        model = self._get_model_id(model_id)
        openai_messages = self._convert_messages(messages)

        params: dict[str, Any] = {
            "model": model,
            "messages": openai_messages,
            "stream": True,
        }

        if self.config:
            if self.config.temperature is not None:
                params["temperature"] = self.config.temperature
            if self.config.max_tokens:
                params["max_tokens"] = self.config.max_tokens

        params.update(kwargs)

        try:
            stream = await client.chat.completions.create(**params)

            async for chunk in stream:
                if chunk.choices:
                    choice = chunk.choices[0]
                    delta = choice.delta
                    yield StreamChunk(
                        content=delta.content if delta else None,
                        finish_reason=choice.finish_reason,
                        tool_calls=(
                            [tc.model_dump() for tc in delta.tool_calls]
                            if delta and delta.tool_calls
                            else None
                        ),
                    )
        except Exception as e:
            raise APIError(f"OpenAI streaming error: {e}") from e


# Register the provider
LLMProviderRegistry.register("openai", OpenAIProvider, set_default=True)
