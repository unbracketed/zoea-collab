# Document Preview Architecture

## Goals
- Offer rich preview/thumbnail experiences (grid/icon cards, hover previews, clipboard chips) so users understand a document without opening it.
- Keep preview generation isolated per document type so new formats can plug in without branching logic.
- Cache rendered artifacts and expose lightweight metadata so both backend APIs and frontend UI can stay responsive.
- Respect Zoea Collab's multi-tenant boundaries (organization → project → workspace) and fit within the existing Documents app.
- Stay in lockstep with Project Sources: previews must refresh when `sync_sources` imports/updates files so source-backed documents never show stale thumbnails.

## Preview Surfaces & Requirements
- **Documents list**: toggleable list vs. icon grid, with thumbnails plus key metadata.
- **Document pickers**: clipboard modal, workflow inputs, etc. should reuse preview data.
- **Clipboard panels**: show the cached preview snippet (image or HTML snippet) next to item names.
- **Future surfaces**: conversation attachments, workspace canvases, and hovercards.
- Previews should degrade gracefully (status badge + fallback icon) if rendering fails or is still pending.

## Architecture Overview
1. **DocumentPreview model** holds cached artifacts per document and preview_kind (thumbnail, snippet, hero, etc.).
2. **Project Sources** (local/S3/R2) sync into Documents; each create/update should immediately schedule preview renders using source metadata (path, etag/mtime, size) for hashing.
3. **PreviewRenderer strategies** (one per document type) generate preview assets and metadata.
4. **PreviewService** orchestrates when to render (on create/update/scheduled refresh), persists results, and invalidates stale caches.
5. **Async jobs** perform heavy rendering work (D2 → SVG rasterization, PDF page rasterization, Markdown-to-HTML screenshot).
6. **Documents API** exposes preview metadata on list/detail responses and provides explicit refresh endpoints.
7. **Frontend preview hooks/store** cache preview JSON and render either an `<img>` thumbnail or sanitized HTML snippet inside reusable components.

```
Project Source sync ─► Document.save() ──► PreviewService.mark_stale(document)
                               │
                      job queue enqueue
                               ▼
                     PreviewRendererRegistry
                        │            │
                MarkdownRenderer   D2Renderer ...
                        │
               PreviewArtifact (image path, svg, html)
                        │
                DocumentPreview row (ready)
                        │
         /api/documents?include_preview=grid
                        │
        Frontend DocumentCard / Clipboard chips
```

## Domain Model Additions (backend/documents/models.py)
`DocumentPreview`
- `document` FK + denormalized `organization/project/workspace` for scoping.
- `preview_kind` (choices: `thumbnail`, `snippet`, `large`), `status` (pending, processing, ready, failed).
- `content_hash` tracks the input signature so we skip regeneration when nothing changed.
- `target_hash` stores the content hash that triggered the render so workers can confirm they are still current before marking `status='ready'`.
- `preview_file` (`ImageField`, stored under `media/previews/YYYY/MM/DD/`).
- `preview_svg` (TextField) or `preview_html` (TextField) for formats that stay vectorized.
- `metadata` JSONField (dominant color, width/height, text snippet, render notes, optional `source_path`/`source_version` for Project Source traceability).
- `file_size` (IntegerField) for storage quota tracking.
- `last_accessed` (DateTimeField) for inactivity-based expiration.
- `generated_at`, `expires_at`, `error_message`.
- Unique constraint on `(document_id, preview_kind)` so each document has deterministic slots.

Optional helper: `DocumentPreviewQuerySet.ready()` and `Document.preview_for(kind)` for easy access, along with a scoped manager (extends `OrganizationScopedQuerySet`) to guarantee every preview lookup honors org/project/workspace boundaries.

## Preview Pipeline & Boundaries
### PreviewService (`backend/documents/preview_service.py`)
- `schedule_preview(document, preview_kind='thumbnail')`: computes current hash → if changed, create/update `DocumentPreview` row (`status=pending`, `target_hash=current_hash`) and enqueue async job.
- `generate_preview(preview_id)` (invoked by worker) resolves preview + document using `Document.objects.select_subclasses()` (or a stored model label) so renderer-specific fields are present, selects renderer, and persists results.
- Workers compare the document's latest `content_hash` against the preview row's `target_hash`; mismatches mark the preview `status='stale'` and queue a fresh job instead of overwriting with stale artifacts.
- `touch_document(document)` called from `post_save` signals or manual `preview:refresh` API to mark previews stale.
- Source integrations: `sync_sources` → document create/update should immediately call `schedule_preview` and carry over `DocumentMetadata` info (`path`, `modified_at`, `etag` if present) so hashing/invalidation matches upstream state without rereading large blobs.
- Accepts optional `force=True` flag to bypass hash comparison.
- Exposes query helpers so other apps (clipboard, workflows) can request preview metadata by document IDs in bulk, with every call validating organization scoping before returning rows.

### PreviewRenderer Registry (`backend/documents/previewers/__init__.py`)
- Base protocol:
  ```python
  class PreviewRenderer(Protocol):
      supported_kinds: tuple[str, ...] = ('thumbnail',)
      def render(self, document: Document, *, kind: str) -> PreviewArtifact: ...
  ```
- Registry maps model class → renderer instance (fallback renderer handles unsupported types and returns icon metadata only).
- `PreviewArtifact` dataclass contains `file_bytes`, `file_mime`, `svg`, `html`, `width`, `height`, `metadata`.
- Renderers may call out to helper libs (e.g., Markdown to HTML using `markdown-it-py`, D2 via `d2-python-wrapper`) but return consistent artifacts.
- Register dedicated renderers for `MermaidDiagram` and `JSONCanvas` alongside existing D2/ReactFlow handlers so new document types participate in the same orchestration/fallback path.

### Storage & Cache Keys
- Compute `content_hash` differently per type:
  - Text-based types: hash of `document.content` + `updated_at`.
  - File uploads (Image/PDF): hash of `FileField` content hash (md5) + file size + mtime.
  - Diagram (React Flow): hash normalized JSON (sorted keys) to avoid needless rerenders.
  - Source-backed docs: include upstream `doc_meta.modified_at`/`etag` and `source_id` + `source_path` so external updates invalidate caches even before the blob is pulled again.
- Optionally append `renderer_version` (Semantic version constant per renderer) to the hash so style tweaks trigger regeneration.
- Store generated files under deterministic paths (e.g., `MEDIA_ROOT/previews/{document_id}/{preview_kind}.webp`) or delete the previous stored file before saving the new one so repeated renders do not leak orphaned media.
- For SVG, keep original text (FE can inline with `<object>` or convert to PNG client-side).

## Document-Type Rendering Strategies

### Phase 1-2: Core Renderers (including new document types)
| Type | Rendering Strategy | Notes |
|------|-------------------|-------|
| **Image** | Use Pillow to resize the original while maintaining aspect ratio, respect EXIF orientation, center-crop to 4:3 for thumbnails, store WebP + dominant color + intrinsic dimension metadata. | End-to-end support exists; safe to run inline for uploads, but Source-backed imports should route through worker to avoid blocking sync. |
| **PDF** | Use PyMuPDF (or pdf2image) to rasterize page 1 at low DPI, downscale to 240×180, store WebP plus page count overlay metadata. | CPU intensive; do via worker. Cache page count to avoid repeated parse. |
| **Markdown/Text** | Render Markdown → HTML (`markdown-it-py`) with "preview.css" (smaller fonts, limited width). Store sanitized HTML snippet. Provide plain-text fallback for clipped text. | Allows FE to display inline HTML without extra requests. |
| **CSV** | Generate HTML table snippet (first N rows/columns) styled with preview CSS, plus optional sparkline metadata (computed server-side). | Keep data limited for privacy; metadata includes truncated cell counts. |
| **D2Diagram** | Use `d2-python-wrapper` library to produce SVG (`D2().render(d2_script, layout="elk", theme="200")`). Store raw SVG + pre-rendered PNG for thumbnail. Add metadata for viewport transforms. | Library bundles official D2 binaries; no subprocess management needed. |
| **MermaidDiagram** | Render via `@mermaid-js/mermaid-cli` (Node + headless Chromium) to SVG, then downscale to WebP thumbnail; capture library version in `renderer_version`. Provide text snippet fallback if CLI is unavailable. | Prioritize for parity with new document type; run in worker to avoid blocking web dyno. |
| **JSONCanvas** | Parse canvas JSON, normalize coordinates, and render with shared React/XYFlow canvas component in Playwright to produce PNG + metadata (node count, bounds). | New document type; headless renderer shares infra with ReactFlow. Provide metadata-only fallback when headless is not configured. |
| **Other TextDocument** | Provide simple text snippet (first ~200 chars) rendered via preview CSS. | |

### Phase 3: Advanced Renderers (Deferred)
| Type | Rendering Strategy | Notes |
|------|-------------------|-------|
| **ReactFlowDiagram** | Use Playwright to render ReactFlow JSON in headless browser. Store PNG + JSON metadata for FE (node count, bounding box). | Shares headless stack with JSONCanvas; requires Node-based headless Chromium. |
| **Complex HTML** | Use Playwright for pixel-perfect HTML/CSS rendering where Python-native tools fall short. | For documents with advanced CSS or JavaScript-dependent layouts. |

### Rendering Stack Strategy
- **Primary approach**: Python-native tools for simplicity, performance, and single-language stack benefits.
- **Headless/Node**: Needed for Mermaid (`@mermaid-js/mermaid-cli`) and JSON Canvas/ReactFlow (Playwright + shared React component). Provide metadata-only fallback if headless tooling is not installed, but plan to provision it in dev/prod because these document types are now first-class.
- **Benefits of hybrid approach**:
  - Start simple with 80% of cases
  - Extend with browser rendering where fidelity matters (diagrams/canvas)
  - PreviewRenderer registry architecture naturally supports multiple rendering backends

## API & Data Contract
- `GET /api/documents` accepts `include_previews=true` and optional `preview_kind=thumbnail`. Response `DocumentOut` gains `preview` object:
  ```json
  {
    "thumbnail": {
      "status": "ready",
      "url": "https://.../media/previews/...webp",
      "width": 240,
      "height": 180,
      "metadata": { "dominant_color": "#112233", "text_snippet": "..." }
    }
  }
  ```
- `GET /api/documents/{id}` returns same data plus HTML snippet when available.
- `POST /api/documents/{id}/previews/{kind}/refresh` marks preview stale and triggers regeneration.
- Batch endpoint `POST /api/documents/previews/bulk` lets clipboard/workflow features fetch preview metadata for arbitrary IDs without pulling full documents.
- Source-backed docs: include safe `source_path`/`source_type` in preview `metadata` so UI can surface "Synced from <source>" and debugging can correlate freshness with upstream files.

Schema updates live in `backend/documents/schemas.py` (new `DocumentPreviewOut`).

## Frontend Boundaries
- Create `frontend/src/components/DocumentCard.jsx` shared by grid/list modes; pulls preview data and decides whether to render `<img>`, inline sanitized HTML via secure wrapper component, or fallback icon.
- Maintain `useDocumentPreviews` hook (Zustand store) keyed by document ID + preview_kind for caching/inflight status; handles refresh if backend returns `pending`.
- `DocumentsPage` adds a view toggle button (list vs. grid) and uses CSS grid for icon layout.
- Provide `PreviewThumbnail` component for other surfaces (clipboard, pickers) to keep consistent styling.
- Diagram/canvas cards (Mermaid, JSON Canvas, ReactFlow) should display type-aware placeholders and offer a manual refresh CTA when headless rendering is unavailable.
- StrictMode-friendly data loading: follow patterns in `docs/react-strictmode-patterns.md` (double-invoke safe effect) and support Suspense-friendly API in the future.

## Security: HTML Sanitization

### Defense-in-Depth Strategy
Multi-tenant security requires layered protection against XSS attacks from malicious document content.

**Backend Sanitization (Primary Defense)**:
- Use `nh3` (Rust-backed, faster than bleach) to sanitize HTML before storing in `DocumentPreview.preview_html`
- Sanitize during preview generation in async workers (performance impact mitigated)
- Apply strict allow-list for tags and attributes:
  - Disallow: `<script>`, `<iframe>`, `on*` event handlers
  - Disallow: `style` attributes with external resources (e.g., `background-image: url(...)`)
  - Allow: Basic formatting tags (`<p>`, `<div>`, `<span>`, `<strong>`, `<em>`, etc.)
- Prevents persistent XSS by ensuring malicious HTML never reaches the database
- **Critical**: Sanitize ALL HTML snippets before storage

**Frontend Sanitization (Defense-in-Depth)**:
- Use `DOMPurify` library in React components to sanitize HTML before rendering
- Apply similarly strict (or stricter) allow-list as backend
- Create wrapper component or custom hook to ensure consistency and prevent XSS
- **SECURITY REQUIREMENT**: Always sanitize HTML before using React's HTML rendering capability
- Protects against:
  - Bugs or misconfigurations in backend sanitization
  - Future code paths that might bypass backend sanitization
  - Scenarios where API consumers might receive unsanitized HTML

**Rationale**:
- Multi-tenant environment requires maximum security posture
- "Stored once, displayed many times" pattern favors backend sanitization
- Frontend layer provides safety net against backend failures
- Redundancy overhead is negligible compared to XSS risk mitigation

**Testing**:
- Integration tests verifying both layers strip malicious content
- Test cases: `<script>` tags, event handlers, `<iframe>`, external resources
- Document sanitization strategy and library configurations

## Async Task Queue: Celery

### Architecture Decision
Use **Celery with Redis** as the distributed task queue for preview generation.

**Why Celery**:
- Industry standard for Django async tasks
- Already referenced in `transformations/EXAMPLES.md` (standardization benefit)
- Robust feature set: advanced retries, scheduling, monitoring, worker pools
- Excellent multi-tenant isolation via task routing
- Mature ecosystem with proven reliability

**Setup**:
- **Broker/Backend**: Redis (simpler than RabbitMQ for most use cases)
- **Dependency Management**: `uv` for Python packages
- **Monitoring**: Flower for task status and debugging
- **Scheduling**: Celery Beat for periodic cleanup tasks

**Multi-Tenant Isolation**:
- Define tenant-specific queues (e.g., `tenant_A_previews_queue`)
- Workers configured to listen to specific queues
- Pass tenant IDs/context to tasks for scoped operations
- Prevents one tenant's heavy workload from blocking others

**Configuration**:
- Manage via Django settings or environment variables
- Define queue routing rules in Celery configuration
- Set up retry logic and failure handling policies

## Performance, Storage & Cleanup

### Storage Management Strategy

**Phase 1: Monitoring & Basic Cleanup (Immediate)**

1. **Automatic File Deletion**:
   - Use `django-cleanup` library for automatic file deletion when `DocumentPreview` instances are deleted
   - Cascades from `Document` deletion (via `on_delete=models.CASCADE`)
   - Handles preview files without manual signal management

2. **File Size Tracking**:
   - Add `file_size` field (IntegerField) to `DocumentPreview` model
   - Record file size when preview is generated
   - Enables per-organization storage aggregation

3. **Orphan Cleanup**:
   - Management command: `cleanup_orphaned_previews`
   - Scans `media/previews/` directory
   - Reconciles file system with database
   - Deletes files without corresponding `DocumentPreview` records
   - **Must include `--dry-run` option** for safe testing
   - Schedule periodically (weekly or monthly)

**Phase 2: Usage Monitoring (Follow-up)**

1. **Per-Organization Aggregation**:
   - Periodic task aggregates total preview storage per `Organization`
   - Store in dedicated `OrganizationStorageMetrics` model or cache
   - Track historical usage trends

2. **Soft Limit Alerts**:
   - Set up internal alerts (Slack, email) for high usage
   - Trigger at 80% of anticipated "free tier" limit
   - Gives team time to investigate or contact customer

**Phase 3: Advanced Features (As Needed)**

1. **Inactivity-Based Expiration**:
   - Add `last_accessed` (DateTimeField) to `DocumentPreview` model
   - Update field when preview is retrieved/served
   - Management command deletes previews unused for N days (e.g., 90-180 days)
   - Regenerate on demand when accessed again

2. **Hard Quota Enforcement**:
   - Implement only after gathering real usage data
   - Consider tiered approach (free tier, paid tiers)
   - Design quota check logic in `PreviewService`
   - Build UI for users to view storage usage

**Storage Targets**:
- Default thumbnail size: 240×180 WebP (~10–20 KB)
- HTML snippets: <4 KB
- Typical organization: estimate 100-500 documents with previews

**Cleanup Policies**:
- Nightly job detects stale previews (hash mismatch, TTL expired) and enqueues refresh
- `max_attempts` + exponential backoff for preview jobs to prevent thrashing on chronic failures
- Privacy: ensure previews inherit same `Organization` scoping via `OrganizationScopedQuerySet`

**Rationale**:
- Storage is relatively cheap; avoid premature optimization with hard quotas
- Regenerating previews is expensive; keep caches warm
- Gather usage data before committing to specific limits
- Multi-tenant isolation: one org's storage shouldn't affect others

## Implementation Phases

### Phase 1: Scaffold & Models
**Goal**: Foundation for preview system without rendering implementation.

**Tasks**:
- Create `DocumentPreview` model with all fields (including `file_size`, `last_accessed`) and Source trace data in `metadata` (`source_id`, `source_path`, `source_version`).
- Add migrations and register model in Django admin.
- Create `PreviewRenderer` protocol and registry skeleton.
- Implement fallback renderer (returns icon/placeholder metadata only).
- Add `PreviewService` class with method stubs.
- Wire `post_save` signals for content-changing fields only (avoid coupling all saves)
  - Only trigger on fields that affect preview: `content`, file uploads, diagram data
  - Avoid triggering on folder moves, Gemini metadata updates (prevent circular imports)
- Teach `sync_sources` pipeline to call `PreviewService.schedule_preview()` after create/update so Project Source imports start producing previews immediately.

**Dependencies**:
- `django-cleanup` for automatic file deletion

**Testing**:
- Model creation/deletion works correctly
- Admin interface displays preview records
- Signals fire only for relevant field changes

### Phase 2: Essential Renderers & API
**Goal**: Working preview system for core document types.

**Tasks**:
- Implement renderers:
  - `ImageRenderer`: Pillow resize/crop → WebP, respect EXIF, ensure Source-imported images stream through worker path instead of blocking `sync_sources`.
  - `PDFRenderer`: PyMuPDF rasterization of page 1 with cached page count metadata.
  - `MarkdownRenderer`: markdown-it-py → sanitized HTML (nh3).
  - `CSVRenderer`: First N rows → HTML table snippet.
  - `D2Renderer`: d2-python-wrapper → SVG.
  - `MermaidRenderer`: invoke `@mermaid-js/mermaid-cli` when available; otherwise return text snippet + "preview unavailable" metadata so Mermaid docs still render in grids.
  - `JSONCanvasRenderer`: return metadata fallback (node count, bounds, colors) while wiring to shared headless renderer in Phase 3; avoid empty previews for this new type.
- Implement `PreviewService.schedule_preview()` and content hash logic using Source metadata (`modified_at`, `etag`, `source_path`) plus renderer versioning.
- Expose previews via `GET /api/documents` (add `include_previews` param) and optionally surface `source_path` in preview metadata for audit.
- Add `DocumentPreviewOut` schema.
- Create `POST /api/documents/{id}/previews/{kind}/refresh` endpoint.
- Frontend: `DocumentCard` component with fallback preview display, including new diagram/canvas placeholders.
- Frontend: List/grid toggle in `DocumentsPage`.

**Dependencies**:
- `pillow` for image processing
- `markdown-it-py` for Markdown → HTML
- `nh3` for HTML sanitization
- `d2-python-wrapper` for D2 diagrams
- `pymupdf` for PDF rendering

**Testing**:
- Each renderer produces correct output format
- Hash-based regeneration skips unchanged documents
- API returns preview metadata correctly
- Frontend displays thumbnails and HTML snippets

### Phase 3: Heavy Renderers & Async Queue
**Goal**: Production-ready system with async workers and cleanup.

**Tasks**:
- Set up Celery with Redis
  - Install Redis locally/CI/production
  - Configure Celery broker and result backend
  - Define task routing for multi-tenant isolation
- Wire `PreviewService.generate_preview()` to Celery tasks
- Move heavy renderers to workers:
  - Mermaid → `@mermaid-js/mermaid-cli` SVG/PNG path
  - JSON Canvas → Playwright + shared React renderer
  - ReactFlow → Playwright path reused by JSON Canvas
- Add retry logic and failure handling
- Implement content hash validation in workers (`target_hash` check)
- Create `cleanup_orphaned_previews` management command (with `--dry-run`)
- Set up Celery Beat for scheduled tasks:
  - Nightly stale preview detection and refresh
  - Weekly orphan cleanup
- Monitoring: integrate Flower for task inspection

**Dependencies**:
- `celery[redis]`
- `redis` (server)
- `flower` for monitoring

**Testing**:
- Preview jobs execute asynchronously
- Retry logic handles failures correctly
- Orphan cleanup command identifies and removes stale files
- Multi-tenant task routing isolates workloads

### Phase 4: Secondary Surfaces & Polish
**Goal**: Integration with other features and advanced capabilities.

**Tasks**:
- Integrate previews into clipboard panel
- Add preview support to document pickers (workflow inputs)
- Implement `POST /api/documents/previews/bulk` endpoint
- Frontend: `useDocumentPreviews` Zustand store
- Frontend: `PreviewThumbnail` component for reusable preview display
- Add metrics/logging:
  - Preview generation time per document type
  - Failure counts and error types
  - Cache hit/miss rates
- Implement per-organization storage monitoring
  - Aggregation task for total preview storage
  - Internal alerts for high usage
- Add `last_accessed` tracking and inactivity-based expiration
- Consider multiple preview kinds per document (thumbnail + snippet + large)
- **Optional**: Higher-fidelity variants (hero-size previews, transparent PNGs for diagrams) once headless stack is stable

**Dependencies**:
- None beyond the Playwright/mermaid-cli stack introduced earlier.

**Testing**:
- Previews display correctly in all UI surfaces
- Bulk endpoint handles large ID lists efficiently
- Storage monitoring accurately tracks per-org usage
- Inactivity expiration cleans up old previews

## Decisions & Rationale

### 1. Rendering Stack: Hybrid Approach
**Decision**: Python-first for text/image/pdf/d2, with Node/Playwright as a built-in path for diagram/canvas types (Mermaid, JSON Canvas, ReactFlow); metadata fallbacks stay in place when headless tooling is unavailable.

**Rationale**:
- New document types (Mermaid, JSON Canvas) require browser-grade rendering for fidelity
- Python-native tools still cover the majority of docs with simpler deployment
- PreviewRenderer registry cleanly routes to either stack without branching logic elsewhere
- Async workers absorb the extra weight of headless Chromium and mermaid-cli

**Trade-offs**:
- Node + Chromium dependency in CI/CD and dev containers
- Need clear fallback states when headless deps are missing
- Slightly higher maintenance due to dual toolchains

### 2. Async Executor: Celery
**Decision**: Use Celery with Redis as the distributed task queue.

**Rationale**:
- Consistency with existing `transformations/EXAMPLES.md` architecture
- Robust multi-tenant isolation via task routing to dedicated queues
- Battle-tested retry logic, scheduling (Celery Beat), and monitoring (Flower)
- Scales independently from web application
- Industry standard with mature ecosystem

**Trade-offs**:
- Requires Redis infrastructure (but common in modern web apps)
- More complex than Django-Q2 with ORM backend
- Worth the investment for heavy operations and multi-tenancy requirements

### 3. D2 Renderer: d2-python-wrapper
**Decision**: Use `d2-python-wrapper` library instead of running D2 binary directly.

**Rationale**:
- Bundles official D2 binaries (full feature support, accurate layouts)
- Clean Python API without subprocess management
- Zero external dependencies or tool version management
- Simpler than extending Graphologue (which is ReactFlow-focused)
- Avoids lossy D2→ReactFlow conversion

**Trade-offs**:
- None significant; this is the best of all worlds

### 4. Storage Quotas: Phased Approach
**Decision**: Defer hard quotas, implement monitoring first, add enforcement later based on usage data.

**Rationale**:
- Storage is relatively cheap; premature optimization adds complexity
- Need real usage data to set appropriate limits
- Monitoring + alerts provide early warning of cost issues
- Preview regeneration is expensive; keep caches warm
- Can add hard quotas later without architectural changes

**Phase 1 (Immediate)**:
- `django-cleanup` for automatic file deletion
- Track `file_size` on `DocumentPreview` model
- Orphan cleanup management command with `--dry-run`

**Phase 2 (Follow-up)**:
- Per-organization usage aggregation and alerts
- `last_accessed` field for inactivity-based expiration

**Phase 3 (As Needed)**:
- Hard quota enforcement based on gathered usage data

**Trade-offs**:
- Risk of higher-than-expected storage costs initially (mitigated by monitoring)
- Users won't hit unexpected limits during early usage

### 5. HTML Sanitization: Defense-in-Depth
**Decision**: Sanitize both server-side (nh3) and client-side (DOMPurify).

**Rationale**:
- Multi-tenant security requires layered protection against XSS
- Backend sanitization prevents persistent XSS (malicious HTML never reaches database)
- Frontend sanitization provides safety net against backend failures
- "Stored once, displayed many times" pattern favors backend sanitization
- Performance overhead negligible compared to security benefits

**Implementation**:
- Backend: `nh3` (Rust-backed, fast) with strict allow-lists
- Frontend: `DOMPurify` to sanitize before rendering HTML with wrapper component
- Both layers apply strict tag/attribute filtering

**Trade-offs**:
- Slight redundancy in sanitization work
- Worth the investment for maximum security in multi-tenant environment

## Dependencies

### Backend (Python)
```
# Core preview system
django-cleanup>=8.0.0         # Automatic file deletion on model deletion
nh3>=0.2.0                    # HTML sanitization (Rust-backed)

# Rendering libraries
Pillow>=10.0.0                # Image processing and thumbnail generation
PyMuPDF>=1.23.0               # PDF page rasterization
markdown-it-py>=3.0.0         # Markdown to HTML conversion
d2-python-wrapper>=0.1.0      # D2 diagram rendering (bundles D2 binaries)
@mermaid-js/mermaid-cli       # Mermaid -> SVG/PNG (Node tool invoked from workers)

# Async task queue
celery[redis]>=5.3.0          # Distributed task queue
redis>=5.0.0                  # Celery broker/backend
flower>=2.0.0                 # Celery monitoring dashboard

# Headless/browser tooling (Phase 3)
playwright>=1.40.0            # Headless browser for Mermaid/JSON Canvas/ReactFlow rendering
```

### Frontend (Node.js)
```json
{
  "dependencies": {
    "dompurify": "^3.0.0",  // HTML sanitization before rendering
    "zustand": "^4.4.0"     // State management (already in project)
  },
  "devDependencies": {
    "@mermaid-js/mermaid-cli": "^10.9.0", // Diagram preview rendering
    "playwright": "^1.40.0"               // Shared headless renderer for Mermaid/JSON Canvas/ReactFlow
  }
}
```

### Infrastructure
- **Redis**: Message broker for Celery (local/Docker for development, managed service for production)
- **Storage**: Cloud object storage (S3, Azure Blob) recommended for production; local filesystem for development

## Future Considerations

### Potential Enhancements
1. **Multiple Preview Sizes**: Support `thumbnail`, `medium`, `large` sizes per document
2. **Video Previews**: Frame extraction for video documents
3. **Audio Waveforms**: Visual waveform previews for audio files
4. **Live Preview Updates**: WebSocket notifications when preview generation completes
5. **Preview History**: Track preview versions over time for debugging
6. **Custom Preview Styles**: Per-organization theming for preview rendering
7. **Preview Analytics**: Track which previews are viewed, clicks, hover time

### Scalability Considerations
1. **CDN Integration**: Serve preview files via CDN for global performance
2. **Tiered Storage**: Move old previews to cheaper cold storage
3. **Distributed Workers**: Scale Celery workers across multiple machines
4. **Preview Prioritization**: High-priority previews (frequently accessed) vs. low-priority
5. **Batch Generation**: Generate previews in batches during off-peak hours

### Security Hardening
1. **URL Signing**: Use Azure Blob/S3 signed URLs for preview access (if moving beyond cookie auth)
2. **Rate Limiting**: Prevent preview generation abuse
3. **Content Security Policy**: Strict CSP headers for preview HTML rendering
4. **Sandboxing**: Isolated preview rendering environments for untrusted content

## References
- [Django-cleanup](https://github.com/un1t/django-cleanup) - Automatic file deletion
- [nh3](https://github.com/messense/nh3-python) - Fast HTML sanitization
- [DOMPurify](https://github.com/cure53/DOMPurify) - Client-side HTML sanitization
- [d2-python-wrapper](https://github.com/diegocarrasco/d2-python-wrapper) - Python interface for D2 diagrams
- [Mermaid CLI](https://github.com/mermaid-js/mermaid-cli) - SVG/PNG rendering for Mermaid diagrams
- [Celery](https://docs.celeryq.dev/) - Distributed task queue
- [Flower](https://flower.readthedocs.io/) - Celery monitoring tool
- [PyMuPDF](https://pymupdf.readthedocs.io/) - PDF processing library
- [Playwright](https://playwright.dev/python/) - Browser automation for diagram/canvas rendering
