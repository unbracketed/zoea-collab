"""LangGraph runtime helpers for executing graphs."""

from __future__ import annotations

import logging
from typing import Any, Callable

from asgiref.sync import sync_to_async

from .state import ExecutionState

logger = logging.getLogger(__name__)


async def run_graph(
    graph_builder: Callable[[], object],
    state: ExecutionState,
    *,
    checkpointer: Any | None = None,
) -> ExecutionState:
    """Build and execute a LangGraph graph with the provided state."""
    graph = graph_builder()

    # Compile if the builder returns a StateGraph
    if hasattr(graph, "compile"):
        if checkpointer is not None:
            graph = graph.compile(checkpointer=checkpointer)
        else:
            graph = graph.compile()

    if hasattr(graph, "ainvoke"):
        result = await graph.ainvoke(state)
        return result

    if hasattr(graph, "invoke"):
        return await sync_to_async(graph.invoke)(state)

    logger.error("Graph builder returned unsupported object: %s", type(graph))
    raise TypeError("Unsupported graph object returned from graph_builder")
