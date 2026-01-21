"""
WorkflowContext - shared state wrapper integrating with PocketFlow.

Provides structured access to inputs, outputs, services, and Django context
while maintaining compatibility with PocketFlow's shared dictionary pattern.
"""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Dict, Iterator, Optional, Tuple

if TYPE_CHECKING:
    from django.contrib.auth.models import User

    from accounts.models import Account
    from projects.models import Project
    from workflows.types import OutputSpec
    from workspaces.models import Workspace


@dataclass
class ServiceContainer:
    """
    Container for service instances accessible via attribute access.

    Example:
        ctx.services.gh.read_issue(7)
        ctx.services.ai.chat("Hello")
    """

    _services: Dict[str, Any] = field(default_factory=dict)

    def __getattr__(self, name: str) -> Any:
        if name.startswith("_"):
            raise AttributeError(name)
        if name not in self._services:
            raise AttributeError(f"Service '{name}' not registered")
        return self._services[name]

    def register(self, ctxref: str, service: Any) -> None:
        """Register a service instance with a context reference name."""
        self._services[ctxref] = service

    def __contains__(self, name: str) -> bool:
        return name in self._services

    def items(self) -> Iterator[Tuple[str, Any]]:
        """Iterate over registered services."""
        return iter(self._services.items())


@dataclass
class InputContainer:
    """
    Container for input values accessible via attribute access.

    Example:
        ctx.inputs.issue_number
        ctx.inputs.get('issue_number', default=1)
    """

    _inputs: Dict[str, Any] = field(default_factory=dict)

    def __getattr__(self, name: str) -> Any:
        if name.startswith("_"):
            raise AttributeError(name)
        if name not in self._inputs:
            raise AttributeError(f"Input '{name}' not provided")
        return self._inputs[name]

    def __setattr__(self, name: str, value: Any) -> None:
        if name.startswith("_"):
            object.__setattr__(self, name, value)
        else:
            self._inputs[name] = value

    def get(self, name: str, default: Any = None) -> Any:
        """Get input value with optional default."""
        return self._inputs.get(name, default)

    def items(self) -> Iterator[Tuple[str, Any]]:
        """Iterate over input key-value pairs."""
        return iter(self._inputs.items())

    def keys(self) -> Iterator[str]:
        """Iterate over input keys."""
        return iter(self._inputs.keys())

    def to_dict(self) -> Dict[str, Any]:
        """Convert inputs to a plain dictionary."""
        return dict(self._inputs)


@dataclass
class OutputContainer:
    """
    Container for output values and specifications.

    Example:
        ctx.outputs.set('plan', content)
        ctx.outputs.get('plan')
    """

    _outputs: Dict[str, Any] = field(default_factory=dict)
    _specs: Dict[str, "OutputSpec"] = field(default_factory=dict)

    def set(self, name: str, value: Any) -> None:
        """Set an output value."""
        self._outputs[name] = value

    def get(self, name: str, default: Any = None) -> Any:
        """Get an output value."""
        return self._outputs.get(name, default)

    def items(self) -> Iterator[Tuple[str, Any]]:
        """Iterate over output key-value pairs."""
        return iter(self._outputs.items())

    def register_spec(self, name: str, spec: "OutputSpec") -> None:
        """Register an output specification."""
        self._specs[name] = spec

    def get_spec(self, name: str) -> Optional["OutputSpec"]:
        """Get output specification by name."""
        return self._specs.get(name)

    def specs(self) -> Iterator[Tuple[str, "OutputSpec"]]:
        """Iterate over output specifications."""
        return iter(self._specs.items())


@dataclass
class WorkflowContext:
    """
    Shared state container for workflow execution.

    Integrates with PocketFlow's shared dictionary pattern while providing
    structured access to inputs, outputs, services, and Django context.

    Usage in nodes:
        def prep(self, shared):
            ctx = shared['ctx']
            issue_num = ctx.inputs.issue_number
            gh = ctx.services.gh
            return gh.read_issue(issue_num)

        def post(self, shared, prep_res, exec_res):
            ctx = shared['ctx']
            ctx.outputs.set('plan', exec_res)
            ctx.state['plan_generated'] = True
            return 'default'
    """

    # Structured containers
    inputs: InputContainer = field(default_factory=InputContainer)
    outputs: OutputContainer = field(default_factory=OutputContainer)
    services: ServiceContainer = field(default_factory=ServiceContainer)

    # Arbitrary state for node-to-node communication
    state: Dict[str, Any] = field(default_factory=dict)

    # Django context (set by runner)
    organization: Optional["Account"] = None
    project: Optional["Project"] = None
    workspace: Optional["Workspace"] = None
    user: Optional["User"] = None

    # Workflow metadata
    workflow_slug: str = ""
    run_id: Optional[str] = None

    def to_shared_dict(self) -> Dict[str, Any]:
        """
        Convert to PocketFlow shared dictionary format.

        Returns a dict that can be passed to PocketFlow's Flow.run().
        The context is accessible via shared['ctx'].
        """
        return {
            "ctx": self,
            # Legacy compatibility accessors (for nodes that access shared directly)
            "inputs": self.inputs.to_dict(),
            "outputs": {},
            "state": self.state,
        }

    @classmethod
    def from_shared_dict(cls, shared: Dict[str, Any]) -> "WorkflowContext":
        """
        Extract context from PocketFlow shared dictionary.

        Args:
            shared: The shared dict passed to node methods

        Returns:
            WorkflowContext instance
        """
        ctx = shared.get("ctx")
        if isinstance(ctx, cls):
            return ctx
        # Fallback: create new context (shouldn't happen in normal usage)
        return cls()
