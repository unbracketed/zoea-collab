"""Typed state schema for LangGraph execution."""

from typing import Any, Literal, NotRequired, TypedDict

TriggerType = Literal[
    "chat_message",
    "email_received",
    "doc_changed",
    "webhook",
    "scheduled",
]


class TriggerEnvelope(TypedDict):
    trigger_type: TriggerType
    source: dict[str, Any]
    channel: NotRequired[dict[str, Any]]
    payload: dict[str, Any]
    attachments: list[dict[str, Any]]
    organization_id: int
    project_id: NotRequired[int]
    workspace_id: NotRequired[int]


class AgentProfile(TypedDict, total=False):
    provider: str
    model_id: str
    tools: list[str]
    skills: list[str]
    runtime: str
    max_steps: int
    instructions: str
    router: str


class ExecutionOutput(TypedDict, total=False):
    kind: Literal["message", "document", "artifact", "webhook"]
    target: dict[str, Any]
    payload: dict[str, Any]
    metadata: dict[str, Any]


class ExecutionState(TypedDict, total=False):
    # Identity + persistence
    run_id: str
    execution_run_id: int
    status: str

    # Inputs
    envelope: TriggerEnvelope | None
    input_map: dict[str, Any]
    inputs: dict[str, Any]

    # Routing / orchestration
    graph_id: str
    agent_profile: AgentProfile

    # Outputs
    outputs: list[ExecutionOutput]
    output_values: dict[str, Any]
    artifacts: list[dict[str, Any]]
    workflow_state: dict[str, Any]

    # Services + context (scaffold for node access)
    services: dict[str, Any]
    context: dict[str, Any]

    # Control + telemetry
    steps: list[dict[str, Any]]
    telemetry: dict[str, Any]
    error: str
    should_continue: bool
    retryable_error: bool
