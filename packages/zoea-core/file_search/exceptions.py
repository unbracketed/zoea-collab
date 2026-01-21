"""
Exceptions for File Search Store operations.

Provides a hierarchy of exceptions for different error scenarios
across all backend implementations.
"""


class FileSearchError(Exception):
    """Base exception for all file search operations."""

    pass


class StoreError(FileSearchError):
    """Error related to store operations (create, delete, get)."""

    pass


class StoreNotFoundError(StoreError):
    """Store does not exist or has been deleted."""

    pass


class StoreCreationError(StoreError):
    """Failed to create a new store."""

    pass


class DocumentError(FileSearchError):
    """Error related to document operations."""

    pass


class DocumentUploadError(DocumentError):
    """Failed to upload/add a document to the store."""

    pass


class DocumentNotFoundError(DocumentError):
    """Document not found in the store."""

    pass


class UnsupportedDocumentTypeError(DocumentError):
    """Document type is not supported by the backend."""

    pass


class SearchError(FileSearchError):
    """Error during search operation."""

    pass


class BackendError(FileSearchError):
    """Backend-specific error."""

    def __init__(self, message: str, backend: str, original_error: Exception = None):
        self.backend = backend
        self.original_error = original_error
        super().__init__(f"[{backend}] {message}")


class ConfigurationError(FileSearchError):
    """Configuration or initialization error."""

    pass


class BackendNotFoundError(ConfigurationError):
    """Requested backend is not registered."""

    pass
