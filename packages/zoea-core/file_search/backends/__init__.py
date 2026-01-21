"""
File Search Store backend implementations.

This package contains concrete implementations of the FileSearchStore
interface for different search technologies.

Available backends:
- gemini: Google Gemini File Search (production)
- chromadb: ChromaDB vector database (local development)
"""

from .gemini import GeminiFileSearchStore

# ChromaDB is optional - only import if installed
try:
    from .chromadb import ChromaDBFileSearchStore
except ImportError:
    ChromaDBFileSearchStore = None  # type: ignore

__all__ = ["GeminiFileSearchStore", "ChromaDBFileSearchStore"]
