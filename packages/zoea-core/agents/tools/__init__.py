# Agent tools module
#
# All smolagents Tool implementations live here.
# Tools are auto-discovered and registered with ToolRegistry.

# Export base classes and utilities
from .base import (
    ARTIFACT_OUTPUT_SCHEMA,
    OutputCollection,
    TelemetryMixin,
    ToolArtifact,
    ZoeaTool,
    create_artifact_output,
    extract_artifacts_from_output,
    log_tool_execution,
    with_telemetry,
)
from .output_collections import InMemoryArtifactCollection

# Lazy imports to avoid import errors if dependencies are missing

_TOOL_IMPORTS = {
    # Search tools
    "WebSearchTool": "agents.tools.web_search",
    "VisitWebpageTool": "agents.tools.visit_webpage",
    "WebpageSummarizerTool": "agents.tools.webpage_summarizer",
    "SportsNewsTool": "agents.tools.sports_news",
    # Document tools
    "DocumentRetrieverTool": "agents.tools.document_retriever",
    "GeminiRetrieverTool": "agents.tools.document_retriever",  # Alias
    "ImageAnalyzerTool": "agents.tools.image_analyzer",
    # Image generation tools
    "OpenAIImageGenTool": "agents.tools.image_gen_openai",
    "HuggingFaceImageGenTool": "agents.tools.image_gen_hf",
    "GeminiImageGenTool": "agents.tools.image_gen_gemini",
    "NanoBananaTool": "agents.tools.image_gen_gemini",  # Alias
    # Data extraction tools
    "UnstructuredTool": "agents.tools.unstructured",
    # Agent skills
    "SkillLoaderTool": "agents.tools.skill_loader",
}


def __getattr__(name):
    """Lazy import of tool classes."""
    if name in _TOOL_IMPORTS:
        module_path = _TOOL_IMPORTS[name]
        import importlib

        module = importlib.import_module(module_path)
        return getattr(module, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    # Base classes
    "ZoeaTool",
    "ToolArtifact",
    "OutputCollection",
    "InMemoryArtifactCollection",
    # Artifact utilities
    "ARTIFACT_OUTPUT_SCHEMA",
    "TelemetryMixin",
    "create_artifact_output",
    "extract_artifacts_from_output",
    "log_tool_execution",
    "with_telemetry",
    # Search tools
    "WebSearchTool",
    "VisitWebpageTool",
    "WebpageSummarizerTool",
    "SportsNewsTool",
    # Document tools
    "DocumentRetrieverTool",
    "GeminiRetrieverTool",
    "ImageAnalyzerTool",
    # Image generation tools
    "OpenAIImageGenTool",
    "HuggingFaceImageGenTool",
    "GeminiImageGenTool",
    "NanoBananaTool",
    # Data extraction tools
    "UnstructuredTool",
    # Agent skills
    "SkillLoaderTool",
]
