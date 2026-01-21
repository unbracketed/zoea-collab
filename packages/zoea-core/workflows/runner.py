"""
WorkflowRunner - async run engine for PocketFlow workflows.

Handles workflow orchestration including:
- Loading and validating workflow configuration
- Instantiating and binding services
- Building workflow context
- Running the PocketFlow flow
- Processing and persisting outputs
"""

import logging
import uuid
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Dict, Optional

from asgiref.sync import sync_to_async

from .config import interpolate_template, load_workflow_config
from .context import WorkflowContext
from .exceptions import WorkflowError
from .registry import ServiceRegistry, WorkflowRegistry, _import_flow_builder
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
    Run engine for PocketFlow workflows.

    Manages the complete lifecycle of workflow runs:
    1. Load workflow configuration
    2. Build context with inputs and Django context
    3. Instantiate and bind services
    4. Run the PocketFlow flow
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

        # Build context with inputs
        ctx = self._build_context(spec, inputs, run_id)

        # Bind services to context
        await self._bind_services(ctx, spec)

        # Get flow builder
        flow_builder = self._get_flow_builder(workflow_def, config_path, spec)

        # Build and run flow
        flow = flow_builder()
        shared = ctx.to_shared_dict()

        logger.debug(f"Running flow for workflow '{workflow_slug}'")

        # PocketFlow is synchronous - run in thread pool
        await sync_to_async(flow.run)(shared)

        # Process outputs
        results = await self._process_outputs(ctx, spec)

        logger.info(f"Workflow '{workflow_slug}' run {run_id} completed")

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

    def _get_flow_builder(
        self,
        workflow_def: Optional[Dict[str, Any]],
        config_path: Optional[Path],
        spec: WorkflowSpec,
    ) -> Callable:
        """
        Get the flow builder function for a workflow.

        Args:
            workflow_def: Workflow registry entry (if registered)
            config_path: Explicit config path (if provided)
            spec: Workflow specification

        Returns:
            Callable that returns a Flow instance
        """
        # Check registered flow builder
        if workflow_def and workflow_def.get("flow_builder"):
            return workflow_def["flow_builder"]

        # Try to import from workflow directory
        if config_path:
            workflow_dir = config_path.parent
        elif workflow_def:
            workflow_dir = Path(workflow_def["config_path"]).parent
        else:
            raise WorkflowError(f"Cannot locate flow builder for {spec.slug}")

        flow_module_path = workflow_dir / "flow.py"
        if flow_module_path.exists():
            return _import_flow_builder(flow_module_path)

        raise WorkflowError(f"No flow.py found for workflow {spec.slug}")

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
