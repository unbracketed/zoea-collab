"""
Telemetry helpers for smolagents runs used by Document RAG.

This module focuses on extracting lightweight, non-content metrics from
smolagents RunResult/step dictionaries for later debugging/monitoring.
"""

from __future__ import annotations

from collections import Counter
from typing import Any


def summarize_smolagents_run(run_result: Any) -> dict[str, Any]:
    """
    Build a minimal telemetry summary from a smolagents RunResult.

    The intent is to capture operational metrics (duration, token usage, tool usage),
    without storing prompts/responses.
    """
    if run_result is None:
        return {"state": "unknown"}

    steps: list[dict[str, Any]] = getattr(run_result, "steps", None) or []
    state = getattr(run_result, "state", "unknown")

    timing_obj = getattr(run_result, "timing", None)
    token_usage_obj = getattr(run_result, "token_usage", None)

    tool_names: list[str] = []
    error_count = 0

    for step in steps:
        if not isinstance(step, dict):
            continue
        if step.get("error"):
            error_count += 1
        for tool_call in step.get("tool_calls") or []:
            try:
                name = tool_call.get("function", {}).get("name")
            except AttributeError:
                name = None
            if name:
                tool_names.append(str(name))

    tool_counts = Counter(tool_names)

    return {
        "state": state,
        "timing": getattr(timing_obj, "dict", lambda: None)(),
        "token_usage": getattr(token_usage_obj, "dict", lambda: None)(),
        "steps": {
            "count": len(steps),
            "error_count": error_count,
            "tool_calls_by_name": dict(tool_counts),
        },
    }

