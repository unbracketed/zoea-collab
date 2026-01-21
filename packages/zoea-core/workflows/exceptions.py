"""Custom exceptions for the workflow system."""


class WorkflowError(Exception):
    """Base exception for workflow errors."""

    pass


class ConfigurationError(WorkflowError):
    """Raised when workflow configuration is invalid."""

    pass


class ServiceNotFoundError(WorkflowError):
    """Raised when a requested service is not registered."""

    pass


class WorkflowExecutionError(WorkflowError):
    """Raised when workflow execution fails."""

    pass


class InputValidationError(WorkflowError):
    """Raised when input validation fails."""

    pass


class OutputError(WorkflowError):
    """Raised when output processing fails."""

    pass
