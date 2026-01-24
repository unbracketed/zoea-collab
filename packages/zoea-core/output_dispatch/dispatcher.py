"""
Output dispatcher service for routing outputs to destinations.

Provides unified interface for dispatching outputs from agent runs
and executions to configured routes.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from django.db import transaction
from django.utils import timezone

if TYPE_CHECKING:
    from accounts.models import Account
    from agent_wrappers.models import ExternalAgentRun
    from execution.models import ExecutionRun
    from projects.models import Project

from .models import DestinationType, DispatchLog, DispatchStatus, OutputRoute

logger = logging.getLogger(__name__)


class OutputDispatcher:
    """
    Service for dispatching outputs to configured routes.

    Handles:
    - Finding matching routes for an output
    - Formatting output according to route configuration
    - Dispatching to various destination types
    - Logging dispatch attempts
    """

    @classmethod
    def dispatch_execution_output(
        cls,
        execution_run: ExecutionRun,
        output_data: dict[str, Any],
    ) -> list[DispatchLog]:
        """
        Dispatch outputs from an execution run to all matching routes.

        Args:
            execution_run: The ExecutionRun that produced the output.
            output_data: The output data to dispatch.

        Returns:
            List of DispatchLog records for each dispatch attempt.
        """
        # Find matching routes
        routes = cls._get_matching_routes(
            organization=execution_run.organization,
            project=execution_run.project,
            trigger=execution_run.trigger,
            output_data=output_data,
        )

        if not routes:
            logger.debug(
                f"No matching routes for execution run {execution_run.run_id}"
            )
            return []

        # Dispatch to each route
        logs = []
        for route in routes:
            log = cls._dispatch_to_route(
                route=route,
                output_data=output_data,
                execution_run=execution_run,
            )
            logs.append(log)

        return logs

    @classmethod
    def dispatch_agent_output(
        cls,
        agent_run: ExternalAgentRun,
        output_data: dict[str, Any] | None = None,
    ) -> list[DispatchLog]:
        """
        Dispatch outputs from an agent run to all matching routes.

        Args:
            agent_run: The ExternalAgentRun that produced the output.
            output_data: Optional output data (defaults to agent run response).

        Returns:
            List of DispatchLog records for each dispatch attempt.
        """
        # Build output data from agent run if not provided
        if output_data is None:
            output_data = {
                "response": agent_run.response,
                "artifacts": agent_run.artifacts,
                "tokens_used": agent_run.tokens_used,
                "steps_taken": agent_run.steps_taken,
                "agent_type": agent_run.agent_type,
                "status": agent_run.status,
            }

        # Get trigger from parent execution run if available
        trigger = None
        if agent_run.execution_run:
            trigger = agent_run.execution_run.trigger

        # Find matching routes
        routes = cls._get_matching_routes(
            organization=agent_run.organization,
            project=agent_run.project,
            trigger=trigger,
            output_data=output_data,
        )

        if not routes:
            logger.debug(f"No matching routes for agent run {agent_run.run_id}")
            return []

        # Dispatch to each route
        logs = []
        for route in routes:
            log = cls._dispatch_to_route(
                route=route,
                output_data=output_data,
                agent_run=agent_run,
            )
            logs.append(log)

        return logs

    @classmethod
    def dispatch_to_route(
        cls,
        route: OutputRoute,
        output_data: dict[str, Any],
        *,
        execution_run: ExecutionRun | None = None,
        agent_run: ExternalAgentRun | None = None,
    ) -> DispatchLog:
        """
        Dispatch output to a specific route.

        Args:
            route: The OutputRoute to dispatch to.
            output_data: The output data to dispatch.
            execution_run: Optional source execution run.
            agent_run: Optional source agent run.

        Returns:
            DispatchLog record for the attempt.
        """
        return cls._dispatch_to_route(
            route=route,
            output_data=output_data,
            execution_run=execution_run,
            agent_run=agent_run,
        )

    # =========================================================================
    # Private Methods
    # =========================================================================

    @classmethod
    def _get_matching_routes(
        cls,
        organization: Account,
        project: Project | None,
        trigger,
        output_data: dict[str, Any],
    ) -> list[OutputRoute]:
        """Find routes that match the given context."""
        # Query for matching routes
        queryset = OutputRoute.objects.filter(
            organization=organization,
            is_enabled=True,
        )

        # Filter by trigger if present
        if trigger:
            queryset = queryset.filter(
                models.Q(trigger=trigger) | models.Q(trigger__isnull=True)
            )
        else:
            queryset = queryset.filter(trigger__isnull=True)

        # Filter by project if present
        if project:
            queryset = queryset.filter(
                models.Q(project=project) | models.Q(project__isnull=True)
            )
        else:
            queryset = queryset.filter(project__isnull=True)

        # Order by priority
        routes = list(queryset.order_by("-priority"))

        # Filter by output conditions
        return [r for r in routes if r.matches_output(output_data)]

    @classmethod
    def _dispatch_to_route(
        cls,
        route: OutputRoute,
        output_data: dict[str, Any],
        execution_run: ExecutionRun | None = None,
        agent_run: ExternalAgentRun | None = None,
    ) -> DispatchLog:
        """Dispatch output to a single route."""
        # Create dispatch log
        with transaction.atomic():
            log = DispatchLog.objects.create(
                organization=route.organization,
                route=route,
                execution_run=execution_run,
                agent_run=agent_run,
                destination_type=route.destination_type,
                destination_info={
                    "route_name": route.name,
                    "channel_id": route.channel_id,
                    "webhook_url": route.webhook_url,
                },
                status=DispatchStatus.PENDING,
            )

        try:
            # Format the payload
            payload = cls._format_payload(route, output_data)
            log.payload = payload
            log.save(update_fields=["payload"])

            # Dispatch based on destination type
            log.set_status(DispatchStatus.SENDING)

            if route.destination_type == DestinationType.WEBHOOK:
                response = cls._dispatch_webhook(route, payload)
            elif route.destination_type == DestinationType.SLACK:
                response = cls._dispatch_slack(route, payload)
            elif route.destination_type == DestinationType.DISCORD:
                response = cls._dispatch_discord(route, payload)
            elif route.destination_type == DestinationType.DOCUMENT:
                response = cls._dispatch_document(route, payload, output_data)
            elif route.destination_type == DestinationType.PLATFORM_REPLY:
                response = cls._dispatch_platform_reply(route, payload, output_data)
            elif route.destination_type == DestinationType.EMAIL:
                response = cls._dispatch_email(route, payload)
            else:
                raise ValueError(f"Unsupported destination type: {route.destination_type}")

            log.response_data = response
            log.set_status(DispatchStatus.SUCCESS)

            logger.info(
                f"Dispatched output to route {route.name} "
                f"(type={route.destination_type})"
            )

        except Exception as e:
            logger.exception(f"Failed to dispatch to route {route.name}: {e}")
            log.set_status(DispatchStatus.FAILED, str(e))

        return log

    @classmethod
    def _format_payload(
        cls,
        route: OutputRoute,
        output_data: dict[str, Any],
    ) -> dict[str, Any]:
        """Format the payload according to route configuration."""
        # Apply template if configured
        if route.template:
            content = cls._render_template(route.template, output_data)
        else:
            # Default formatting based on format type
            if route.format_type == "json":
                content = output_data
            elif route.format_type == "markdown":
                content = cls._format_as_markdown(output_data)
            else:
                content = cls._format_as_text(output_data)

        payload = {
            "content": content,
            "format": route.format_type,
            "timestamp": timezone.now().isoformat(),
        }

        # Include artifacts if configured
        if route.include_artifacts and "artifacts" in output_data:
            payload["artifacts"] = output_data["artifacts"]

        return payload

    @classmethod
    def _render_template(cls, template: str, data: dict[str, Any]) -> str:
        """Render a template with the given data."""
        try:
            # Simple variable substitution
            result = template
            for key, value in data.items():
                placeholder = f"{{{{{key}}}}}"
                result = result.replace(placeholder, str(value))
            return result
        except Exception as e:
            logger.warning(f"Template rendering failed: {e}")
            return str(data)

    @classmethod
    def _format_as_text(cls, data: dict[str, Any]) -> str:
        """Format output data as plain text."""
        parts = []

        if "response" in data:
            parts.append(data["response"])

        if "artifacts" in data and data["artifacts"]:
            parts.append("\nArtifacts:")
            for artifact in data["artifacts"]:
                parts.append(f"  - {artifact.get('path', artifact)}")

        return "\n".join(parts)

    @classmethod
    def _format_as_markdown(cls, data: dict[str, Any]) -> str:
        """Format output data as markdown."""
        parts = []

        if "response" in data:
            parts.append(data["response"])

        if "artifacts" in data and data["artifacts"]:
            parts.append("\n## Artifacts")
            for artifact in data["artifacts"]:
                path = artifact.get("path", str(artifact))
                action = artifact.get("action", "")
                parts.append(f"- `{path}` ({action})" if action else f"- `{path}`")

        return "\n".join(parts)

    # =========================================================================
    # Destination-Specific Dispatchers
    # =========================================================================

    @classmethod
    def _dispatch_webhook(
        cls,
        route: OutputRoute,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        """Dispatch to a webhook URL."""
        import requests

        if not route.webhook_url:
            raise ValueError("Webhook URL not configured")

        response = requests.post(
            route.webhook_url,
            json=payload,
            timeout=30,
            headers={"Content-Type": "application/json"},
        )

        response.raise_for_status()

        return {
            "status_code": response.status_code,
            "response": response.text[:1000],  # Truncate long responses
        }

    @classmethod
    def _dispatch_slack(
        cls,
        route: OutputRoute,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        """Dispatch to Slack channel via platform adapter."""
        if not route.platform_connection:
            raise ValueError("Platform connection not configured for Slack")

        from platform_adapters.adapters import GenericWebhookAdapter

        adapter = GenericWebhookAdapter(route.platform_connection)

        content = payload.get("content", "")
        if isinstance(content, dict):
            content = str(content)

        result = adapter.send_message(
            channel_id=route.channel_id,
            content=content,
        )

        return {
            "success": result.success,
            "external_id": result.external_id,
            "error": result.error_message,
        }

    @classmethod
    def _dispatch_discord(
        cls,
        route: OutputRoute,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        """Dispatch to Discord channel via platform adapter."""
        # Similar to Slack, use platform adapter
        if not route.platform_connection:
            raise ValueError("Platform connection not configured for Discord")

        from platform_adapters.adapters import GenericWebhookAdapter

        adapter = GenericWebhookAdapter(route.platform_connection)

        content = payload.get("content", "")
        if isinstance(content, dict):
            content = str(content)

        result = adapter.send_message(
            channel_id=route.channel_id,
            content=content,
        )

        return {
            "success": result.success,
            "external_id": result.external_id,
            "error": result.error_message,
        }

    @classmethod
    def _dispatch_document(
        cls,
        route: OutputRoute,
        payload: dict[str, Any],
        output_data: dict[str, Any],
    ) -> dict[str, Any]:
        """Create a document from the output."""
        from documents.models import MarkdownDocument

        # Generate document name
        name = route.document_name_template.format(
            timestamp=timezone.now().strftime("%Y%m%d_%H%M%S"),
            **output_data,
        )

        content = payload.get("content", "")
        if isinstance(content, dict):
            import json

            content = json.dumps(content, indent=2)

        # Create document
        document = MarkdownDocument.objects.create(
            organization=route.organization,
            project=route.project,
            folder=route.document_folder,
            name=name,
            content=content,
        )

        return {
            "document_id": document.id,
            "document_name": document.name,
        }

    @classmethod
    def _dispatch_platform_reply(
        cls,
        route: OutputRoute,
        payload: dict[str, Any],
        output_data: dict[str, Any],
    ) -> dict[str, Any]:
        """Reply to the original platform message."""
        # Get the original message info from output_data
        channel_id = output_data.get("channel_id") or route.channel_id
        thread_id = output_data.get("thread_id")

        if not route.platform_connection:
            raise ValueError("Platform connection not configured")

        from platform_adapters.adapters import GenericWebhookAdapter

        adapter = GenericWebhookAdapter(route.platform_connection)

        content = payload.get("content", "")
        if isinstance(content, dict):
            content = str(content)

        result = adapter.send_message(
            channel_id=channel_id,
            content=content,
            thread_id=thread_id,
        )

        return {
            "success": result.success,
            "external_id": result.external_id,
            "error": result.error_message,
        }

    @classmethod
    def _dispatch_email(
        cls,
        route: OutputRoute,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        """Dispatch via email."""
        # Email dispatch not yet implemented
        raise NotImplementedError("Email dispatch not yet implemented")


# Import models for Django Q lookups
from django.db import models


def dispatch_output(
    output_data: dict[str, Any],
    *,
    execution_run: ExecutionRun | None = None,
    agent_run: ExternalAgentRun | None = None,
) -> list[DispatchLog]:
    """
    Convenience function to dispatch output.

    Args:
        output_data: The output data to dispatch.
        execution_run: Optional source execution run.
        agent_run: Optional source agent run.

    Returns:
        List of DispatchLog records.
    """
    if execution_run:
        return OutputDispatcher.dispatch_execution_output(execution_run, output_data)
    elif agent_run:
        return OutputDispatcher.dispatch_agent_output(agent_run, output_data)
    else:
        raise ValueError("Either execution_run or agent_run must be provided")
