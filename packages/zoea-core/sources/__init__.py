"""
Source interface for document storage backends.

This module provides abstractions for pulling documents from various storage
backends (local filesystem, S3, R2, etc.) into the Zoea Studio document system.
"""

from .base import SourceInterface
from .registry import SourceRegistry
from .local import LocalFileSystemSource

__all__ = [
    'SourceInterface',
    'SourceRegistry',
    'LocalFileSystemSource',
]
