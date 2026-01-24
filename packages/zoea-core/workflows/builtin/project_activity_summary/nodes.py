"""
Node implementations for project_activity_summary workflow.

Gathers activity data from ExecutionRun, ChannelMessage, and Document models,
summarizes with LLM, and formats output for dispatch.
"""

from datetime import timedelta
from typing import Any

from django.db.models import Avg, Count, Q, Sum
from django.utils import timezone

from langgraph_runtime.state import ExecutionOutput, ExecutionState


def gather_activity(state: ExecutionState) -> dict[str, Any]:
    """
    Query recent activity from ExecutionRun, ChannelMessage, and Document models.

    Reads lookback_hours from inputs and queries all relevant models for activity
    within that time window.
    """
    from channels.models import ChannelMessage
    from documents.models import Document
    from execution.models import ExecutionRun

    ctx = state.get("context", {})
    org_id = ctx.get("organization_id")
    project_id = ctx.get("project_id")
    inputs = state.get("inputs", {})

    lookback_hours = inputs.get("lookback_hours", 24)
    since = timezone.now() - timedelta(hours=lookback_hours)

    # Build base filters
    base_filter = {"organization_id": org_id}
    if project_id:
        base_filter["project_id"] = project_id

    # --- ExecutionRun activity ---
    runs = ExecutionRun.objects.filter(**base_filter, created_at__gte=since)

    run_stats = runs.aggregate(
        total=Count("id"),
        completed=Count("id", filter=Q(status="completed")),
        failed=Count("id", filter=Q(status="failed")),
        pending=Count("id", filter=Q(status="pending")),
        running=Count("id", filter=Q(status="running")),
        total_tokens=Sum("token_usage__total"),
    )

    # Calculate average duration for completed runs
    completed_runs = runs.filter(
        status="completed",
        started_at__isnull=False,
        completed_at__isnull=False,
    )
    durations = []
    for run in completed_runs[:100]:  # Limit for performance
        if run.duration_seconds:
            durations.append(run.duration_seconds)
    avg_duration = sum(durations) / len(durations) if durations else None

    runs_by_trigger_type = list(
        runs.exclude(trigger_type="")
        .values("trigger_type")
        .annotate(count=Count("id"))
        .order_by("-count")
    )

    runs_by_workflow = list(
        runs.exclude(workflow_slug__isnull=True)
        .exclude(workflow_slug="")
        .values("workflow_slug")
        .annotate(count=Count("id"))
        .order_by("-count")[:5]
    )

    # Get recent failures for detail
    recent_failures = list(
        runs.filter(status="failed")
        .order_by("-created_at")[:5]
        .values("run_id", "workflow_slug", "trigger_type", "error", "created_at")
    )

    # --- ChannelMessage activity ---
    msg_filter = {"organization_id": org_id, "created_at__gte": since}
    if project_id:
        msg_filter["channel__project_id"] = project_id

    messages = ChannelMessage.objects.filter(**msg_filter)

    message_stats = messages.aggregate(
        total=Count("id"),
        user_messages=Count("id", filter=Q(role="user")),
        assistant_messages=Count("id", filter=Q(role="assistant")),
    )

    active_channels = list(
        messages.values("channel__display_name", "channel__adapter_type")
        .annotate(count=Count("id"))
        .order_by("-count")[:5]
    )

    # --- Document activity ---
    doc_filter = {"organization_id": org_id}
    if project_id:
        doc_filter["project_id"] = project_id

    docs_created = Document.objects.filter(**doc_filter, created_at__gte=since)
    docs_modified = Document.objects.filter(
        **doc_filter,
        updated_at__gte=since,
        created_at__lt=since,  # Modified, not created
    )

    # Get document type breakdown using ContentType
    # Document uses multi-table inheritance, so we check which subclass tables have records
    from django.contrib.contenttypes.models import ContentType

    doc_type_counts = []
    doc_ids = list(docs_created.values_list("id", flat=True)[:100])

    if doc_ids:
        # Check common document types
        doc_types = ["textdocument", "markdown", "image", "pdf", "filedocument"]
        for dtype in doc_types:
            ct = ContentType.objects.filter(model=dtype).first()
            if ct:
                model_class = ct.model_class()
                if model_class:
                    count = model_class.objects.filter(document_ptr_id__in=doc_ids).count()
                    if count > 0:
                        doc_type_counts.append({"doc_type": dtype, "count": count})

    doc_stats = {
        "created": docs_created.count(),
        "modified": docs_modified.count(),
        "by_type": sorted(doc_type_counts, key=lambda x: -x["count"]),
    }

    # Store activity data in workflow_state
    workflow_state = dict(state.get("workflow_state", {}))
    workflow_state["activity_data"] = {
        "period": {
            "since": since.isoformat(),
            "until": timezone.now().isoformat(),
            "hours": lookback_hours,
        },
        "executions": {
            "stats": run_stats,
            "avg_duration_seconds": avg_duration,
            "by_trigger_type": runs_by_trigger_type,
            "by_workflow": runs_by_workflow,
            "recent_failures": recent_failures,
        },
        "messages": {
            "stats": message_stats,
            "active_channels": active_channels,
        },
        "documents": doc_stats,
    }

    return {"workflow_state": workflow_state}


def summarize_activity(state: ExecutionState) -> dict[str, Any]:
    """
    Use LLM to generate human-readable summary from gathered activity data.
    """
    workflow_state = state.get("workflow_state", {})
    activity = workflow_state.get("activity_data", {})
    services = state.get("services", {})
    ai_service = services.get("ai")

    if not activity:
        workflow_state["summary_text"] = "No activity data available to summarize."
        return {"workflow_state": workflow_state}

    exec_stats = activity.get("executions", {}).get("stats", {})
    msg_stats = activity.get("messages", {}).get("stats", {})
    doc_stats = activity.get("documents", {})
    period = activity.get("period", {})

    # Build prompt for summarization
    prompt = f"""Summarize the following project activity data into a concise, human-readable summary.
Focus on key highlights, trends, and any notable events or concerns.

Activity Period: {period.get('hours', 24)} hours

## Execution Activity
- Total runs: {exec_stats.get('total', 0)}
- Completed: {exec_stats.get('completed', 0)}
- Failed: {exec_stats.get('failed', 0)}
- Pending: {exec_stats.get('pending', 0)}
- Running: {exec_stats.get('running', 0)}
- Average duration: {activity.get('executions', {}).get('avg_duration_seconds', 'N/A')} seconds
- By trigger type: {activity.get('executions', {}).get('by_trigger_type', [])}
- Top workflows: {activity.get('executions', {}).get('by_workflow', [])}

## Messaging Activity
- Total messages: {msg_stats.get('total', 0)}
- User messages: {msg_stats.get('user_messages', 0)}
- Assistant messages: {msg_stats.get('assistant_messages', 0)}
- Active channels: {activity.get('messages', {}).get('active_channels', [])}

## Document Activity
- Documents created: {doc_stats.get('created', 0)}
- Documents modified: {doc_stats.get('modified', 0)}
- By type: {doc_stats.get('by_type', [])}

## Recent Failures
{_format_failures(activity.get('executions', {}).get('recent_failures', []))}

Write a brief summary (3-5 paragraphs) highlighting:
1. Overall activity level and health
2. Most active areas (workflows, channels)
3. Any concerns (failures, errors) with recommendations
4. Notable achievements or trends
"""

    if ai_service is None:
        workflow_state["summary_text"] = _generate_fallback_summary(activity)
        return {"workflow_state": workflow_state}

    # Call AI service
    try:
        ai_service.configure_agent(
            name="ActivitySummarizer",
            instructions=(
                "You are an expert at summarizing project activity data. "
                "Create clear, actionable summaries that highlight important patterns "
                "and concerns. Always output in Markdown format."
            ),
        )
        summary = ai_service.chat(prompt)
        workflow_state["summary_text"] = summary
    except Exception as e:
        workflow_state["summary_text"] = (
            f"Error generating AI summary: {e}\n\n"
            f"{_generate_fallback_summary(activity)}"
        )

    return {"workflow_state": workflow_state}


def format_output(state: ExecutionState) -> dict[str, Any]:
    """
    Format the summary for output, optionally including metrics section.
    """
    workflow_state = state.get("workflow_state", {})
    activity = workflow_state.get("activity_data", {})
    summary = workflow_state.get("summary_text", "")
    inputs = state.get("inputs", {})

    include_metrics = inputs.get("include_metrics", True)
    include_failures = inputs.get("include_failures", True)
    output_format = inputs.get("output_format", "markdown")

    period = activity.get("period", {})
    exec_stats = activity.get("executions", {}).get("stats", {})
    msg_stats = activity.get("messages", {}).get("stats", {})
    doc_stats = activity.get("documents", {})

    # Format based on output type
    if output_format == "slack":
        header = (
            f":bar_chart: *Project Activity Summary*\n"
            f"_{period.get('hours', 24)}h period ending {period.get('until', '')[:10]}_\n\n"
        )
    else:
        header = (
            f"# Project Activity Summary\n\n"
            f"**Period:** {period.get('hours', 24)} hours ending {period.get('until', '')[:10]}\n\n"
        )

    metrics_section = ""
    if include_metrics:
        completed = exec_stats.get("completed", 0)
        failed = exec_stats.get("failed", 0)

        if output_format == "slack":
            metrics_section = f"""*Quick Stats:*
- Executions: {exec_stats.get('total', 0)} ({completed} :white_check_mark: / {failed} :x:)
- Messages: {msg_stats.get('total', 0)}
- Documents: {doc_stats.get('created', 0)} created, {doc_stats.get('modified', 0)} modified

"""
        else:
            metrics_section = f"""## Quick Stats

| Metric | Value |
|--------|-------|
| Executions | {exec_stats.get('total', 0)} ({completed} completed, {failed} failed) |
| Messages | {msg_stats.get('total', 0)} |
| Documents Created | {doc_stats.get('created', 0)} |
| Documents Modified | {doc_stats.get('modified', 0)} |

"""

    failures_section = ""
    if include_failures:
        recent_failures = activity.get("executions", {}).get("recent_failures", [])
        if recent_failures:
            if output_format == "slack":
                failures_section = "\n*Recent Failures:*\n"
                for f in recent_failures[:3]:
                    failures_section += f"- `{f.get('run_id', '')[:8]}` {f.get('workflow_slug', 'unknown')}: {f.get('error', 'No error message')[:100]}\n"
            else:
                failures_section = "\n## Recent Failures\n\n"
                for f in recent_failures[:3]:
                    failures_section += (
                        f"- **{f.get('run_id', '')[:8]}** ({f.get('workflow_slug', 'unknown')}): "
                        f"{f.get('error', 'No error message')[:100]}\n"
                    )

    formatted = header + metrics_section + "## Summary\n\n" + summary + failures_section

    # Store formatted output
    workflow_state["formatted_output"] = formatted

    # Create ExecutionOutput for downstream processing
    outputs = list(state.get("outputs", []))
    output_entry: ExecutionOutput = {
        "kind": "document",
        "target": {"folder": "Reports/Activity"},
        "payload": {
            "name": "Activity Summary",
            "content": formatted,
            "type": "MarkdownDocument",
        },
        "metadata": {
            "activity_period_hours": period.get("hours", 24),
            "output_format": output_format,
        },
    }
    outputs.append(output_entry)

    # Also populate output_values for WorkflowRunner processing
    output_values = dict(state.get("output_values", {}))
    output_values["Activity Summary"] = formatted

    return {
        "workflow_state": workflow_state,
        "outputs": outputs,
        "output_values": output_values,
    }


def _format_failures(failures: list) -> str:
    """Format failure list for the prompt."""
    if not failures:
        return "No recent failures."

    lines = []
    for f in failures[:5]:
        error_preview = (f.get("error") or "No error message")[:100]
        lines.append(
            f"- Run {f.get('run_id', '')[:8]} ({f.get('workflow_slug', 'unknown')}): {error_preview}"
        )
    return "\n".join(lines)


def _generate_fallback_summary(activity: dict) -> str:
    """Generate a basic summary without AI when service unavailable."""
    exec_stats = activity.get("executions", {}).get("stats", {})
    msg_stats = activity.get("messages", {}).get("stats", {})
    doc_stats = activity.get("documents", {})
    period = activity.get("period", {})

    total = exec_stats.get("total", 0)
    completed = exec_stats.get("completed", 0)
    failed = exec_stats.get("failed", 0)

    success_rate = (completed / total * 100) if total > 0 else 0

    return f"""Over the past {period.get('hours', 24)} hours, the project recorded {total} execution runs with a {success_rate:.1f}% success rate ({completed} completed, {failed} failed).

Messaging activity included {msg_stats.get('total', 0)} total messages across active channels.

Document activity showed {doc_stats.get('created', 0)} new documents created and {doc_stats.get('modified', 0)} existing documents modified.

{"**Note:** There were " + str(failed) + " failures that may need investigation." if failed > 0 else "All systems appear to be operating normally."}
"""
