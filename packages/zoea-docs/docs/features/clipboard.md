# Clipboard Architecture Plan

## Goals
- Provide a reusable "clipboard" concept that captures ordered snippets of context a user needs while working in a workspace session.
- Introduce a single managed clipboard per user/workspace that behaves like a deque and allows both persistent Django model attachments and ephemeral workspace nodes.
- Support seamless activation/switching of clipboards per workspace/user and keep a list of "recent" clipboards for recall.
- Offer APIs and services so other Django apps (chat, documents, workflows, etc.) can push, mirror, or query clipboard items without duplicating business rules.

## Core Concepts
- **Clipboard**: base abstraction (one active per user/workspace) with metadata, activation state, and ordering information.
- **ClipboardItem**: ordered container pointing either to a Django model (GenericForeignKey) or to a VirtualClipboardNode for transient payloads. Keeps enqueue direction plus metadata for previews and provenance.
- **VirtualClipboardNode**: durable representation of ephemeral artifacts (draft canvas, temporary workflow output, code snippet) with JSON payload/preview that may later materialize into a first-class model.
- **ClipboardSession/History (optional)**: stores serialized snapshots to implement "save clipboard" or template reuse.

## Relationships
```
User 1---* Clipboard
Workspace 1---* Clipboard
Clipboard 1---* ClipboardItem
ClipboardItem *---1 Generic Model
ClipboardItem *---1 VirtualClipboardNode
```
- Clipboards are scoped to both `user` and `workspace`. Each workspace maintains exactly one active clipboard per user while allowing archived/recent copies.

## Model Design
### Clipboard (abstract base)
Fields:
- `id`
- `workspace` FK → `workspaces.Workspace`
- `owner` FK → `auth.User`
- `name`, `description`
- `is_active` (tracks which clipboard is current for a workspace/user)
- `is_recent` (tracks previously active clipboards)
- `activation_rank` or `activated_at` for ordering active/recent lists
- `metadata` JSONField for UI preferences (auto-sync flags, color, tags)
- `created_at`, `updated_at`

Constraints & behavior:
- Unique `(workspace, owner, is_active=True)` enforced through custom manager + DB constraint.
- Manager helpers: `active_for(workspace, owner)`, `recent_for(...)`, `activate(clipboard)` (deactivates previous and marks as recent).

### ClipboardItem
Fields:
- `clipboard` FK
- `position` (integer for ordering) + `deque_group` counters for O(1) push (e.g., `sequence_head`, `sequence_tail` stored on clipboard)
- `direction_added` (`left`/`right`)
- `added_by` FK → `User`
- `is_pinned`
- `content_type`, `object_id` (nullable)
- `virtual_node` FK (nullable)
- `source_metadata` JSON (highlights, snippet text, workspace node reference)
- `source_channel` choice (conversation, workflow, canvas, etc.)
- `created_at`, `updated_at`

Behavior:
- Provide helper methods `push_left`, `push_right`, `pop_left`, `pop_right`, `reorder(new_index)` executed through `ClipboardService`.
- Signals (future) can react to clipboard item lifecycle events for analytics or cleanup.

### VirtualClipboardNode
Fields:
- `node_type` (diagram, workflow_artifact, draft_doc, code_snippet, etc.)
- `payload` JSON/Text storing raw content or serialized data
- `preview_text`, `preview_image`
- `origin_reference` metadata (source message id, workflow step, etc.)
- `expires_at` (optional TTL for cleanup)
- `materialized_content_type/object_id` (optional link once the item has been saved elsewhere)
- `created_at`, `updated_at`, `created_by`

## Services & Logic
### ClipboardService
Responsibilities:
1. `get_or_create_active_clipboard(workspace, owner)` ensuring exactly one active clipboard per workspace/user.
2. `activate_clipboard(clipboard)` moves prior actives to recent and updates `activated_at` ordering metadata.
3. `create_clipboard_from_template(source_clipboard, name)` clones metadata + optionally references existing items.
4. `add_item` (explicit) takes `content_type/object_id` or `virtual_payload`, direction, and metadata. Handles dedup rules and ordering updates.
5. `pop_item`, `remove_item`, `clear_clipboard`, `reorder_items` (bulk reorder patch).
6. `convert_virtual_to_model(virtual_node, model_instance)` updates reference and notifies watchers.
7. `export_clipboard` / `import_clipboard` for templates/recent recall.

### Query Utilities
- `ClipboardQuerySet` extends `OrganizationScopedQuerySet` to filter by `workspace__project__organization` ensuring cross-app security.
- `ClipboardItemQuerySet` helper filters (by `content_type`, `added_by`, `pinned`).

### Signals & Integration
- Signals: `clipboard_activated`, `clipboard_item_added`, `clipboard_item_removed`, `virtual_node_materialized`.
- Other apps listen for signals to display analytics, mark tasks as referencing clipboard items, etc.
- Hook into deletion of referenced models (via Django's `on_delete=SET_NULL` or `pre_delete` receivers) to either remove or mark clipboard items stale.

## API Surface (Django Ninja)
Routers under `/api/clipboards/` in the app:
1. `GET /clipboards/` – list active clipboards filtered by `workspace_id` (optional `include_recent`).
2. `POST /clipboards/` – create a new clipboard (optionally activate immediately).
3. `GET /clipboards/{id}` – retrieve clipboard metadata (optionally include items).
4. `POST /clipboards/{id}/activate` – switch the active clipboard for that workspace/user.
5. `GET /clipboards/{id}/items` – ordered list of clipboard items.
6. `POST /clipboards/{id}/items` – add a clipboard item (supports `direction`, `content_type`, `object_id`, `virtual_payload`).
7. `DELETE /clipboards/{id}/items/{item_id}` – remove an item.
8. `POST /clipboards/{id}/items/reorder` – reorder items using `{item_id, position}` payloads.
9. `GET /clipboards/{id}/export` – export clipboard contents (Markdown initially).

Schemas should mirror patterns in existing apps (e.g., `WorkspaceDetailResponse`). Provide consistent metadata for UI (preview text, tags, origin info).

## Views & UI Hooks
- Workspace-level page displays the active clipboard plus a drawer for recent clipboards.
- Provide UI operations for reorder, delete, push/pop, and pinning.
- Recent clipboards view lists archived clipboards with `activated_at`, `item_count`, and allows re-activation or deletion.

## Permissions & Security
- All clipboard queries filtered through organization scoping from the workspace relationship.
- Users must belong to workspace's project organization via existing membership models.
- Clipboard item attachments enforce `ClipboardAttachable` interface or permission checks (e.g., verifying user can view referenced document/conversation).
- Expose audit trails for clipboard activation and item addition to maintain traceability.

## Data Lifecycle & Maintenance
- Optional TTL cleanup job for expired `VirtualClipboardNode`s.
- When workspace is archived/deleted, cascade delete or archive corresponding clipboards and nodes.
- Provide management command to re-sync `position` values if sequences drift.
- Consider storage limits per clipboard (max items) and apply FIFO eviction (pop opposite end) when limit reached.

## Testing Strategy
- Model tests verifying constraints (single active clipboard per workspace/user and deletion cascades).
- Service tests covering push/pop/reorder, activation flow, and virtual node conversions.
- API tests (permissions, serialization) using Django Ninja test client and factories for attached models.
- Integration tests ensuring clipboard operations surface correctly in chat, documents, and canvas flows.
- Cleanup tests verifying expired virtual nodes are purged by cron/management command.

## Implementation Milestones
1. **Scaffold App**: `python manage.py startapp context_clipboards`, add to `INSTALLED_APPS`, create migrations for base models.
2. **Models & Querysets**: implement Clipboard, ClipboardItem, VirtualClipboardNode with constraints and helper methods.
3. **Service Layer**: build `services.py` (ClipboardService) plus optional signals for analytics/cleanup.
4. **API Layer**: add Ninja router, schemas, and endpoints for clipboards/items.
5. **Admin & Fixtures**: register models, add search/filter, seed data for dev/testing.
6. **Tests**: create factories, unit/integration tests for models, service, API.
7. **Frontend Integration (future)**: expose endpoints to FE; ensure cross-app hooks (chat, workflows, documents) call service functions to add items.
