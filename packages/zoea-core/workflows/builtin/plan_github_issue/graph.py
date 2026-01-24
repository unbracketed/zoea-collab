"""LangGraph wrapper for plan_github_issue using existing workflow nodes."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from langgraph.graph import END, StateGraph

from langgraph_runtime.state import ExecutionState
from workflows.config import load_workflow_config
from workflows.context import WorkflowContext
from workflows.types import WorkflowSpec

from .nodes import PlanIssue, ReadGithubIssue

_CONFIG_PATH = Path(__file__).parent / "flow-config.yaml"
_WORKFLOW_SPEC: WorkflowSpec = load_workflow_config(_CONFIG_PATH)


def _build_context(state: ExecutionState) -> WorkflowContext:
    """Build a WorkflowContext from LangGraph state."""
    context = state.get("context") or {}
    organization = None
    project = None

    try:
        from accounts.models import Account
        from projects.models import Project

        org_id = context.get("organization_id")
        if org_id:
            organization = Account.objects.get(id=org_id)

        project_id = context.get("project_id")
        if project_id:
            project = Project.objects.get(id=project_id)

    except Exception:
        # Context objects are optional for graph execution; scoped queries will fallback.
        pass

    ctx = WorkflowContext(
        organization=organization,
        project=project,
        workspace=None,  # Workspace is being deprecated
        user=None,
        workflow_slug=_WORKFLOW_SPEC.slug,
        run_id=state.get("run_id"),
    )

    for name, value in (state.get("inputs") or {}).items():
        setattr(ctx.inputs, name, value)

    for output_spec in _WORKFLOW_SPEC.outputs:
        ctx.outputs.register_spec(output_spec.name, output_spec)

    for ctxref, service in (state.get("services") or {}).items():
        ctx.services.register(ctxref, service)

    ctx.state = dict(state.get("workflow_state") or {})
    return ctx


def _output_values_from_ctx(ctx: WorkflowContext) -> Dict[str, Any]:
    return {name: value for name, value in ctx.outputs.items()}


def _read_github_issue(state: ExecutionState) -> Dict[str, Any]:
    """Read GitHub issue data node."""
    ctx = _build_context(state)
    shared = ctx.to_shared_dict()
    node = ReadGithubIssue()

    prep_res = node.prep(shared)
    node.post(shared, prep_res, None)

    return {
        "workflow_state": ctx.state,
        "output_values": _output_values_from_ctx(ctx),
    }


async def _plan_issue(state: ExecutionState) -> Dict[str, Any]:
    """Generate implementation plan using AI."""
    ctx = _build_context(state)
    shared = ctx.to_shared_dict()
    node = PlanIssue()

    prep_res = node.prep(shared)
    run_res = await node.async_run(prep_res)
    node.post(shared, prep_res, run_res)

    return {
        "workflow_state": ctx.state,
        "output_values": _output_values_from_ctx(ctx),
    }


def build_graph() -> StateGraph:
    """Build LangGraph for plan_github_issue workflow."""
    graph = StateGraph(ExecutionState)

    graph.add_node("read_github_issue", _read_github_issue)
    graph.add_node("plan_issue", _plan_issue)

    graph.set_entry_point("read_github_issue")
    graph.add_edge("read_github_issue", "plan_issue")
    graph.add_edge("plan_issue", END)

    return graph
