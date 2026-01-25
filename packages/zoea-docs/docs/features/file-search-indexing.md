# File Search Background Indexing

Automatic background indexing of documents, messages, and project content into a searchable knowledge base using Django-Q2 task queues.

## Overview

Zoea continuously builds a per-project knowledge base by indexing content as it arrives. This happens asynchronously in background tasks, ensuring that:

- API responses are fast (no blocking on indexing)
- Content becomes searchable shortly after creation
- Failed indexing can be retried automatically
- System health can be monitored via management commands

**Design principle:** Indexing is infrastructure, not a workflow. It's deterministic text extraction + vector storage with no LLM reasoning required.

## What Gets Indexed

### Automatic Indexing (Signal-Based)

The following content is automatically queued for indexing when created or updated:

| Content Type | Trigger | Signal Location |
|-------------|---------|-----------------|
| **Documents** | `post_save` on Document | `documents/signals.py` |
| **Chat Messages** | `post_save` on Message (created only) | `chat/signals.py` |
| **Email Messages** | `post_save` on EmailMessage (when `status="processed"`) | `email_gateway/signals.py` |
| **Platform Messages** | `post_save` on PlatformMessage (when `status="processing"`) | `platform_adapters/signals.py` |
| **Project Working Directory** | `post_save` on Project (created only) | `projects/signals.py` |

### Supported Document Types

Files are indexed based on their content:

**Text Documents:**
- Markdown (`.md`, `.markdown`)
- Plain text (`.txt`)
- YAML/JSON (`.yaml`, `.yml`, `.json`)
- CSV (`.csv`)
- D2 Diagrams (`.d2`)

**Binary Documents:**
- PDF (`.pdf`) - Text extracted
- Word Documents (`.docx`) - Text extracted
- Spreadsheets (`.xlsx`) - Text extracted
- Images (`.png`, `.jpg`, `.jpeg`, `.gif`, `.bmp`, `.webp`) - Captioned via AI

### Project Working Directory Import

When a new Project is created with a `working_directory` set, the system automatically:

1. Scans the directory for supported file types
2. Creates Document models for each file
3. Indexes all documents into the project's file search store

**Ignored paths:** `.git`, `.hg`, `.svn`, `__MACOSX`, `.DS_Store`, `node_modules`, `__pycache__`, and all dotfiles/directories.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    Django Signal Handlers                        │
├─────────────────────────────────────────────────────────────────┤
│  documents/signals.py   → queue_document_indexing()             │
│  chat/signals.py        → queue_chat_message_indexing()         │
│  email_gateway/signals.py → queue_email_message_indexing()      │
│  platform_adapters/signals.py → queue_platform_message_indexing()│
│  projects/signals.py    → queue_project_working_directory_indexing()│
└──────────────────────────┬──────────────────────────────────────┘
                           │ transaction.on_commit()
┌──────────────────────────▼──────────────────────────────────────┐
│                     Django-Q2 Task Queue                         │
├─────────────────────────────────────────────────────────────────┤
│  file_search/tasks.py                                            │
│  ├── index_document_task()                                      │
│  ├── index_chat_message_task()                                  │
│  ├── index_email_message_task()                                 │
│  ├── index_platform_message_task()                              │
│  └── index_project_working_directory_task()                     │
└──────────────────────────┬──────────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────────┐
│                  file_search/indexing.py                         │
├─────────────────────────────────────────────────────────────────┤
│  index_document()         - Extracts text, generates captions   │
│  index_chat_message()     - Indexes message content             │
│  index_email_message()    - Indexes email body                  │
│  index_platform_message() - Indexes webhook content + attachments│
└──────────────────────────┬──────────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────────┐
│                   File Search Backend                            │
├─────────────────────────────────────────────────────────────────┤
│  Gemini File Search (default) or ChromaDB                       │
│  - Per-project vector stores                                    │
│  - Semantic search capabilities                                 │
└─────────────────────────────────────────────────────────────────┘
```

## Running the Task Worker

Background indexing requires the Django-Q2 task worker to be running:

```bash
# Start the task worker
python manage.py qcluster

# Or via mise
mise run qcluster
```

Without the worker running, tasks will queue up and execute when the worker starts.

## Management Commands

### Check Indexing Status

View the current state of indexing across the system:

```bash
python manage.py indexing_status
```

**Output sections:**

- **Background Task Queue** - Pending tasks, recent successes/failures
- **Document Sync Status** - Total documents, sync rates, unsynced documents
- **Platform Message Status** - Webhook message indexing status
- **Documents with Sync Errors** - Documents that failed to index

**Options:**

```bash
# Filter by project
python manage.py indexing_status --project "My Project"

# Show only errors
python manage.py indexing_status --errors-only

# Show only pending tasks
python manage.py indexing_status --pending-only

# Limit results
python manage.py indexing_status --limit 50
```

### Reindex Documents

Manually reindex documents for a project:

```bash
# Reindex all documents in a project (inline)
python manage.py reindex_documents --project "My Project"

# Reindex in background via Django-Q2
python manage.py reindex_documents --project "My Project" --background

# Reindex all projects
python manage.py reindex_documents --all --background

# Dry run (see what would be indexed)
python manage.py reindex_documents --project "My Project" --dry-run

# Filter by document type
python manage.py reindex_documents --project "My Project" --type WordDocument

# Force re-extraction (e.g., regenerate image captions)
python manage.py reindex_documents --project "My Project" --force

# Control batch size for background mode
python manage.py reindex_documents --all --background --batch-size 100
```

## Error Tracking

Documents track indexing errors for monitoring and debugging:

| Field | Description |
|-------|-------------|
| `gemini_sync_error` | Error message from last failed sync attempt |
| `gemini_sync_attempts` | Number of sync attempts (for retry tracking) |
| `gemini_synced_at` | Timestamp of last successful sync |

View documents with errors:

```bash
python manage.py indexing_status --errors-only
```

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `FILE_SEARCH_BACKEND` | `chromadb` | Backend to use (`chromadb` or `gemini`) |
| `GEMINI_API_KEY` | *Required for Gemini* | Google Gemini API key |
| `CHROMADB_PERSIST_DIRECTORY` | `None` | Directory for ChromaDB persistence |
| `FILE_SEARCH_MAX_TEXT_BYTES` | `2097152` | Max bytes to read from text files |

### Django Settings

```python
# Disable background indexing (run synchronously instead)
FILE_SEARCH_DISABLE_BACKGROUND_INDEXING = True

# Django-Q2 configuration (in settings.py)
Q_CLUSTER = {
    'name': 'zoea',
    'workers': 2,
    'timeout': 300,
    'retry': 360,
    'queue_limit': 50,
    'bulk': 10,
    'orm': 'default',
}
```

## Skipping Indexing

To skip automatic indexing for specific objects, set the `_skip_file_search` flag before saving:

```python
# Skip document indexing
document = Document(...)
document._skip_file_search = True
document.save()

# Skip project working directory indexing
project = Project(...)
project._skip_directory_indexing = True
project.save()
```

## Task Timeouts

| Task | Timeout |
|------|---------|
| Document indexing | 5 minutes |
| Chat message indexing | 1 minute |
| Email message indexing | 1 minute |
| Platform message indexing | 1 minute |
| Project directory indexing | 10 minutes |
| Full project reindex | 30 minutes |

## Troubleshooting

### Tasks Not Processing

1. Ensure the task worker is running: `python manage.py qcluster`
2. Check for pending tasks: `python manage.py indexing_status --pending-only`
3. Check Django-Q2 admin panel for failed tasks

### Documents Not Being Indexed

1. Verify the document has a project assigned
2. Check for sync errors: `python manage.py indexing_status --errors-only`
3. Ensure the file search backend is configured correctly
4. Check that `FILE_SEARCH_DISABLE_BACKGROUND_INDEXING` is not set

### Platform Messages Not Indexed

Platform messages require:
- `status="processing"` (set after successful webhook validation)
- A `project` assigned to the message/connection

Messages without a project cannot be indexed (no project-scoped store).

### Working Directory Not Imported

Project working directory import requires:
- The project was newly created (not updated)
- `working_directory` is set and exists on disk
- `_skip_directory_indexing` flag is not set

## Related Features

- [Document RAG Chat](document-rag.md) - Interactive chat with documents
- [Gemini Search](gemini-search.md) - CLI-based document search
- [Email Gateway](email-gateway.md) - Email message processing
