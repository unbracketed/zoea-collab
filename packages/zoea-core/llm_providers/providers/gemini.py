"""
Google Gemini LLM Provider implementation.
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

# Well-known Gemini models with their capabilities
GEMINI_MODELS = [
    ModelInfo(
        model_id="gemini-2.5-flash",
        display_name="Gemini 2.5 Flash",
        provider="gemini",
        description="Fast and efficient for most tasks",
        context_window=1048576,  # 1M tokens
        max_output_tokens=8192,
        supports_vision=True,
        supports_tools=True,
        supports_streaming=True,
    ),
    ModelInfo(
        model_id="gemini-2.5-pro",
        display_name="Gemini 2.5 Pro",
        provider="gemini",
        description="Most capable Gemini model",
        context_window=1048576,  # 1M tokens
        max_output_tokens=8192,
        supports_vision=True,
        supports_tools=True,
        supports_streaming=True,
    ),
    ModelInfo(
        model_id="gemini-2.0-flash",
        display_name="Gemini 2.0 Flash",
        provider="gemini",
        description="Previous generation fast model",
        context_window=1048576,
        max_output_tokens=8192,
        supports_vision=True,
        supports_tools=True,
        supports_streaming=True,
    ),
    ModelInfo(
        model_id="gemini-1.5-pro",
        display_name="Gemini 1.5 Pro",
        provider="gemini",
        description="Advanced reasoning model",
        context_window=2097152,  # 2M tokens
        max_output_tokens=8192,
        supports_vision=True,
        supports_tools=True,
        supports_streaming=True,
    ),
    ModelInfo(
        model_id="gemini-1.5-flash",
        display_name="Gemini 1.5 Flash",
        provider="gemini",
        description="Fast model for high-volume tasks",
        context_window=1048576,
        max_output_tokens=8192,
        supports_vision=True,
        supports_tools=True,
        supports_streaming=True,
    ),
]


class GeminiProvider(LLMProvider):
    """
    Google Gemini API provider implementation.

    Supports Gemini 2.5, 2.0, and 1.5 models for chat completion.
    Uses the google-genai SDK.
    """

    def __init__(self, config: LLMConfig | None = None):
        """Initialize Gemini provider."""
        super().__init__(config)
        self._client = None

    @property
    def provider_name(self) -> str:
        return "gemini"

    @property
    def display_name(self) -> str:
        return "Google Gemini"

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

    def _get_client(self):
        """Get or create Gemini client."""
        if self._client is None:
            try:
                from google import genai
            except ImportError as e:
                raise ImportError("google-genai package not installed") from e

            api_key = self._get_api_key() or getattr(settings, "GEMINI_API_KEY", None)
            self._client = genai.Client(api_key=api_key)
        return self._client

    # -------------------------------------------------------------------------
    # Model Discovery
    # -------------------------------------------------------------------------

    def list_models(self) -> list[ModelInfo]:
        """Return available Gemini models."""
        return GEMINI_MODELS.copy()

    def list_models_from_api(self) -> list[ModelInfo]:
        """
        Fetch available models from Gemini API.

        This queries the API directly for the most up-to-date model list.
        """
        try:
            client = self._get_client()
            models = []

            for model in client.models.list():
                model_id = model.name.replace("models/", "")
                # Only include generative models
                if "gemini" in model_id.lower():
                    known = self.get_model(model_id)
                    if known:
                        models.append(known)
                    else:
                        models.append(
                            ModelInfo(
                                model_id=model_id,
                                display_name=model.display_name or model_id,
                                provider=self.provider_name,
                                description=model.description,
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
            from google import genai

            key = api_key or self._get_api_key() or getattr(settings, "GEMINI_API_KEY", None)
            if not key:
                return False

            client = genai.Client(api_key=key)
            # Make a simple models list call to validate
            list(client.models.list())
            return True
        except Exception:
            return False

    # -------------------------------------------------------------------------
    # Chat Completion
    # -------------------------------------------------------------------------

    def _convert_messages(self, messages: list[ChatMessage]) -> tuple[str | None, list[dict[str, Any]]]:
        """
        Convert ChatMessage objects to Gemini format.

        Returns (system_instruction, contents) tuple.
        Gemini uses a different format - system messages are separate.
        """
        system_instruction = None
        contents = []

        for msg in messages:
            role = msg.role.value if hasattr(msg.role, "value") else str(msg.role)

            if role == "system":
                # Gemini handles system as a separate parameter
                system_instruction = msg.content
            elif role == "user":
                contents.append({"role": "user", "parts": [{"text": msg.content}]})
            elif role == "assistant":
                contents.append({"role": "model", "parts": [{"text": msg.content}]})
            # Tool messages handled separately if needed

        return system_instruction, contents

    def chat(
        self,
        messages: list[ChatMessage],
        model_id: str | None = None,
        **kwargs,
    ) -> ChatResponse:
        """Perform synchronous chat completion."""
        client = self._get_client()
        model = self._get_model_id(model_id)
        system_instruction, contents = self._convert_messages(messages)

        # Build config
        from google.genai import types

        config_params: dict[str, Any] = {}

        if self.config:
            if self.config.temperature is not None:
                config_params["temperature"] = self.config.temperature
            if self.config.max_tokens:
                config_params["max_output_tokens"] = self.config.max_tokens

        # Allow kwargs to override
        if "temperature" in kwargs:
            config_params["temperature"] = kwargs.pop("temperature")
        if "max_tokens" in kwargs:
            config_params["max_output_tokens"] = kwargs.pop("max_tokens")

        if system_instruction:
            config_params["system_instruction"] = system_instruction

        try:
            response = client.models.generate_content(
                model=model,
                contents=contents,
                config=types.GenerateContentConfig(**config_params) if config_params else None,
            )

            # Extract text from response
            text = ""
            if response.text:
                text = response.text

            # Extract usage if available
            usage = None
            if hasattr(response, "usage_metadata") and response.usage_metadata:
                um = response.usage_metadata
                usage = {
                    "prompt_tokens": getattr(um, "prompt_token_count", 0),
                    "completion_tokens": getattr(um, "candidates_token_count", 0),
                    "total_tokens": getattr(um, "total_token_count", 0),
                }

            return ChatResponse(
                content=text,
                model=model,
                finish_reason=self._get_finish_reason(response),
                usage=usage,
                raw_response=response,
            )
        except Exception as e:
            error_msg = str(e)
            if "api key" in error_msg.lower() or "authentication" in error_msg.lower():
                raise AuthenticationError(f"Gemini authentication failed: {e}") from e
            raise APIError(f"Gemini API error: {e}") from e

    async def chat_async(
        self,
        messages: list[ChatMessage],
        model_id: str | None = None,
        **kwargs,
    ) -> ChatResponse:
        """
        Perform asynchronous chat completion.

        Note: google-genai uses synchronous client, so we run in executor.
        """
        import asyncio

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, lambda: self.chat(messages, model_id, **kwargs)
        )

    def chat_stream(
        self,
        messages: list[ChatMessage],
        model_id: str | None = None,
        **kwargs,
    ) -> Generator[StreamChunk, None, None]:
        """Stream chat completion synchronously."""
        client = self._get_client()
        model = self._get_model_id(model_id)
        system_instruction, contents = self._convert_messages(messages)

        from google.genai import types

        config_params: dict[str, Any] = {}

        if self.config:
            if self.config.temperature is not None:
                config_params["temperature"] = self.config.temperature
            if self.config.max_tokens:
                config_params["max_output_tokens"] = self.config.max_tokens

        if system_instruction:
            config_params["system_instruction"] = system_instruction

        try:
            response = client.models.generate_content_stream(
                model=model,
                contents=contents,
                config=types.GenerateContentConfig(**config_params) if config_params else None,
            )

            for chunk in response:
                if chunk.text:
                    yield StreamChunk(
                        content=chunk.text,
                        finish_reason=self._get_finish_reason(chunk),
                    )
        except Exception as e:
            raise APIError(f"Gemini streaming error: {e}") from e

    async def chat_stream_async(
        self,
        messages: list[ChatMessage],
        model_id: str | None = None,
        **kwargs,
    ) -> AsyncGenerator[StreamChunk, None]:
        """
        Stream chat completion asynchronously.

        Note: Wraps sync streaming since google-genai doesn't have native async.
        """
        import asyncio

        loop = asyncio.get_event_loop()

        # Run sync generator in thread and yield results
        def run_stream():
            return list(self.chat_stream(messages, model_id, **kwargs))

        chunks = await loop.run_in_executor(None, run_stream)
        for chunk in chunks:
            yield chunk

    # -------------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------------

    def _get_finish_reason(self, response) -> str | None:
        """Extract finish reason from Gemini response."""
        if hasattr(response, "candidates") and response.candidates:
            candidate = response.candidates[0]
            if hasattr(candidate, "finish_reason"):
                return str(candidate.finish_reason)
        return None


# Register the provider
LLMProviderRegistry.register("gemini", GeminiProvider, set_default=False)
