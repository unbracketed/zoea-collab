# Zoea Collab Refactor - Implementation Progress

**Date:** 2026-01-23 (Updated)
**Reference:** `codex-refactor-plan.md`

## Overview

The refactor aims to unify Zoea around:
- **ExecutionRun** as the single system of record (replacing EventTriggerRun + WorkflowRun)
- **Channel + ChannelMessage** as first-class models for all messaging sources
- **LangGraph** as the workflow orchestration runtime (replacing PocketFlow)
- **TriggerEnvelope** as the normalized input shape for all triggers

---

## Phase 1: Schema + API Foundations ✅ Complete

| Item | Status | Location |
|------|--------|----------|
| `TriggerEnvelope` schema | ✅ Done | `langgraph_runtime/state.py` |
| `ExecutionState` TypedDict | ✅ Done | `langgraph_runtime/state.py` |
| `AgentProfile` TypedDict | ✅ Done | `langgraph_runtime/state.py` |
| `ExecutionOutput` TypedDict | ✅ Done | `langgraph_runtime/state.py` |
| `Channel` model | ✅ Done | `channels/models.py` |
| `ChannelMessage` model | ✅ Done | `channels/models.py` |
| `ExecutionRun` unified model | ✅ Done | `execution/models.py` |
| Database migrations | ✅ Done | `execution/migrations/0001_initial.py`, `channels/migrations/0001_initial.py` |

### New Apps Created

- **`execution/`** - Unified ExecutionRun model
- **`channels/`** - Channel + ChannelMessage models

---

## Phase 2: LangGraph Runtime + Execution Path ✅ Complete

| Item | Status | Location |
|------|--------|----------|
| LangGraph runtime module | ✅ Done | `langgraph_runtime/` |
| `run_graph()` async executor | ✅ Done | `langgraph_runtime/runtime.py` |
| Node helpers (scaffold) | ✅ Done | `langgraph_runtime/nodes.py` |
| Graph builder utilities | ✅ Done | `langgraph_runtime/graphs.py` |
| `WorkflowRegistry` with `graph_builder` | ✅ Done | `workflows/registry.py` |
| `WorkflowRunner` LangGraph path | ✅ Done | `workflows/runner.py:128-139` |
| Legacy PocketFlow fallback | ✅ Done | `workflows/runner.py:141-169` |
| Add `langgraph` dependency | ✅ Done | `pyproject.toml:39-40` |
| First LangGraph workflow | ✅ Done | `workflows/builtin/project_activity_summary/graph.py` |
| EventTrigger → ExecutionRun routing | 🔲 TODO | `events/dispatcher.py` |

### Key Changes

**`workflows/registry.py`:**
- Now tracks `graph_id`, `graph_builder`, and optional `legacy_flow_builder`
- Discovers `graph.py` first, falls back to `flow.py`

**`workflows/runner.py`:**
- Builds `ExecutionState` from inputs with Django context
- Runs LangGraph graphs via `run_graph()`
- Falls back to legacy PocketFlow when no graph available
- Processes outputs from LangGraph state

---

## Harness Integration ✅ Complete

| Item | Status | Location |
|------|--------|----------|
| `SkillExecutionContext.from_execution_run()` | ✅ Done | `events/harness.py:96-140` |
| Backward-compatible `from_trigger_run()` | ✅ Done | `events/harness.py:142-152` |

---

## Phase 3: Sandboxes + Agent Wrappers ✅ Complete

| Item | Status | Location |
|------|--------|----------|
| `SandboxConfig` model | ✅ Done | `sandboxes/models.py` |
| `SandboxSession` model | ✅ Done | `sandboxes/models.py` |
| `SandboxManager` service | ✅ Done | `sandboxes/manager.py` |
| `BaseSandboxExecutor` interface | ✅ Done | `sandboxes/executors/base.py` |
| `TmuxExecutor` implementation | ✅ Done | `sandboxes/executors/tmux.py` |
| Docker executor | 🔲 TODO | `sandboxes/executors/docker.py` |
| `ExternalAgentConfig` model | ✅ Done | `agent_wrappers/models.py` |
| `ExternalAgentRun` model | ✅ Done | `agent_wrappers/models.py` |
| `BaseAgentWrapper` interface | ✅ Done | `agent_wrappers/wrappers/base.py` |
| `ClaudeCodeWrapper` | ✅ Done | `agent_wrappers/wrappers/claude_code.py` |
| `ExternalAgentService` | ✅ Done | `agent_wrappers/service.py` |

### New Apps Created

- **`sandboxes/`** - Execution environment management (tmux, docker, VM)
- **`agent_wrappers/`** - External agent integration (Claude Code, Codex, etc.)

---

## Phase 4: Platform Adapters + Output Dispatch ✅ Complete

| Item | Status | Location |
|------|--------|----------|
| `PlatformConnection` model | ✅ Done | `platform_adapters/models.py` |
| `PlatformMessage` model | ✅ Done | `platform_adapters/models.py` |
| `BasePlatformAdapter` interface | ✅ Done | `platform_adapters/adapters/base.py` |
| `GenericWebhookAdapter` | ✅ Done | `platform_adapters/adapters/webhook.py` |
| Platform adapters API | ✅ Done | `platform_adapters/api.py` |
| `OutputRoute` model | ✅ Done | `output_dispatch/models.py` |
| `DispatchLog` model | ✅ Done | `output_dispatch/models.py` |
| `OutputDispatcher` service | ✅ Done | `output_dispatch/dispatcher.py` |
| Webhook dispatcher | ✅ Done | `output_dispatch/dispatcher.py` |
| Slack dispatcher | ✅ Done | `output_dispatch/dispatcher.py` |
| Document dispatcher | ✅ Done | `output_dispatch/dispatcher.py` |
| `ScheduledEvent` model | ✅ Done | `events/models.py` |
| `ScheduledEventService` | ✅ Done | `events/scheduler.py` |
| Extended `EventType` choices | ✅ Done | `events/models.py` |

### New Apps Created

- **`platform_adapters/`** - Unified platform connection management
- **`output_dispatch/`** - Configurable output routing to destinations

---

## Phase 5: Cleanup + Docs 🔄 In Progress

| Item | Status | Notes |
|------|--------|-------|
| Remove `workspaces` app | ✅ Done | Deleted entirely |
| Remove `context_clipboards` app | ✅ Done | Deleted entirely |
| Migrate workspace FK → project FK | ✅ Done | All models updated |
| Deprecate/fold Conversation model | 🔲 TODO | |
| Update CLI for ExecutionRun | 🔲 TODO | |
| End-to-end tests | 🔲 TODO | |
| Documentation updates | 🔲 TODO | |

---

## Files Changed (Recent)

### New Apps (Phase 3-4)
```
packages/zoea-core/sandboxes/
├── models.py              - SandboxConfig, SandboxSession
├── manager.py             - SandboxManager service
├── executors/base.py      - BaseSandboxExecutor interface
├── executors/tmux.py      - TmuxExecutor implementation
└── tests/test_models.py   - 18 tests

packages/zoea-core/agent_wrappers/
├── models.py              - ExternalAgentConfig, ExternalAgentRun
├── service.py             - ExternalAgentService
├── wrappers/base.py       - BaseAgentWrapper interface
├── wrappers/claude_code.py - ClaudeCodeWrapper
└── tests/test_models.py   - 19 tests

packages/zoea-core/platform_adapters/
├── models.py              - PlatformConnection, PlatformMessage
├── adapters/base.py       - BasePlatformAdapter interface
├── adapters/webhook.py    - GenericWebhookAdapter
├── api.py                 - Webhook receiver endpoints
└── tests/                 - Adapter and model tests

packages/zoea-core/output_dispatch/
├── models.py              - OutputRoute, DispatchLog
├── dispatcher.py          - OutputDispatcher service
└── tests/test_models.py   - 17 tests
```

### New Files (Phase 1-2)
```
packages/zoea-core/execution/
packages/zoea-core/channels/
packages/zoea-core/langgraph_runtime/
packages/zoea-core/workflows/builtin/project_activity_summary/
packages/zoea-core/events/scheduler.py     - ScheduledEventService
```

### Modified Files
```
packages/zoea-core/events/models.py        - Added ScheduledEvent, extended EventType
packages/zoea-core/events/api.py           - Added scheduled event endpoints
packages/zoea-core/workflows/registry.py   - graph_builder discovery
packages/zoea-core/workflows/runner.py     - LangGraph execution path
packages/zoea-core/pyproject.toml          - Added new apps + croniter dependency
packages/zoea-core/zoea/settings.py        - Registered new apps
```

### Removed/Deleted
```
packages/zoea-core/workspaces/             - Entire app deleted
packages/zoea-core/context_clipboards/     - Entire app deleted
packages/zoea-core/cli/commands/workspaces.py
packages/zoea-core/cli/commands/clipboard.py
```

---

## Next Steps (Immediate)

1. **Implement Docker executor:**
   - `sandboxes/executors/docker.py` with /workspace mount pattern
   - Test with Claude Code wrapper

2. **Wire output dispatch to execution flow:**
   - Call `OutputDispatcher.dispatch_execution_output()` on ExecutionRun completion
   - Test webhook and Slack dispatchers end-to-end

3. **Add remaining platform adapters:**
   - `SlackAdapter` for Slack app integration
   - `DiscordAdapter` for Discord bot integration

4. **End-to-end integration tests:**
   - Webhook → PlatformMessage → EventTrigger → ExecutionRun → OutputDispatch
   - Scheduled event → ExecutionRun → OutputDispatch

---

## Open Questions

1. **Docker Runtime Constraints:** What tool/skill constraints beyond ScopedProjectAPI harness?
2. **Sandbox Cleanup:** Auto-cleanup stale sessions, or require explicit termination?
3. **Output Templating:** Use Jinja2 for output templates, or keep simple string formatting?

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         PLATFORM ADAPTERS                                    │
│  GenericWebhookAdapter, SlackAdapter (TODO), DiscordAdapter (TODO)          │
│  PlatformConnection + PlatformMessage models                                 │
└─────────────────────────────────────┬───────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         EVENT SYSTEM                                         │
│  EventTrigger + ScheduledEvent → EventDispatcher → ExecutionRun             │
└─────────────────────────────────────┬───────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         LANGGRAPH RUNTIME                                    │
│  WorkflowRegistry → WorkflowRunner → run_graph() → ExecutionState           │
└───────────┬─────────────────────────┬───────────────────────────────────────┘
            │                         │
            ▼                         ▼
┌───────────────────────┐  ┌───────────────────────┐
│   SANDBOX MANAGER     │  │   AGENT WRAPPERS      │
│   TmuxExecutor        │  │   ClaudeCodeWrapper   │
│   DockerExecutor(TODO)│  │   ExternalAgentService│
│   SandboxSession      │  │   ExternalAgentRun    │
└───────────────────────┘  └───────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         OUTPUT DISPATCH                                      │
│  OutputRoute → OutputDispatcher → DispatchLog                               │
│  WebhookDispatcher, SlackDispatcher, DocumentDispatcher                     │
└─────────────────────────────────────────────────────────────────────────────┘
```

### LangGraph Node Layout (Default Graph)
```
ingest_envelope → route_trigger → build_inputs → select_agent_profile
                                                        ↓
                                                    run_agent ←── (needs_more_context)
                                                        ↓
                                                        ↓ ←── (retryable_error)
                                                        ↓
                                              collect_outputs → persist_outputs → finalize_run
```

### Project Activity Summary Workflow
```
gather_activity → summarize_activity → format_output → END
```

This is the first LangGraph-native workflow, demonstrating:
- Query across ExecutionRun, ChannelMessage, Document models
- LLM summarization via AIService
- Output formatting with markdown/slack variants
- ExecutionOutput generation for downstream processing
- Full test coverage (9 tests)
