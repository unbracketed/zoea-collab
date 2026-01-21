"""
Abstract base class for document source interfaces.

This module defines the contract that all document sources must implement.
Sources are responsible for listing and reading documents from various
storage backends.
"""

from abc import ABC, abstractmethod
from typing import Iterator, Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime


@dataclass
class DocumentMetadata:
    """
    Metadata about a document from a source.

    This dataclass provides a consistent interface for document metadata
    across different source types.
    """
    # Required fields
    path: str  # Unique identifier within the source (file path, S3 key, etc.)
    name: str  # Display name for the document

    # Optional fields
    size: Optional[int] = None  # Size in bytes
    modified_at: Optional[datetime] = None  # Last modification time
    content_type: Optional[str] = None  # MIME type
    extension: Optional[str] = None  # File extension (e.g., '.md', '.pdf')

    def __post_init__(self):
        """Auto-populate extension from path if not provided."""
        if self.extension is None and '.' in self.path:
            self.extension = '.' + self.path.rsplit('.', 1)[1].lower()


class SourceInterface(ABC):
    """
    Abstract interface for document sources.

    All document source implementations (local filesystem, S3, R2, etc.)
    must inherit from this class and implement its abstract methods.

    Example:
        class MySource(SourceInterface):
            def validate_config(self) -> None:
                if 'required_field' not in self.config:
                    raise ValueError("Missing required_field")

            def list_documents(self) -> Iterator[DocumentMetadata]:
                # Implementation
                yield DocumentMetadata(path='doc1.md', name='Document 1')

            def read_document(self, path: str) -> bytes:
                # Implementation
                return b'Document content'

            def get_display_name(self) -> str:
                return f"My Source: {self.config.get('name')}"
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the source with configuration.

        Args:
            config: Dictionary containing source-specific configuration.
                    Each source type defines its own config schema.

        Raises:
            ValueError: If configuration is invalid.
        """
        self.config = config
        self.validate_config()

    @abstractmethod
    def validate_config(self) -> None:
        """
        Validate source-specific configuration.

        Called during __init__ to ensure the source is properly configured.
        Should raise ValueError with a descriptive message if configuration
        is invalid.

        Raises:
            ValueError: If configuration is missing required fields or invalid.
        """
        pass

    @abstractmethod
    def list_documents(self) -> Iterator[DocumentMetadata]:
        """
        Yield metadata for all documents in this source.

        This method should iterate through all available documents in the
        source and yield DocumentMetadata for each one. The path field
        in DocumentMetadata should be usable with read_document().

        Yields:
            DocumentMetadata: Metadata for each document in the source.

        Raises:
            Exception: If there's an error accessing the source.
        """
        pass

    @abstractmethod
    def read_document(self, path: str) -> bytes:
        """
        Read document content from the source.

        Args:
            path: Document path/identifier (from DocumentMetadata.path)

        Returns:
            Document content as bytes.

        Raises:
            FileNotFoundError: If document doesn't exist.
            Exception: If there's an error reading the document.
        """
        pass

    @abstractmethod
    def get_display_name(self) -> str:
        """
        Get human-readable source description.

        This should return a descriptive name that helps users identify
        the source in the UI/admin interface.

        Returns:
            Human-readable source description.

        Example:
            "Local Filesystem: /path/to/docs"
            "S3 Bucket: my-bucket/prefix/"
            "Cloudflare R2: project-docs"
        """
        pass

    @abstractmethod
    def test_connection(self) -> bool:
        """
        Test if the source is accessible with current configuration.

        This method should verify that the source can be accessed with
        the current configuration (e.g., credentials are valid, path exists).

        Returns:
            True if connection is successful, False otherwise.
        """
        pass

    def get_source_type(self) -> str:
        """
        Get the source type identifier.

        Returns the registered type name for this source class.
        Subclasses typically don't need to override this.

        Returns:
            Source type identifier (e.g., 'local', 's3', 'r2').
        """
        return self.__class__.__name__.replace('Source', '').lower()
