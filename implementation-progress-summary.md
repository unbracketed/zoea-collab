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

## Phase 3: AgentRuntime + Docker 🔲 Not Started

| Item | Status |
|------|--------|
| AgentRuntime interface | 🔲 TODO |
| Docker runtime with /workspace mount | 🔲 TODO |
| Bind SkillExecutionHarness to runtime | 🔲 TODO |

---

## Phase 4: Outputs + Adapters 🔲 Not Started

| Item | Status |
|------|--------|
| OutputAdapters interface | 🔲 TODO |
| Slack adapter | 🔲 TODO |
| Discord adapter | 🔲 TODO |
| Email adapter | 🔲 TODO |
| Webhook adapter | 🔲 TODO |
| Scheduled triggers (cron, one-shot) | 🔲 TODO |
| Webhook ingress trigger | 🔲 TODO |

---

## Phase 5: Cleanup + Docs 🔲 Not Started

| Item | Status |
|------|--------|
| Deprecate/fold Conversation model | 🔲 TODO |
| Update CLI for ExecutionRun | 🔲 TODO |
| End-to-end tests | 🔲 TODO |
| Documentation updates | 🔲 TODO |

---

## Files Changed (Recent)

### New Files
```
packages/zoea-core/execution/__init__.py
packages/zoea-core/execution/apps.py
packages/zoea-core/execution/models.py
packages/zoea-core/execution/admin.py
packages/zoea-core/execution/migrations/0001_initial.py

packages/zoea-core/channels/__init__.py
packages/zoea-core/channels/apps.py
packages/zoea-core/channels/models.py
packages/zoea-core/channels/admin.py
packages/zoea-core/channels/migrations/0001_initial.py

packages/zoea-core/langgraph_runtime/__init__.py
packages/zoea-core/langgraph_runtime/state.py
packages/zoea-core/langgraph_runtime/nodes.py
packages/zoea-core/langgraph_runtime/graphs.py
packages/zoea-core/langgraph_runtime/runtime.py

packages/zoea-core/workflows/builtin/project_activity_summary/__init__.py
packages/zoea-core/workflows/builtin/project_activity_summary/flow-config.yaml
packages/zoea-core/workflows/builtin/project_activity_summary/graph.py
packages/zoea-core/workflows/builtin/project_activity_summary/nodes.py
packages/zoea-core/workflows/builtin/project_activity_summary/tests.py
```

### Modified Files
```
packages/zoea-core/workflows/registry.py    - graph_builder discovery
packages/zoea-core/workflows/runner.py      - LangGraph execution path
packages/zoea-core/events/harness.py        - from_execution_run()
packages/zoea-core/events/dispatcher.py     - Updated imports
packages/zoea-core/events/api.py            - Updated for ExecutionRun
packages/zoea-core/flows/api.py             - Updated for ExecutionRun
packages/zoea-core/pyproject.toml           - Added new apps
packages/zoea-core/zoea/settings.py         - Registered new apps
```

### Removed/Deprecated
```
packages/zoea-core/events/models.py         - EventTriggerRun removed (use ExecutionRun)
packages/zoea-core/workflows/models.py      - WorkflowRun removed (use ExecutionRun)
```

---

## Next Steps (Immediate)

1. **Update event dispatcher:**
   - `events/dispatcher.py` to create ExecutionRun and route to LangGraph

2. **Test full trigger → execution flow:**
   - EventTrigger → ExecutionRun → LangGraph → outputs

3. **Add scheduled event support:**
   - Create `ScheduledEvent` model
   - Integrate with Django-Q2 scheduler
   - Wire to `project_activity_summary` workflow

4. **Begin Phase 3: AgentRuntime + Docker:**
   - Define AgentRuntime interface
   - Implement Docker executor with /workspace mount

---

## Open Questions

1. **Legacy Fallback:** Keep PocketFlow fallback for one release, or cut over immediately?
2. **Channel Storage:** Store full transcript in DB, or also support `log.jsonl` (hybrid)?
3. **Docker Runtime Constraints:** What tool/skill constraints beyond ScopedProjectAPI harness?

---

## Architecture Diagram

```
Sources/Adapters → TriggerEnvelope → TriggerRouter → ExecutionRun → LangGraph Runtime → AgentRuntime → OutputAdapters
                                                           ↓
                                                    Channel + ChannelMessage
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
