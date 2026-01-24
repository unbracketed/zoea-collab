"""
Base node classes with enhanced context access for workflow nodes.

Provides convenience methods for accessing WorkflowContext within
workflow node lifecycle methods. Works with both LangGraph state
and legacy PocketFlow shared dict patterns.
"""

import asyncio
from typing import Any, Dict, Optional

from .context import WorkflowContext


class Node:
    """
    Minimal base node class for workflow execution.

    This is a standalone implementation that doesn't require PocketFlow.
    Nodes implement prep() -> run_action() -> post() lifecycle.
    """

    def prep(self, shared: Dict[str, Any]) -> Any:
        """Prepare data for execution. Override in subclass."""
        return None

    def run_action(self, prep_res: Any) -> Any:
        """Execute the node logic. Override in subclass."""
        return None

    def post(self, shared: Dict[str, Any], prep_res: Any, run_res: Any) -> str:
        """Post-process and return next action. Override in subclass."""
        return "default"

    def run(self, shared: Dict[str, Any]) -> str:
        """Run the full node lifecycle: prep -> run_action -> post."""
        prep_res = self.prep(shared)
        run_res = self.run_action(prep_res)
        return self.post(shared, prep_res, run_res)


class WorkflowNode(Node):
    """
    Base node class with convenience methods for context access.

    Extends PocketFlow's Node with helper methods that make it easier
    to work with WorkflowContext in the node lifecycle methods.

    Example:
        class MyNode(WorkflowNode):
            def prep(self, shared):
                # Get input values easily
                issue_num = self.input(shared, 'issue_number')
                # Get service instances
                gh = self.service(shared, 'gh')
                return gh.read_issue(issue_num)

            def run_action(self, issue_data):
                # Process the data
                return f"Issue: {issue_data['title']}"

            def post(self, shared, prep_res, run_res):
                # Store output
                self.set_output(shared, 'summary', run_res)
                return 'default'
    """

    def ctx(self, shared: Dict[str, Any]) -> WorkflowContext:
        """
        Get WorkflowContext from shared dict.

        Args:
            shared: The shared dict passed to node methods

        Returns:
            WorkflowContext instance
        """
        return WorkflowContext.from_shared_dict(shared)

    def input(self, shared: Dict[str, Any], name: str, default: Any = None) -> Any:
        """
        Get input value by name.

        Args:
            shared: The shared dict
            name: Input parameter name
            default: Default value if input not found

        Returns:
            Input value or default
        """
        ctx = self.ctx(shared)
        return ctx.inputs.get(name, default)

    def service(self, shared: Dict[str, Any], ref: str) -> Any:
        """
        Get service by context reference.

        Args:
            shared: The shared dict
            ref: Service context reference (e.g., 'gh', 'ai')

        Returns:
            Service instance
        """
        ctx = self.ctx(shared)
        return getattr(ctx.services, ref)

    def set_output(self, shared: Dict[str, Any], name: str, value: Any) -> None:
        """
        Set output value.

        Args:
            shared: The shared dict
            name: Output name
            value: Output value
        """
        ctx = self.ctx(shared)
        ctx.outputs.set(name, value)

    def set_state(self, shared: Dict[str, Any], key: str, value: Any) -> None:
        """
        Set state value for node-to-node communication.

        Args:
            shared: The shared dict
            key: State key
            value: State value
        """
        ctx = self.ctx(shared)
        ctx.state[key] = value

    def get_state(self, shared: Dict[str, Any], key: str, default: Any = None) -> Any:
        """
        Get state value.

        Args:
            shared: The shared dict
            key: State key
            default: Default value if key not found

        Returns:
            State value or default
        """
        ctx = self.ctx(shared)
        return ctx.state.get(key, default)


class AsyncWorkflowNode(WorkflowNode):
    """
    Node with async run support.

    Override async_run() for async operations. The standard PocketFlow
    method will automatically run async_run() using asyncio.run().

    This is useful for nodes that need to call async services like
    ChatAgentService.

    Example:
        class AINode(AsyncWorkflowNode):
            def _prep(self, shared):
                return "Generate a plan for..."

            async def async_run(self, prompt):
                # Can use await here
                ai = self.async_service('ai')
                return await ai.achat(prompt)

            def post(self, shared, prep_res, run_res):
                self.set_output(shared, 'plan', run_res)
                return 'default'
    """

    # Store shared reference for access in async_run
    _current_shared: Optional[Dict[str, Any]] = None

    # PocketFlow calls this method - we override it to bridge to async
    def __getattribute__(self, name):
        # Intercept the 'exec' attribute access to return our async bridge
        if name == "exec":
            return lambda prep_res: asyncio.run(self.async_run(prep_res))
        return super().__getattribute__(name)

    async def async_run(self, prep_res: Any) -> Any:
        """
        Override this method for async operations.

        Args:
            prep_res: Result from prep() method

        Returns:
            Result to be passed to post()
        """
        raise NotImplementedError("Subclasses must implement async_run()")

    def prep(self, shared: Dict[str, Any]) -> Any:
        """
        Store shared reference and call _prep().

        Override _prep() instead of prep() if you need to access
        shared in async_run().
        """
        self._current_shared = shared
        return self._prep(shared)

    def _prep(self, shared: Dict[str, Any]) -> Any:
        """
        Override this for prep logic.

        The shared dict is also available as self._current_shared
        for use in async_run().
        """
        return None

    def async_service(self, ref: str) -> Any:
        """
        Get service in async context using stored shared reference.

        Use this in async_run() when you need service access.

        Args:
            ref: Service context reference

        Returns:
            Service instance
        """
        if self._current_shared is None:
            raise RuntimeError("async_service() called outside of node run")
        return self.service(self._current_shared, ref)

    def async_ctx(self) -> WorkflowContext:
        """
        Get context in async context using stored shared reference.

        Use this in async_run() when you need context access.

        Returns:
            WorkflowContext instance
        """
        if self._current_shared is None:
            raise RuntimeError("async_ctx() called outside of node run")
        return self.ctx(self._current_shared)
