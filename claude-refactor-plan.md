# Zoea Collab Core Refactoring Plan

**Goal:** Reorient Zoea as the **glue layer** between external systems, LLM models, and agents running in isolated sandboxes with guarded access to user data.

**Status:** Phase 1 (LangGraph scaffolding) partially complete. See [Implementation Progress](#implementation-progress) below.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         PLATFORM ADAPTERS                                │
│  (Slack, Discord, Email, Webhooks, Notion, n8n/Zapier, Zoea Studio)     │
└─────────────────────────────────┬───────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         UNIFIED EVENT BUS                                │
│  EventType: chat_message, scheduled_cron, webhook_received, etc.        │
│  Scheduler: one-shot events, cron events (via Django-Q2)                │
└─────────────────────────────────┬───────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                       TRIGGER ROUTER                                     │
│  TriggerEnvelope → TriggerDefinition → ExecutionRun → LangGraph         │
└───────────┬─────────────────────┬─────────────────────┬─────────────────┘
            │                     │                     │
            ▼                     ▼                     ▼
┌───────────────────┐  ┌───────────────────┐  ┌───────────────────┐
│  SANDBOX MANAGER  │  │  AGENT WRAPPER    │  │ OUTPUT DISPATCHER │
│  tmux/Docker/VM   │  │  Claude Code,     │  │ Slack, Discord,   │
│  /workspace mount │  │  Codex, OpenCode  │  │ Webhook, Docs     │
└─────────┬─────────┘  └─────────┬─────────┘  └───────────────────┘
          │                      │
          ▼                      ▼
┌───────────────────┐  ┌───────────────────┐
│ KNOWLEDGE STORE   │  │ CHANNEL STORAGE   │
│ File Search, RAG  │  │ JSONL logs        │
│ ChromaDB/Gemini   │  │ Session state     │
└───────────────────┘  └───────────────────┘
```

## Unified Schema Approach

### TriggerEnvelope (Implemented in `langgraph_runtime/state.py`)
Normalized input shape for all triggers:
```python
class TriggerEnvelope(TypedDict):
    trigger_type: Literal["chat_message", "email_received", "doc_changed", "webhook", "scheduled"]
    source: dict[str, Any]           # {adapter, external_id, metadata}
    channel: NotRequired[dict]       # {channel_id, external_id, type, display_name}
    payload: dict[str, Any]          # normalized message/body/metadata
    attachments: list[dict]
    organization_id: int
    project_id: NotRequired[int]
    workspace_id: NotRequired[int]
```

### ExecutionRun (New unified model - TODO)
Replaces `EventTriggerRun` + `WorkflowRun`:
```python
class ExecutionRun(models.Model):
    run_id = UUIDField(unique=True)
    status = CharField(choices=["pending", "running", "completed", "failed", "cancelled"])
    organization = ForeignKey('organizations.Organization')
    project = ForeignKey('projects.Project', null=True)
    workspace = ForeignKey('workspaces.Workspace', null=True)
    channel = ForeignKey('Channel', null=True)
    trigger_type = CharField()
    trigger_source = JSONField()           # adapter + external ids
    input_envelope = JSONField()           # TriggerEnvelope
    pattern_id = CharField(blank=True)     # or graph_id
    agent_profile = JSONField()            # model/tools/skills/runtime
    outputs = JSONField(default=list)      # ExecutionOutput list
    telemetry = JSONField(default=dict)    # token usage, audit log
    artifacts = ForeignKey('DocumentCollection', null=True)
    created_at, started_at, completed_at, error
```

### Channel + ChannelMessage (New models - TODO)
First-class channel abstraction:
```python
class Channel(models.Model):
    organization, project, workspace
    adapter_type = CharField()  # slack, discord, email, zoea_chat
    external_id = CharField()
    display_name = CharField()
    metadata = JSONField()

class ChannelMessage(models.Model):
    channel = ForeignKey(Channel)
    external_id = CharField()
    sender = CharField()
    role = CharField()
    content = TextField()
    raw_content = TextField()
    attachments = JSONField()
    metadata = JSONField()
```

### LangGraph Node Layout
```
ingest_envelope → route_trigger → build_inputs → select_agent_profile
       ↓
   run_agent ←────────── (needs_more_context)
       ↓
       ↓ ←────────── (retryable_error)
       ↓
collect_outputs → persist_outputs → finalize_run
```

## What to Keep (Works Well)

- **Multi-tenant models** via `django-organizations` with `OrganizationScopedQuerySet`
- **Document hierarchy** with MPTT Folders, multi-table inheritance for document types
- **LLMProviderRegistry** for OpenAI/Gemini/local model abstraction
- **SkillExecutionHarness** with `ScopedProjectAPI` and `OperationAuditLog` (Python-level isolation)
- **SkillsAgentService** with smolagents CodeAgent and skill loading
- **EventTrigger/EventTriggerRun** models for tracking executions
- **Django-Q2** for background task execution

## What to Replace

- **PocketFlow** → **LangGraph** for workflow orchestration
  - Graph-based stateful workflows match event-driven architecture
  - Explicit state management aids debugging
  - Persistence hooks for durable execution
  - Optional LangSmith tracing for observability

- **EventTriggerRun + WorkflowRun** → **ExecutionRun** (unified model)
  - Single system of record for all executions
  - Eliminates duplication between events and workflows apps

- **Implicit channel handling** → **Channel + ChannelMessage** (first-class models)
  - Explicit channel abstraction across all sources
  - Conversation model can reference Channel for internal chat

## Design Reference

Use **agentic-patterns.com** (125+ patterns) as design guidance:
- **Orchestration:** Plan-Then-Execute, Sub-Agent Spawning, Planner-Worker Separation
- **Security:** Isolated VM per Rollout, PII Tokenization
- **Tool Use:** Code-Then-Execute, CLI-First Skill Design
- **Context:** Filesystem-Based Agent State, Dynamic Context Injection

## New Django Apps to Create

### 1. `platform_adapters` - Unified Trigger Interface
Abstracts Slack, Discord, Email, Webhooks, Notion into unified ChannelMessage format.

**Models:**
- `PlatformConnection` - Connection config (credentials, webhook secret, platform type)
- `ChannelMessage` - Unified message format (channel_id, sender, content, attachments, raw_payload)

**Service Classes:**
- `BasePlatformAdapter` (ABC) - `parse_inbound()`, `send_message()`, `validate_webhook()`
- `SlackAdapter`, `DiscordAdapter`, `NotionAdapter`, `GenericWebhookAdapter`

**Key Files to Create:**
- `packages/zoea-core/platform_adapters/models.py`
- `packages/zoea-core/platform_adapters/adapters/base.py`
- `packages/zoea-core/platform_adapters/adapters/slack.py`
- `packages/zoea-core/platform_adapters/api.py`

### 2. `sandboxes` - Agent Isolation Manager
Manages execution environments: tmux sessions, Docker containers, VMs.

**Models:**
- `SandboxConfig` - Template (type, resource limits, allowed_paths, docker_image)
- `SandboxSession` - Active session (container_id, tmux_session, workspace_path, status)

**Service Classes:**
- `SandboxManager` - `create_sandbox()`, `get_executor()`, `terminate()`
- `BaseSandboxExecutor` (ABC) - `execute()`, `write_file()`, `read_file()`, `cleanup()`
- `TmuxExecutor`, `DockerExecutor`, `VMExecutor` (exe.dev/sprites.dev)

**Key Files to Create:**
- `packages/zoea-core/sandboxes/models.py`
- `packages/zoea-core/sandboxes/manager.py`
- `packages/zoea-core/sandboxes/executors/tmux.py`
- `packages/zoea-core/sandboxes/executors/docker.py`

### 3. `agent_wrappers` - External Agent Integration
Wraps external coding agents: Claude Code, Codex, OpenCode, Shelley.

**Models:**
- `ExternalAgentConfig` - Config (agent_type, credentials, default_sandbox, settings)
- `ExternalAgentRun` - Execution record (prompt, response, tokens_used, artifacts)

**Service Classes:**
- `ExternalAgentService` - Unified interface for all external agents
- `BaseAgentWrapper` (ABC) - `execute()`, `stream_output()`
- `ClaudeCodeWrapper`, `CodexWrapper`, `OpenCodeWrapper`, `ShelleyWrapper`

**Key Files to Create:**
- `packages/zoea-core/agent_wrappers/models.py`
- `packages/zoea-core/agent_wrappers/service.py`
- `packages/zoea-core/agent_wrappers/wrappers/claude_code.py`

### 4. `output_dispatch` - Result Routing
Routes agent outputs to configured destinations.

**Models:**
- `OutputRoute` - Config (trigger, destination_type, channel_id, webhook_url, template)

**Service Classes:**
- `OutputDispatcher` - `dispatch()` to all configured routes
- `SlackDispatcher`, `DiscordDispatcher`, `WebhookDispatcher`, `DocumentDispatcher`

**Key Files to Create:**
- `packages/zoea-core/output_dispatch/models.py`
- `packages/zoea-core/output_dispatch/dispatcher.py`

## Existing Apps to Refactor

### `events` App Enhancements

**Extended EventType choices:**
```python
class EventType(models.TextChoices):
    # Existing
    EMAIL_RECEIVED = "email_received"
    DOCUMENT_CREATED = "document_created"
    DOCUMENT_UPDATED = "document_updated"

    # New: Messaging
    CHAT_MESSAGE = "chat_message"
    SLACK_MESSAGE = "slack_message"
    DISCORD_MESSAGE = "discord_message"

    # New: Webhooks
    WEBHOOK_RECEIVED = "webhook_received"
    NOTION_PAGE_UPDATED = "notion_page_updated"

    # New: Scheduled
    SCHEDULED_ONESHOT = "scheduled_oneshot"
    SCHEDULED_CRON = "scheduled_cron"

    # New: System
    AGENT_COMPLETED = "agent_completed"
```

**New Model - ScheduledEvent:**
```python
class ScheduledEvent(models.Model):
    organization = ForeignKey('organizations.Organization')
    name = CharField(max_length=255)
    event_type = CharField(choices=[('oneshot', 'One-Shot'), ('cron', 'Recurring')])
    cron_expression = CharField(max_length=100, blank=True)  # "0 9 * * 1-5"
    scheduled_at = DateTimeField(null=True)  # For one-shot
    timezone = CharField(max_length=50, default='UTC')
    trigger = ForeignKey(EventTrigger)
    event_data = JSONField(default=dict)
    is_enabled = BooleanField(default=True)
    next_run_at = DateTimeField(null=True)
```

**Files to Modify:**
- `packages/zoea-core/events/models.py` - Add EventTypes, ScheduledEvent
- `packages/zoea-core/events/dispatcher.py` - Handle new event types
- `packages/zoea-core/events/scheduler.py` (new) - Cron job management via Django-Q2

### `email_gateway` Refactor
Migrate to use `platform_adapters.EmailAdapter` instead of hard-coded Mailgun handling.

### `workflows` App - PocketFlow → LangGraph Migration

**Remove:**
- PocketFlow-based node chaining
- Custom WorkflowRunner

**LangGraph Integration Architecture:**

```python
# workflows/state.py - State model as contract
from typing import TypedDict, Optional
from pydantic import BaseModel

class WorkflowState(TypedDict):
    """State carried through LangGraph execution."""
    # Trigger context
    trigger_envelope: dict          # Platform, channel, message data
    execution_run_id: str           # ExecutionRun.run_id for durability
    channel_metadata: dict          # Channel-specific context

    # Mutable step outputs
    normalized_input: Optional[dict]
    route_decision: Optional[str]
    agent_outputs: list[dict]
    final_output: Optional[dict]

# workflows/graphs/base.py - Graph structure
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.postgres import PostgresSaver

class ZoeaWorkflowGraph:
    """Base class for LangGraph-based workflows."""

    def __init__(self):
        self.graph = StateGraph(WorkflowState)
        # Checkpoints keyed by ExecutionRun.run_id
        self.checkpointer = PostgresSaver.from_conn_string(settings.DATABASE_URL)

    def build_standard_graph(self):
        """Standard node flow: normalize → route → agent → output"""
        self.graph.add_node("normalize_input", self.normalize_input)
        self.graph.add_node("route", self.route_to_handler)
        self.graph.add_node("agent_step", self.run_agent)
        self.graph.add_node("output_adapter", self.dispatch_output)

        self.graph.add_edge("normalize_input", "route")
        self.graph.add_conditional_edges(
            "route",
            self.should_continue,
            {"agent": "agent_step", "direct_output": "output_adapter"}
        )
        # Loop back for plan-execute/refine patterns
        self.graph.add_conditional_edges(
            "agent_step",
            self.agent_should_continue,
            {"continue": "agent_step", "done": "output_adapter"}
        )
        self.graph.add_edge("output_adapter", END)

    def compile(self, thread_id: str):
        """Compile with checkpointer using ExecutionRun.run_id"""
        return self.graph.compile(
            checkpointer=self.checkpointer,
            interrupt_before=["agent_step"],  # Human-in-the-loop
        )
```

**Key Integration Points:**

1. **State Model as Contract:**
   - `WorkflowState` carries TriggerEnvelope, ExecutionRun IDs, channel metadata
   - Mutable step outputs for each node

2. **Durability via Checkpoints:**
   - Checkpoints keyed by `ExecutionRun.run_id`
   - Store in PostgreSQL (same DB) or JSONB field on ExecutionRun
   - Enables resume after crash/restart

3. **Graph Node Flow:**
   ```
   normalize_input → route → agent_step ↺ → output_adapter → END
                              (loops for plan-execute patterns)
   ```

4. **Observability:**
   - Optional LangSmith tracing integration
   - Trace each graph run for debugging
   - No extra infrastructure needed initially

**Why This Fits Zoea:**
- LLM as control plane: LangGraph is low-level, doesn't impose agent architecture
- ExecutionRuns become durable, auditable system of record
- Keep existing tools (smolagents) embedded in graph nodes
- LangGraph doesn't require LangChain - it's optional

**Files to Create/Modify:**
- `packages/zoea-core/workflows/state.py` (new) - WorkflowState definition
- `packages/zoea-core/workflows/graphs/base.py` (new) - ZoeaWorkflowGraph
- `packages/zoea-core/workflows/graphs/rag.py` (new) - RAG workflow graph
- `packages/zoea-core/workflows/runner.py` - Update to use LangGraph
- `packages/zoea-core/pyproject.toml` - Add `langgraph`, `langgraph-checkpoint-postgres`
- Remove `pocketflow` dependency

## API Endpoint Changes

**New Endpoints:**
```
POST /api/webhooks/{platform}/{connection_id}  # Unified webhook receiver
GET/POST /api/connections                       # Platform connections
GET/POST /api/sandboxes/configs                 # Sandbox configurations
GET/POST /api/sandboxes/sessions                # Active sessions
POST /api/sandboxes/sessions/{id}/terminate
GET/POST /api/agents/external                   # External agent configs
POST /api/agents/external/{id}/run
GET/POST /api/outputs/routes                    # Output routing
GET/POST /api/events/scheduled                  # Scheduled events
```

## CLI Enhancements

```bash
# Platform adapters
zoea adapters list
zoea adapters add slack --name "Main Workspace"
zoea adapters test {connection_id}

# Sandboxes
zoea sandboxes list
zoea sandboxes create --type docker --name "Agent Runner"
zoea sandboxes shell {session_id}

# External agents
zoea agents list
zoea agents run claude-code --prompt "Fix the bug in auth.py"

# Scheduled events
zoea events schedule --cron "0 9 * * *" --trigger email-digest
```

## Implementation Phases

### Phase 1: LangGraph Migration (Foundation)
1. Add `langgraph`, `langgraph-checkpoint-postgres` to dependencies, remove `pocketflow`
2. Create `workflows/state.py` with `WorkflowState` TypedDict
3. Create `workflows/graphs/base.py` with `ZoeaWorkflowGraph` base class
4. Implement standard graph flow: `normalize_input → route → agent_step → output_adapter`
5. Add conditional edge looping for plan-execute/refine patterns
6. Configure PostgreSQL checkpointer keyed by `ExecutionRun.run_id`
7. Update `ExecutionRun` model to store checkpoint reference
8. Migrate existing PocketFlow workflows to LangGraph graphs
9. **Optional:** Enable LangSmith tracing for observability
10. **Test:** Verify existing workflow behavior preserved

### Phase 2: Platform Adapters
1. Create `platform_adapters` app with models
2. Implement `GenericWebhookAdapter` for n8n/Zapier
3. Migrate `email_gateway` to use adapter pattern
4. Add unified webhook endpoint
5. **Backward Compatible:** Keep existing email webhook working

### Phase 3: Enhanced Events
1. Extend `EventType` choices (additive, no breaking changes)
2. Add `ScheduledEvent` model
3. Implement cron scheduler via Django-Q2
4. Wire scheduled events to `EventDispatcher`

### Phase 4: Sandbox Manager
1. Create `sandboxes` app with models
2. Implement `TmuxExecutor` (simplest, good for development)
3. Implement `DockerExecutor` with /workspace mount pattern
4. Update `SkillsAgentService` to optionally use sandboxes

### Phase 5: Agent Wrappers
1. Create `agent_wrappers` app with models
2. Implement `ClaudeCodeWrapper` (CLI invocation in sandbox)
3. Add `ExternalAgentConfig` to `EventTrigger.agent_config`
4. Implement OpenCode and Shelley wrappers

### Phase 6: Output Dispatcher
1. Create `output_dispatch` app with models
2. Implement `WebhookDispatcher` (simplest first)
3. Implement `SlackDispatcher` using platform adapter
4. Wire into `EventTriggerRun` completion flow

### Phase 7: Polish & Integration
1. Add `ChannelLog` model for JSONL session logs
2. Full CLI coverage for all new features
3. Documentation and examples
4. Integration tests

## Critical Files Reference

| File | Purpose |
|------|---------|
| `events/models.py` | Extend EventType, add ScheduledEvent |
| `events/harness.py` | Pattern for SandboxManager isolation |
| `chat/skills_agent_service.py` | Integrate external agent wrappers |
| `llm_providers/registry.py` | Pattern for PlatformAdapterRegistry |
| `agents/registry.py` | Pattern for registries |

## File/Knowledge Access for Sandboxed Agents

Options for providing files to agents in sandboxes:

1. **Mount Pattern (Recommended for Docker):**
   - Mount `/workspace` containing project documents
   - Agent can read/write within this directory
   - Use bubblewrap overlays to restrict cross-channel access

2. **Copy-In/Copy-Out Pattern:**
   - Copy required files into sandbox workspace before execution
   - Copy artifacts out after completion
   - Works for all sandbox types

3. **API Access Pattern:**
   - Agent uses HTTP API to request files from Zoea
   - Zoea validates access via `ScopedProjectAPI`
   - Works when direct filesystem access isn't available

## Verification Plan

1. **Unit Tests:** Each new model, service, and executor
2. **Integration Tests:**
   - Webhook → EventTrigger → Sandbox → Output flow
   - Scheduled event execution
   - Platform adapter round-trip (receive message, send response)
3. **Manual Testing:**
   - `zoea adapters add slack` + send message + verify response
   - `zoea agents run claude-code --prompt "hello"` in Docker sandbox
   - Cron event fires at scheduled time

## Implementation Decisions

Based on discussion:
- **Workflow Framework:** LangGraph (replacing PocketFlow) - production-proven, graph-based, explicit state
- **First Adapter:** Generic Webhook - covers n8n, Zapier, and custom integrations
- **Sandbox Priority:** Docker containers with /workspace mount pattern
- **File Strategy:** Mount pattern for direct filesystem access in Docker sandboxes
- **Design Reference:** agentic-patterns.com for pattern guidance

## Implementation Progress

### ✅ Completed (Phase 1 Partial)
- **LangGraph scaffolding** - `packages/zoea-core/langgraph_runtime/`
  - `state.py` - `ExecutionState`, `TriggerEnvelope`, `AgentProfile`, `ExecutionOutput` TypedDicts
  - `nodes.py` - Placeholder node helpers
  - `graphs.py` - Graph builder utilities
  - `runtime.py` - `run_graph()` async executor
- **Registry updates** - `packages/zoea-core/workflows/registry.py`
  - Tracks `graph_id`, `graph_builder`, `legacy_flow_builder`
  - Discovers `graph.py` first, falls back to `flow.py`
- **Runner updates** - `packages/zoea-core/workflows/runner.py`
  - Builds `ExecutionState` from inputs
  - Runs LangGraph graphs via `run_graph()`
  - Falls back to legacy PocketFlow when no graph available

### 🔲 Remaining (Phase 1)
1. Add `langgraph` + `langgraph-checkpoint-postgres` to `pyproject.toml` dependencies
2. Create first LangGraph workflow: `workflows/builtin/summarize_content/graph.py`
3. Add `ExecutionRun` model (unified from EventTriggerRun + WorkflowRun)
4. Add `Channel` + `ChannelMessage` models
5. Configure PostgreSQL checkpointer
6. Decide: keep legacy fallback for one release or cut over immediately

### 🔲 Phases 2-7 (Not Started)
See [Implementation Phases](#implementation-phases) above.

## Open Questions

1. **Legacy Fallback:** Keep PocketFlow in parallel for one release, or cut over immediately?
2. **Channel Storage:** Store full transcript in DB, or also support `log.jsonl` (hybrid)?
3. **Docker Runtime Constraints:** What tool/skill constraints beyond ScopedProjectAPI harness?
