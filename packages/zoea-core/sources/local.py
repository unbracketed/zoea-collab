"""
Local filesystem document source implementation.

This module implements a source that reads documents from the local filesystem
using glob patterns to filter files.
"""

import os
from pathlib import Path
from typing import Iterator, List
import mimetypes

from .base import SourceInterface, DocumentMetadata
from .registry import SourceRegistry


class LocalFileSystemSource(SourceInterface):
    """
    Local filesystem document source.

    This source reads documents from a local directory using glob patterns
    to filter which files to include.

    Configuration:
        {
            "path": "/absolute/path/to/documents",  # Required
            "pattern": "**/*.{md,pdf,png,jpg}",     # Optional, default: **/*
            "recursive": true,                       # Optional, default: true
            "follow_symlinks": false                 # Optional, default: false
        }

    Example:
        source = LocalFileSystemSource({
            "path": "/Users/brian/projects/demo-docs",
            "pattern": "**/*.md"
        })

        for doc_meta in source.list_documents():
            content = source.read_document(doc_meta.path)
            print(f"Read {len(content)} bytes from {doc_meta.name}")
    """

    # Supported file extensions for document types
    DOCUMENT_EXTENSIONS = {
        # Images
        '.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp', '.svg',
        # PDFs
        '.pdf',
        # Text documents
        '.md', '.markdown', '.txt', '.csv', '.json', '.yaml', '.yml',
        # Diagrams
        '.d2',
    }

    def validate_config(self) -> None:
        """
        Validate local filesystem source configuration.

        Raises:
            ValueError: If configuration is invalid.
        """
        if 'path' not in self.config:
            raise ValueError("Local filesystem source requires 'path' in config")

        path = Path(self.config['path'])

        if not path.is_absolute():
            raise ValueError(f"Path must be absolute, got: {self.config['path']}")

        if not path.exists():
            raise ValueError(f"Path does not exist: {self.config['path']}")

        if not path.is_dir():
            raise ValueError(f"Path is not a directory: {self.config['path']}")

    def list_documents(self) -> Iterator[DocumentMetadata]:
        """
        List all documents matching the configured pattern.

        Yields:
            DocumentMetadata: Metadata for each matching document.
        """
        base_path = Path(self.config['path'])
        pattern = self.config.get('pattern', '**/*')
        recursive = self.config.get('recursive', True)
        follow_symlinks = self.config.get('follow_symlinks', False)

        # Use rglob for recursive patterns, glob for non-recursive
        if recursive and '**' in pattern:
            files = base_path.rglob(pattern.replace('**/', ''))
        else:
            files = base_path.glob(pattern)

        for file_path in sorted(files):
            # Skip if not following symlinks and this is a symlink
            if not follow_symlinks and file_path.is_symlink():
                continue

            # Skip directories
            if not file_path.is_file():
                continue

            # Skip files with unsupported extensions
            if file_path.suffix.lower() not in self.DOCUMENT_EXTENSIONS:
                continue

            # Get file stats
            stat = file_path.stat()

            # Create metadata
            yield DocumentMetadata(
                path=str(file_path),  # Absolute path
                name=file_path.name,  # File name only
                size=stat.st_size,
                modified_at=stat.st_mtime,  # Will be converted to datetime
                content_type=mimetypes.guess_type(str(file_path))[0],
                extension=file_path.suffix.lower()
            )

    def read_document(self, path: str) -> bytes:
        """
        Read document content from the filesystem.

        Args:
            path: Absolute path to the document.

        Returns:
            Document content as bytes.

        Raises:
            FileNotFoundError: If document doesn't exist.
            PermissionError: If document is not readable.
        """
        file_path = Path(path)

        if not file_path.exists():
            raise FileNotFoundError(f"Document not found: {path}")

        if not file_path.is_file():
            raise ValueError(f"Path is not a file: {path}")

        return file_path.read_bytes()

    def get_display_name(self) -> str:
        """
        Get human-readable source description.

        Returns:
            Description including the filesystem path.
        """
        path = self.config['path']
        pattern = self.config.get('pattern', '**/*')
        return f"Local Filesystem: {path} ({pattern})"

    def test_connection(self) -> bool:
        """
        Test if the filesystem path is accessible.

        Returns:
            True if path exists and is readable, False otherwise.
        """
        try:
            path = Path(self.config['path'])
            if not path.exists() or not path.is_dir():
                return False

            # Try to list the directory
            list(path.iterdir())
            return True

        except (OSError, PermissionError):
            return False


# Register the local filesystem source
SourceRegistry.register('local', LocalFileSystemSource)
