"""
Type definitions for the LLM Provider interface.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class MessageRole(str, Enum):
    """Standard message roles."""

    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


@dataclass
class ChatMessage:
    """A message in a chat conversation.

    For vision/multimodal messages, content can be a list of content parts:
    [{"type": "text", "text": "..."}, {"type": "image_url", "image_url": {"url": "data:..."}}]
    """

    role: MessageRole | str
    content: str | list[dict[str, Any]]  # str for text-only, list for multimodal
    name: str | None = None
    tool_calls: list[dict[str, Any]] | None = None
    tool_call_id: str | None = None


@dataclass
class ModelInfo:
    """Information about an available model."""

    model_id: str
    display_name: str
    provider: str
    description: str | None = None
    context_window: int | None = None
    max_output_tokens: int | None = None
    supports_vision: bool = False
    supports_tools: bool = False
    supports_streaming: bool = True


@dataclass
class ChatResponse:
    """Response from a chat completion."""

    content: str
    model: str
    finish_reason: str | None = None
    usage: dict[str, int] | None = None
    tool_calls: list[dict[str, Any]] | None = None
    raw_response: Any = None


@dataclass
class StreamChunk:
    """A chunk from a streaming response."""

    content: str | None = None
    finish_reason: str | None = None
    tool_calls: list[dict[str, Any]] | None = None


@dataclass
class LLMConfig:
    """Configuration for an LLM provider/model."""

    provider: str
    model_id: str
    api_key: str | None = None
    endpoint: str | None = None  # For local models
    temperature: float = 0.7
    max_tokens: int | None = None
    extra_params: dict[str, Any] = field(default_factory=dict)


@dataclass
class ProviderInfo:
    """Information about a provider."""

    name: str
    display_name: str
    requires_api_key: bool = True
    supports_custom_endpoint: bool = False
    default_endpoint: str | None = None
    available_models: list[ModelInfo] = field(default_factory=list)
