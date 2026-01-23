"""
WorkflowRunner - async run engine for LangGraph workflows.

Handles workflow orchestration including:
- Loading and validating workflow configuration
- Instantiating and binding services
- Building execution state
- Running the LangGraph graph
- Processing and persisting outputs
"""

import logging
import uuid
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Dict, Optional

from asgiref.sync import sync_to_async

from .config import interpolate_template, load_workflow_config
from langgraph_runtime.runtime import run_graph
from langgraph_runtime.state import ExecutionState

from .context import WorkflowContext
from .exceptions import WorkflowError
from .registry import (
    ServiceRegistry,
    WorkflowRegistry,
    _import_flow_builder,
    _import_graph_builder,
)
from .services.documents import DocumentService
from .types import WorkflowSpec

if TYPE_CHECKING:
    from django.contrib.auth.models import User

    from accounts.models import Account
    from projects.models import Project
    from workspaces.models import Workspace

logger = logging.getLogger(__name__)


class WorkflowRunner:
    """
    Run engine for LangGraph workflows.

    Manages the complete lifecycle of workflow runs:
    1. Load workflow configuration
    2. Build execution state with inputs and Django context
    3. Instantiate and bind services
    4. Run the LangGraph graph
    5. Process outputs (create documents, etc.)

    Example:
        runner = WorkflowRunner(organization, project, workspace, user)
        result = await runner.run('plan-github-issue', {'issue_number': 7})
    """

    def __init__(
        self,
        organization: "Account",
        project: "Project",
        workspace: "Workspace",
        user: "User",
    ):
        """
        Initialize workflow runner with Django context.

        Args:
            organization: Organization for scoping outputs
            project: Project for scoping outputs
            workspace: Workspace for scoping outputs
            user: User running the workflow
        """
        self.organization = organization
        self.project = project
        self.workspace = workspace
        self.user = user
        self.service_registry = ServiceRegistry.get_instance()

    async def run(
        self,
        workflow_slug: str,
        inputs: Dict[str, Any],
        config_path: Optional[Path] = None,
    ) -> Dict[str, Any]:
        """
        Run a workflow asynchronously.

        Args:
            workflow_slug: Workflow identifier (e.g., 'plan_github_issue')
            inputs: Input values dict
            config_path: Optional explicit config path override

        Returns:
            Dict with:
            - run_id: Unique run identifier
            - workflow: Workflow slug
            - outputs: Dict of output results
            - state: Final workflow state

        Raises:
            WorkflowError: If workflow not found or run fails
        """
        run_id = str(uuid.uuid4())[:8]
        logger.info(f"Starting workflow '{workflow_slug}' run {run_id}")

        # Load workflow definition
        workflow_def = WorkflowRegistry.get_instance().get(workflow_slug)

        if config_path:
            spec = load_workflow_config(config_path)
        elif workflow_def:
            spec = load_workflow_config(Path(workflow_def["config_path"]))
        else:
            raise WorkflowError(f"Workflow not found: {workflow_slug}")

        # Build execution state with inputs
        state = self._build_state(spec, inputs, run_id, workflow_def)

        # Bind services to state
        await self._bind_services_to_state(state, spec)

        # Get graph builder (preferred)
        graph_builder = self._get_graph_builder(workflow_def, config_path, spec)

        if graph_builder is not None:
            logger.debug(f"Running LangGraph for workflow '{workflow_slug}'")
            final_state = await run_graph(graph_builder, state)
            results = await self._process_outputs_from_state(final_state, spec)

            logger.info(f"Workflow '{workflow_slug}' run {run_id} completed")
            return {
                "run_id": run_id,
                "workflow": workflow_slug,
                "outputs": results,
                "state": final_state,
            }

        # Fallback to legacy PocketFlow flows when present
        legacy_flow_builder = self._get_legacy_flow_builder(
            workflow_def, config_path, spec
        )
        if legacy_flow_builder is None:
            raise WorkflowError(
                f"No LangGraph graph available for workflow {workflow_slug}"
            )

        logger.warning(
            "Using legacy PocketFlow flow for workflow '%s'. "
            "Migrate to graph.py with build_graph().",
            workflow_slug,
        )

        ctx = self._build_context(spec, inputs, run_id)
        await self._bind_services(ctx, spec)
        flow = legacy_flow_builder()
        shared = ctx.to_shared_dict()
        await sync_to_async(flow.run)(shared)
        results = await self._process_outputs(ctx, spec)

        logger.info(f"Workflow '{workflow_slug}' run {run_id} completed (legacy)")
        return {
            "run_id": run_id,
            "workflow": workflow_slug,
            "outputs": results,
            "state": ctx.state,
        }

    def _build_context(
        self,
        spec: WorkflowSpec,
        inputs: Dict[str, Any],
        run_id: str,
    ) -> WorkflowContext:
        """
        Build workflow context with validated inputs.

        Args:
            spec: Workflow specification
            inputs: Raw input values
            run_id: Unique run identifier

        Returns:
            Configured WorkflowContext

        Raises:
            WorkflowError: If input validation fails
        """
        ctx = WorkflowContext(
            organization=self.organization,
            project=self.project,
            workspace=self.workspace,
            user=self.user,
            workflow_slug=spec.slug,
            run_id=run_id,
        )

        # Validate and set inputs
        for input_spec in spec.inputs:
            raw_value = inputs.get(input_spec.name)

            try:
                validated_value = input_spec.validate_value(raw_value)
                if validated_value is not None:
                    setattr(ctx.inputs, input_spec.name, validated_value)
            except ValueError as e:
                raise WorkflowError(str(e))

        # Register output specs
        for output_spec in spec.outputs:
            ctx.outputs.register_spec(output_spec.name, output_spec)

        logger.debug(f"Built context with {len(spec.inputs)} inputs")
        return ctx

    def _build_state(
        self,
        spec: WorkflowSpec,
        inputs: Dict[str, Any],
        run_id: str,
        workflow_def: Optional[Dict[str, Any]],
    ) -> ExecutionState:
        """
        Build LangGraph execution state with validated inputs.

        Args:
            spec: Workflow specification
            inputs: Raw input values
            run_id: Unique run identifier
            workflow_def: Workflow registry entry (if registered)

        Returns:
            ExecutionState dictionary
        """
        validated_inputs: Dict[str, Any] = {}
        for input_spec in spec.inputs:
            raw_value = inputs.get(input_spec.name)
            try:
                validated_value = input_spec.validate_value(raw_value)
                if validated_value is not None:
                    validated_inputs[input_spec.name] = validated_value
            except ValueError as e:
                raise WorkflowError(str(e))

        graph_id = spec.graph_id or spec.slug
        if workflow_def and workflow_def.get("graph_id"):
            graph_id = workflow_def["graph_id"] or graph_id

        state: ExecutionState = {
            "run_id": run_id,
            "status": "running",
            "envelope": inputs.get("envelope"),
            "input_map": {},
            "inputs": validated_inputs,
            "graph_id": graph_id,
            "outputs": [],
            "output_values": {},
            "artifacts": [],
            "workflow_state": {},
            "steps": [],
            "telemetry": {},
            "context": {
                "organization_id": self.organization.id,
                "project_id": self.project.id if self.project else None,
                "workspace_id": self.workspace.id if self.workspace else None,
                "user_id": self.user.id,
                "workflow_slug": spec.slug,
            },
        }

        logger.debug("Built execution state with %s inputs", len(spec.inputs))
        return state

    async def _bind_services(
        self,
        ctx: WorkflowContext,
        spec: WorkflowSpec,
    ) -> None:
        """
        Instantiate and bind services to context.

        Args:
            ctx: Workflow context
            spec: Workflow specification
        """
        for svc_spec in spec.services:
            try:
                service = self.service_registry.create(
                    svc_spec.name,
                    svc_spec.config,
                )
                ctx.services.register(svc_spec.ctxref, service)
                logger.debug(f"Bound service {svc_spec.name} as '{svc_spec.ctxref}'")
            except Exception as e:
                raise WorkflowError(f"Failed to instantiate service {svc_spec.name}: {e}")

    async def _bind_services_to_state(
        self,
        state: ExecutionState,
        spec: WorkflowSpec,
    ) -> None:
        """
        Instantiate and bind services to execution state.

        Args:
            state: LangGraph execution state
            spec: Workflow specification
        """
        services: Dict[str, Any] = {}
        for svc_spec in spec.services:
            try:
                service = self.service_registry.create(
                    svc_spec.name,
                    svc_spec.config,
                )
                services[svc_spec.ctxref] = service
                logger.debug(
                    "Bound service %s as '%s' (state)",
                    svc_spec.name,
                    svc_spec.ctxref,
                )
            except Exception as e:
                raise WorkflowError(f"Failed to instantiate service {svc_spec.name}: {e}")

        state["services"] = services

    def _get_graph_builder(
        self,
        workflow_def: Optional[Dict[str, Any]],
        config_path: Optional[Path],
        spec: WorkflowSpec,
    ) -> Optional[Callable]:
        """
        Get the LangGraph builder function for a workflow.

        Args:
            workflow_def: Workflow registry entry (if registered)
            config_path: Explicit config path (if provided)
            spec: Workflow specification

        Returns:
            Callable that returns a LangGraph graph
        """
        # Check registered graph builder
        if workflow_def and workflow_def.get("graph_builder"):
            return workflow_def["graph_builder"]

        # Try to import from workflow directory
        if config_path:
            workflow_dir = config_path.parent
        elif workflow_def:
            workflow_dir = Path(workflow_def["config_path"]).parent
        else:
            raise WorkflowError(f"Cannot locate graph builder for {spec.slug}")

        graph_module_path = workflow_dir / "graph.py"
        if graph_module_path.exists():
            return _import_graph_builder(graph_module_path)

        return None

    def _get_legacy_flow_builder(
        self,
        workflow_def: Optional[Dict[str, Any]],
        config_path: Optional[Path],
        spec: WorkflowSpec,
    ) -> Callable | None:
        """
        Get legacy PocketFlow builder for a workflow.

        Returns:
            Callable that returns a Flow instance, or None.
        """
        if workflow_def and workflow_def.get("legacy_flow_builder"):
            return workflow_def["legacy_flow_builder"]

        if config_path:
            workflow_dir = config_path.parent
        elif workflow_def:
            workflow_dir = Path(workflow_def["config_path"]).parent
        else:
            return None

        flow_module_path = workflow_dir / "flow.py"
        if flow_module_path.exists():
            return _import_flow_builder(flow_module_path)

        return None

    async def _process_outputs(
        self,
        ctx: WorkflowContext,
        spec: WorkflowSpec,
    ) -> Dict[str, Any]:
        """
        Process workflow outputs - create documents, etc.

        Args:
            ctx: Workflow context with output values
            spec: Workflow specification

        Returns:
            Dict of output results
        """
        doc_service = DocumentService(
            organization=self.organization,
            project=self.project,
            workspace=self.workspace,
            user=self.user,
        )

        results = {}
        input_values = ctx.inputs.to_dict()

        for output_spec in spec.outputs:
            # Get output value from context
            output_key = output_spec.name
            content = ctx.outputs.get(output_key)

            # Also check state for backwards compatibility
            if content is None:
                # Try to find in state by partial key match
                for state_key, state_value in ctx.state.items():
                    if isinstance(state_value, str) and len(state_value) > 100:
                        # Assume large strings are generated content
                        content = state_value
                        break

            if content is None:
                logger.warning(f"Output '{output_key}' not found in context")
                continue

            # Interpolate name and target with input values
            try:
                name = interpolate_template(output_spec.name, input_values)
                target = None
                if output_spec.target:
                    target = interpolate_template(output_spec.target, input_values)
            except Exception as e:
                logger.error(f"Failed to interpolate output template: {e}")
                continue

            # Create document based on output type
            if output_spec.type == "MarkdownDocument":
                try:
                    doc = await doc_service.create_markdown(
                        name=name,
                        content=content,
                        folder_path=target,
                    )
                    results[output_key] = {
                        "type": "MarkdownDocument",
                        "id": doc.id,
                        "name": doc.name,
                        "folder": target,
                    }
                    logger.info(f"Created output document: {doc.name}")
                except Exception as e:
                    logger.error(f"Failed to create output document: {e}")
                    results[output_key] = {
                        "type": "MarkdownDocument",
                        "error": str(e),
                    }
            else:
                logger.warning(f"Unsupported output type: {output_spec.type}")
                results[output_key] = {
                    "type": output_spec.type,
                    "content": content[:200] if isinstance(content, str) else str(content),
                }

        return results

    async def _process_outputs_from_state(
        self,
        state: ExecutionState,
        spec: WorkflowSpec,
    ) -> Dict[str, Any]:
        """
        Process workflow outputs from LangGraph state.

        Args:
            state: LangGraph execution state with output values
            spec: Workflow specification

        Returns:
            Dict of output results
        """
        doc_service = DocumentService(
            organization=self.organization,
            project=self.project,
            workspace=self.workspace,
            user=self.user,
        )

        results: Dict[str, Any] = {}
        input_values = state.get("inputs", {})
        output_values = state.get("output_values", {}) or {}
        outputs_list = state.get("outputs", []) or []

        for output_spec in spec.outputs:
            output_key = output_spec.name
            content = output_values.get(output_key)

            if content is None:
                # Try to find a matching output entry by name
                for output in outputs_list:
                    payload = output.get("payload", {}) if isinstance(output, dict) else {}
                    if payload.get("name") == output_key:
                        content = payload.get("content")
                        break

            if content is None:
                # Last-resort heuristic: large string value in state
                for state_value in state.values():
                    if isinstance(state_value, str) and len(state_value) > 100:
                        content = state_value
                        break

            if content is None:
                logger.warning(f"Output '{output_key}' not found in state")
                continue

            try:
                name = interpolate_template(output_spec.name, input_values)
                target = None
                if output_spec.target:
                    target = interpolate_template(output_spec.target, input_values)
            except Exception as e:
                logger.error(f"Failed to interpolate output template: {e}")
                continue

            if output_spec.type == "MarkdownDocument":
                try:
                    doc = await doc_service.create_markdown(
                        name=name,
                        content=content,
                        folder_path=target,
                    )
                    results[output_key] = {
                        "type": "MarkdownDocument",
                        "id": doc.id,
                        "name": doc.name,
                        "folder": target,
                    }
                    logger.info(f"Created output document: {doc.name}")
                except Exception as e:
                    logger.error(f"Failed to create output document: {e}")
                    results[output_key] = {
                        "type": "MarkdownDocument",
                        "error": str(e),
                    }
            else:
                logger.warning(f"Unsupported output type: {output_spec.type}")
                results[output_key] = {
                    "type": output_spec.type,
                    "content": content[:200] if isinstance(content, str) else str(content),
                }

        return results


def run_workflow_sync(
    workflow_slug: str,
    inputs: Dict[str, Any],
    organization: "Account",
    project: "Project",
    workspace: "Workspace",
    user: "User",
    config_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """
    Convenience function to run a workflow synchronously.

    Args:
        workflow_slug: Workflow identifier
        inputs: Input values
        organization: Organization for scoping
        project: Project for scoping
        workspace: Workspace for scoping
        user: User running the workflow
        config_path: Optional explicit config path

    Returns:
        Workflow run result
    """
    import asyncio

    runner = WorkflowRunner(organization, project, workspace, user)
    return asyncio.run(runner.run(workflow_slug, inputs, config_path))
