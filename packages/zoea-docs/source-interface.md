# Source Interface Specification

## Overview

The Source interface provides an abstraction layer for document storage backends in Zoea Collab. This design allows projects to pull documents from various storage locations (local filesystem, S3, Cloudflare R2, etc.) without being coupled to a specific storage implementation.

## Architecture

### Design Principles

1. **Abstraction**: Clean interface that all storage backends must implement
2. **Multi-tenant**: Sources are scoped to both organizations and projects
3. **Extensibility**: New storage backends can be added without modifying existing code
4. **Validation**: Configuration is validated at both the interface and Django model level
5. **Registry Pattern**: Source implementations are registered and retrieved by type identifier

### Component Overview

```
sources/
├── __init__.py          # Package exports
├── base.py              # SourceInterface abstract base class
├── registry.py          # SourceRegistry for managing implementations
├── local.py             # LocalFileSystemSource implementation
├── models.py            # Django Source model
├── admin.py             # Django admin interface
└── apps.py              # Django app configuration
```

## Core Interfaces

### SourceInterface

Abstract base class that all source implementations must inherit from.

**Required Methods:**

- `validate_config() -> None`: Validate source-specific configuration
- `list_documents() -> Iterator[DocumentMetadata]`: List all available documents
- `read_document(path: str) -> bytes`: Read document content
- `get_display_name() -> str`: Human-readable source description
- `test_connection() -> bool`: Test if source is accessible

**Configuration:**

Each source type accepts a `config` dictionary with source-specific fields. Configuration is validated in `__init__()` via `validate_config()`.

### DocumentMetadata

Dataclass for consistent document metadata across different source types.

**Fields:**

- `path` (str): Unique identifier within the source (required)
- `name` (str): Display name for the document (required)
- `size` (int, optional): Size in bytes
- `modified_at` (datetime, optional): Last modification time
- `content_type` (str, optional): MIME type
- `extension` (str, optional): File extension

## Django Model

### Source Model

Django model for storing source configurations in the database.

**Fields:**

- `organization` (FK): Organization that owns this source (multi-tenant)
- `project` (FK): Project this source belongs to
- `source_type` (str): Type identifier (e.g., 'local', 's3', 'r2')
- `name` (str): Display name
- `description` (str): Optional description
- `config` (JSON): Source-specific configuration
- `is_active` (bool): Whether source is actively used
- `last_sync_at` (datetime): Last sync timestamp
- `last_test_at` (datetime): Last connection test timestamp
- `last_test_success` (bool): Result of last connection test

**Methods:**

- `get_source_instance() -> SourceInterface`: Get configured source implementation
- `test_connection() -> bool`: Test connection and update status
- `get_display_name() -> str`: Get display name from implementation

**Validation:**

- Organization must match project's organization
- Source type must be registered
- Configuration must be valid for the source type

## Implemented Sources

### LocalFileSystemSource

Reads documents from a local directory using glob patterns.

**Configuration Schema:**

```python
{
    "path": "/absolute/path/to/documents",  # Required
    "pattern": "**/*.{md,pdf,png,jpg}",     # Optional, default: **/*
    "recursive": True,                       # Optional, default: True
    "follow_symlinks": False                 # Optional, default: False
}
```

**Supported File Types:**

- Images: .png, .jpg, .jpeg, .gif, .bmp, .webp, .svg
- PDFs: .pdf
- Text: .md, .markdown, .txt, .csv, .json, .yaml, .yml
- Diagrams: .d2

**Example:**

```python
from sources.models import Source

source = Source.objects.create(
    project=project,
    source_type='local',
    name='Project Documents',
    config={
        'path': '/Users/brian/projects/demo-docs',
        'pattern': '**/*.{md,pdf,png}',
        'recursive': True
    }
)

# Get source instance and list documents
source_impl = source.get_source_instance()
for doc_meta in source_impl.list_documents():
    content = source_impl.read_document(doc_meta.path)
    print(f"Read {doc_meta.name}: {len(content)} bytes")
```

## Future Source Types

### AWS S3 Source

**Planned Configuration:**

```python
{
    "bucket": "my-documents",
    "prefix": "project-files/",
    "region": "us-west-2",
    "access_key_id": "...",     # Optional, can use IAM roles
    "secret_access_key": "..."  # Optional, can use IAM roles
}
```

### Cloudflare R2 Source

**Planned Configuration:**

```python
{
    "bucket": "zoea-docs",
    "account_id": "...",
    "access_key_id": "...",
    "secret_access_key": "..."
}
```

## Registry Pattern

The `SourceRegistry` class maintains a mapping of source type identifiers to implementation classes.

**Usage:**

```python
from sources.registry import SourceRegistry
from sources.base import SourceInterface

# Register a new source type
class MySource(SourceInterface):
    # Implementation...
    pass

SourceRegistry.register('my-source', MySource)

# Retrieve and instantiate
source_class = SourceRegistry.get('my-source')
source = source_class({'config': 'values'})
```

**Automatic Registration:**

Source implementations can register themselves when imported:

```python
# At the end of source implementation file
SourceRegistry.register('local', LocalFileSystemSource)
```

## Migration Strategy

### Converting from working_directory

The migration from `Project.working_directory` to the Source model is handled automatically:

1. **Migration 0001**: Creates the Source model
2. **Migration 0002**: Data migration that:
   - Iterates through all projects
   - Creates a local filesystem source for each project with `working_directory`
   - Preserves the original path in the source config

**Example migration result:**

```python
# Before
project = Project(
    name="My Project",
    working_directory="/Users/brian/projects/demo-docs"
)

# After migration
project.sources.all()
# [<Source: Default Documents (local, active)>]

source = project.sources.first()
source.config
# {'path': '/Users/brian/projects/demo-docs',
#  'pattern': '**/*.{md,pdf,png,jpg,jpeg,gif,csv,txt,d2}',
#  'recursive': True,
#  'follow_symlinks': False}
```

### Deprecation Path

The `working_directory` field will eventually be deprecated:

1. ✅ Phase 1: Add Source model alongside `working_directory` (current)
2. Phase 2: Update all code to use Sources instead of `working_directory`
3. Phase 3: Make `working_directory` nullable
4. Phase 4: Remove `working_directory` field entirely

## Admin Interface

The Django admin provides comprehensive source management:

**Features:**

- List view with filtering by type, organization, active status
- Connection status indicators (green: connected, red: failed, gray: not tested)
- Test connection action for selected sources
- Activate/deactivate actions
- Organization-scoped filtering (users only see their org's sources)
- JSON config editing with syntax highlighting

**Access Control:**

- Superusers can see all sources
- Regular users only see sources from their organizations
- Organization is auto-populated from project

## Testing

Comprehensive test suite with 45 tests covering:

### LocalFileSystemSource Tests (34 tests)
- Configuration validation
- Document listing with various filters
- Recursive traversal
- Pattern matching
- Metadata population
- Document reading
- Connection testing
- Symlink handling

### Registry Tests (11 tests)
- Source registration
- Duplicate prevention
- Type retrieval
- Unregistration

### Model Tests (14 tests)
- CRUD operations
- Validation
- Organization scoping
- User filtering
- Connection testing
- Instance creation

**Running Tests:**

```bash
# Run all source tests
uv run pytest sources/tests/ -v

# Run specific test file
uv run pytest sources/tests/test_local_source.py -v

# Run with coverage
uv run pytest sources/tests/ --cov=sources --cov-report=html
```

## Usage Examples

### Creating a Source

```python
from sources.models import Source

source = Source.objects.create(
    project=project,
    source_type='local',
    name='Documentation',
    description='Project documentation files',
    config={
        'path': '/Users/brian/projects/docs',
        'pattern': '**/*.md'
    }
)
```

### Listing Documents from a Source

```python
source = Source.objects.get(name='Documentation')
source_impl = source.get_source_instance()

for doc_meta in source_impl.list_documents():
    print(f"Found: {doc_meta.name}")
    print(f"  Path: {doc_meta.path}")
    print(f"  Size: {doc_meta.size} bytes")
    print(f"  Type: {doc_meta.content_type}")
```

### Testing Connection

```python
source = Source.objects.get(name='Documentation')

if source.test_connection():
    print("✓ Connection successful")
    print(f"  Last tested: {source.last_test_at}")
else:
    print("✗ Connection failed")
```

### Filtering Sources

```python
# Get all sources for a project
project_sources = Source.objects.for_project(project)

# Get only active sources
active_sources = Source.objects.active()

# Get sources for a user
user_sources = Source.objects.for_user(user)

# Combine filters
project_active_sources = Source.objects.for_project(project).active()
```

## Security Considerations

### Configuration Security

⚠️ **Important**: Source configurations may contain sensitive credentials (API keys, access tokens, etc.).

**Current Implementation:**
- Stored as plain JSON in the database
- Accessible via Django admin (organization-scoped)

**Future Enhancements:**
- Encrypt sensitive fields using Django's encrypted fields
- Support environment variables for credentials
- Integrate with secret management systems (AWS Secrets Manager, etc.)

**Best Practices:**
- Limit who has admin access
- Use IAM roles instead of explicit credentials when possible
- Rotate credentials regularly
- Never commit credentials to version control

### Path Traversal Prevention

LocalFileSystemSource validates that:
- Paths are absolute (not relative)
- Paths exist and are directories
- Only files within the configured path are accessible

## Performance Considerations

### Document Listing

- Sources should implement efficient iteration (yield, not return full list)
- Large directories may take time to enumerate
- Consider implementing pagination for cloud sources

### Caching

- Document metadata could be cached to reduce API calls
- Connection test results are cached in the model
- Consider implementing a TTL-based cache for expensive operations

### Batch Operations

When syncing many documents:
- Process in batches to avoid memory issues
- Use database bulk operations when creating Document records
- Implement progress tracking for long-running syncs

## Related Documentation

- [Multi-Tenant Architecture](django-organizations-guide.md)
- [Document Models](../documents/models.md)
- [Gemini File Search Integration](../documents/gemini-service.md)

## API Reference

For complete API documentation, see the inline docstrings in:
- `sources/base.py`: SourceInterface and DocumentMetadata
- `sources/registry.py`: SourceRegistry
- `sources/local.py`: LocalFileSystemSource
- `sources/models.py`: Source model
