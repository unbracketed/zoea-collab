"""
LangGraph definition for project_activity_summary workflow.

This is the first LangGraph-native workflow in Zoea Collab.

Flow:
    gather_activity -> summarize_activity -> format_output -> END
"""

from langgraph.graph import END, StateGraph

from langgraph_runtime.state import ExecutionState
from workflows.builtin.project_activity_summary.nodes import (
    format_output,
    gather_activity,
    summarize_activity,
)


def build_graph() -> StateGraph:
    """
    Build the project_activity_summary LangGraph.

    The graph follows a linear flow:
    1. gather_activity - Query ExecutionRun, ChannelMessage, Document for recent activity
    2. summarize_activity - Use LLM to generate human-readable summary
    3. format_output - Format for output destination and create ExecutionOutput

    Returns:
        StateGraph configured and ready to compile
    """
    graph = StateGraph(ExecutionState)

    # Add nodes
    graph.add_node("gather_activity", gather_activity)
    graph.add_node("summarize_activity", summarize_activity)
    graph.add_node("format_output", format_output)

    # Define edges (linear flow)
    graph.set_entry_point("gather_activity")
    graph.add_edge("gather_activity", "summarize_activity")
    graph.add_edge("summarize_activity", "format_output")
    graph.add_edge("format_output", END)

    return graph
