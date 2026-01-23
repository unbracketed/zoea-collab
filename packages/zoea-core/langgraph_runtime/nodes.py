"""Default LangGraph node scaffolding for Zoea execution."""

from __future__ import annotations

from typing import Any

from .state import ExecutionOutput, ExecutionState


def ingest_envelope(state: ExecutionState) -> dict[str, Any]:
    """Normalize incoming envelope. Placeholder for adapter-specific coercion."""
    return {}


def route_trigger(state: ExecutionState) -> dict[str, Any]:
    """Route trigger to a graph/pattern. Placeholder for TriggerRouter."""
    return {}


def build_inputs(state: ExecutionState) -> dict[str, Any]:
    """Map envelope to workflow inputs. Placeholder for input mapping rules."""
    return {}


def select_agent_profile(state: ExecutionState) -> dict[str, Any]:
    """Select agent profile (tools, skills, model, runtime)."""
    return {}


def run_agent(state: ExecutionState) -> dict[str, Any]:
    """Execute agent runtime. Placeholder for docker/local runtimes."""
    # Ensure outputs list exists to simplify downstream steps.
    outputs = list(state.get("outputs", []))
    return {"outputs": outputs, "should_continue": False, "retryable_error": False}


def collect_outputs(state: ExecutionState) -> dict[str, Any]:
    """Collect artifacts and translate into ExecutionOutputs."""
    outputs = list(state.get("outputs", []))
    return {"outputs": outputs}


def persist_outputs(state: ExecutionState) -> dict[str, Any]:
    """Persist outputs (documents/messages/webhooks)."""
    return {}


def finalize_run(state: ExecutionState) -> dict[str, Any]:
    """Finalize run bookkeeping."""
    return {"status": "completed"}


def should_continue(state: ExecutionState) -> str:
    """Conditional edge selector for run_agent."""
    if state.get("retryable_error"):
        return "retry"
    if state.get("should_continue"):
        return "continue"
    return "done"


def ensure_output_value(
    state: ExecutionState, name: str, value: Any
) -> dict[str, Any]:
    """Helper to populate output_values from nodes."""
    output_values = dict(state.get("output_values", {}))
    output_values[name] = value
    return {"output_values": output_values}


def append_output(state: ExecutionState, output: ExecutionOutput) -> dict[str, Any]:
    """Helper to append an ExecutionOutput entry."""
    outputs = list(state.get("outputs", []))
    outputs.append(output)
    return {"outputs": outputs}
