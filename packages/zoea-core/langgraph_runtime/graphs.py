"""LangGraph graph builders for Zoea execution."""

from __future__ import annotations

from typing import Callable

from .nodes import (
    build_inputs,
    collect_outputs,
    finalize_run,
    ingest_envelope,
    persist_outputs,
    route_trigger,
    run_agent,
    select_agent_profile,
    should_continue,
)
from .state import ExecutionState

GraphBuilder = Callable[[], object]


def build_default_graph() -> object:
    """Build a default LangGraph execution graph."""
    try:
        from langgraph.graph import END, StateGraph
    except ImportError as e:
        raise ImportError(
            "LangGraph is not installed. Add 'langgraph' to zoea-core dependencies."
        ) from e

    graph = StateGraph(ExecutionState)

    graph.add_node("ingest_envelope", ingest_envelope)
    graph.add_node("route_trigger", route_trigger)
    graph.add_node("build_inputs", build_inputs)
    graph.add_node("select_agent_profile", select_agent_profile)
    graph.add_node("run_agent", run_agent)
    graph.add_node("collect_outputs", collect_outputs)
    graph.add_node("persist_outputs", persist_outputs)
    graph.add_node("finalize_run", finalize_run)

    graph.set_entry_point("ingest_envelope")
    graph.add_edge("ingest_envelope", "route_trigger")
    graph.add_edge("route_trigger", "build_inputs")
    graph.add_edge("build_inputs", "select_agent_profile")
    graph.add_edge("select_agent_profile", "run_agent")

    graph.add_conditional_edges(
        "run_agent",
        should_continue,
        {
            "continue": "build_inputs",
            "retry": "run_agent",
            "done": "collect_outputs",
        },
    )

    graph.add_edge("collect_outputs", "persist_outputs")
    graph.add_edge("persist_outputs", "finalize_run")
    graph.add_edge("finalize_run", END)

    return graph


GRAPH_BUILDERS: dict[str, GraphBuilder] = {
    "default": build_default_graph,
}


def get_graph_builder(graph_id: str) -> GraphBuilder:
    """Resolve a graph builder by id."""
    if graph_id in GRAPH_BUILDERS:
        return GRAPH_BUILDERS[graph_id]
    raise KeyError(f"Unknown graph_id: {graph_id}")
