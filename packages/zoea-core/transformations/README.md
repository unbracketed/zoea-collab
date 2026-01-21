# Content Transformation System

A flexible, extensible system for transforming content between different types and formats using a factory-based registry pattern with MRO-aware lookup.

## Table of Contents

- [Quick Start](#quick-start)
- [Core Concepts](#core-concepts)
- [Usage Examples](#usage-examples)
- [Adding New Transformers](#adding-new-transformers)
- [Advanced Topics](#advanced-topics)
- [API Reference](#api-reference)

## Quick Start

### Basic Transformation (No Extra Arguments Needed)

```python
from transformations import transform, OutputFormat
from documents.models import Markdown

# Transform a Markdown document to an outline structure
markdown_doc = Markdown.objects.get(id=1)
outline = transform(markdown_doc, OutputFormat.OUTLINE)

# Result is a hierarchical tree structure
print(outline["sections"])

# Transform a conversation to markdown text
from chat.models import Conversation

conversation = Conversation.objects.get(id=5)
markdown_text = transform(conversation, OutputFormat.MARKDOWN)
print(markdown_text)
```

**That's it!** Most transformations work with just the source object and output format.

### Advanced: Passing Optional Context

For advanced scenarios, you can pass additional context via keyword arguments:

```python
from transformations import transform, OutputFormat

# Optional context for special cases
result = transform(
    source_obj,
    OutputFormat.MARKDOWN,
    # Optional context arguments below:
    custom_style="dark",           # Custom formatting options
    include_metadata=True,         # Feature flags
    export_for_org=other_org       # Cross-tenant operations
)
```

**Note:** The source objects (Markdown, Conversation, etc.) already contain their organization, user, and other metadata as Django model fields. You typically don't need to pass this information again.

## Core Concepts

### 1. Factory-Based Registration

Transformers are registered as **factories** (not singletons), allowing:
- Fresh instances per transformation call
- Dependency injection via closures or constructor parameters
- Stateless transformations by default

```python
@register_transformer(MyModel, OutputFormat.JSON)
class MyTransformer(BaseTransformer):
    def transform(self, source, **context):
        return {"data": source.value}
```

### 2. MRO-Aware Lookup

Transformers registered for parent classes automatically work for subclasses:

```python
# Register for parent class
@register_transformer(TextDocument, OutputFormat.JSON)
class TextToJSONTransformer(BaseTransformer):
    def transform(self, source, **context):
        return {"content": source.content}

# Works for all subclasses
markdown = Markdown.objects.first()  # Markdown inherits from TextDocument
result = transform(markdown, OutputFormat.JSON)  # Uses TextToJSONTransformer
```

Child classes can override parent transformers for more specific behavior.

### 3. Type-Safe Output Formats

Use the `OutputFormat` enum to prevent typos and ensure type safety:

```python
from transformations import OutputFormat

# Available formats
OutputFormat.MARKDOWN       # Markdown text
OutputFormat.JSON          # JSON-serializable dict
OutputFormat.OUTLINE       # Hierarchical tree structure
OutputFormat.REACTFLOW     # React Flow diagram data
OutputFormat.D2            # D2 diagram markup
OutputFormat.SYSTEM_MESSAGE # AI system prompt
OutputFormat.USER_PROMPT   # User-facing prompt
```

### 4. Value Objects for Chaining

Use lightweight value objects instead of unsaved Django models for chained transformations:

```python
from transformations import MarkdownPayload, OutputFormat, transform

# Conversation → Markdown text
markdown_text = transform(conversation, OutputFormat.MARKDOWN)

# Create payload from markdown text (no database)
payload = MarkdownPayload(content=markdown_text)

# Markdown → Outline
outline = transform(payload, OutputFormat.OUTLINE)
```

## Usage Examples

### Example 1: Basic Document Export

```python
from transformations import transform, OutputFormat
from documents.models import Markdown

# Get document and transform - no extra arguments needed
markdown_doc = Markdown.objects.get(id=1)
json_output = transform(markdown_doc, OutputFormat.JSON)

print(json_output)
# {
#     "id": 1,
#     "title": "My Document",
#     "content": "# Heading\n\nContent...",
#     "created_at": "2025-11-16T10:30:00",
#     ...
# }
```

### Example 2: Conversation Export

```python
from transformations import transform, OutputFormat
from chat.models import Conversation

# Simple - just source and format
conversation = Conversation.objects.get(id=1)
markdown_text = transform(conversation, OutputFormat.MARKDOWN)

# Returns formatted markdown text
# # What is the weather like?
# **Agent:** TestAgent
# **Created by:** alice
# ...
```

### Example 3: Optional Context Arguments

For transformers that need additional configuration, pass optional context:

```python
from transformations import transform, OutputFormat

# Pass optional context for customization
result = transform(
    markdown_doc,
    OutputFormat.MARKDOWN,
    # These are all optional:
    include_metadata=True,         # Custom option
    export_format="github_flavored"  # Format preference
)
```

**When to use context:**
- Custom formatting options not stored in the model
- Cross-organization exports (exporting for a different org than the source)
- Feature flags that change transformation behavior
- Injecting external services for transformations that need them

### Example 4: Chained Transformations

```python
from transformations import transform, OutputFormat, MarkdownPayload

# Step 1: Conversation → Markdown
markdown_text = transform(conversation, OutputFormat.MARKDOWN)

# Step 2: Create lightweight payload (no DB instance)
payload = MarkdownPayload(content=markdown_text)

# Step 3: Markdown → Outline
outline = transform(payload, OutputFormat.OUTLINE)

# Inspect the hierarchical structure
for section in outline["sections"]:
    print(f"{section['level']}: {section['title']}")
    for child in section['children']:
        print(f"  {child['level']}: {child['title']}")
```

### Example 5: Checking Available Formats

```python
from transformations import get_available_formats, has_transformer
from documents.models import Markdown

# Check what formats are available for a type
formats = get_available_formats(Markdown)
print(formats)  # [OutputFormat.OUTLINE, OutputFormat.JSON, OutputFormat.MARKDOWN]

# Check if a specific transformation exists
if has_transformer(Markdown, OutputFormat.OUTLINE):
    outline = transform(markdown_doc, OutputFormat.OUTLINE)
```

## Adding New Transformers

### Method 1: Simple Class Registration

For transformers without dependencies:

```python
from transformations.base import BaseTransformer, StructuredDataTransformer
from transformations.enums import OutputFormat
from transformations.registry import register_transformer
from myapp.models import CustomModel

@register_transformer(CustomModel, OutputFormat.JSON)
class CustomToJSONTransformer(StructuredDataTransformer):
    """Convert CustomModel to JSON-serializable dict."""

    def transform(self, source: CustomModel, **context) -> dict:
        return {
            "id": source.id,
            "name": source.name,
            "data": source.data_field,
            "created_at": source.created_at.isoformat(),
        }
```

### Method 2: Factory with Dependency Injection

For transformers that need external services:

```python
from transformations import register_transformer, OutputFormat
from transformations.base import BaseTransformer

# Define the transformer class
class DiagramTransformer(BaseTransformer):
    def __init__(self, graphologue_service):
        self.service = graphologue_service

    def transform(self, source, **context):
        # Use the injected service
        diagram_data = self.service.convert(source.content)
        return diagram_data

# Create a factory function
def make_diagram_transformer():
    from chat.graphologue_service import GraphologueService
    from django.conf import settings

    service = GraphologueService(api_key=settings.OPENAI_API_KEY)
    return DiagramTransformer(service)

# Register using the factory
@register_transformer(
    Conversation,
    OutputFormat.REACTFLOW,
    factory=make_diagram_transformer
)
class _RegisteredDiagramTransformer:
    """Placeholder for registration (factory creates actual instance)."""
    pass
```

### Method 3: Inheriting from Specialized Base Classes

Use type-specific base classes for better organization:

```python
from transformations.base import (
    TextTransformer,           # For text output (str)
    StructuredDataTransformer, # For dict/JSON output
    DiagramTransformer,        # For diagram data structures
)

@register_transformer(MyModel, OutputFormat.MARKDOWN)
class MyToMarkdownTransformer(TextTransformer):
    """Produces markdown text output."""

    def transform(self, source, **context) -> str:
        return f"# {source.title}\n\n{source.content}"

@register_transformer(MyModel, OutputFormat.JSON)
class MyToJSONTransformer(StructuredDataTransformer):
    """Produces JSON-serializable dict output."""

    def transform(self, source, **context) -> dict:
        return {"title": source.title, "content": source.content}
```

### Method 4: Supporting Multiple Source Types

Register the same transformer for multiple types:

```python
@register_transformer(Markdown, OutputFormat.JSON)
@register_transformer(CSV, OutputFormat.JSON)
@register_transformer(Diagram, OutputFormat.JSON)
class TextDocumentToJSONTransformer(StructuredDataTransformer):
    """Works for all TextDocument subclasses."""

    def transform(self, source, **context) -> dict:
        return {
            "name": source.name,
            "content": source.content,
            "type": source.__class__.__name__,
        }
```

## Advanced Topics

### Understanding Context Arguments

**Most of the time, you don't need context arguments.** Django model instances already have everything they need:

```python
# The source object already has organization, user, etc.
markdown_doc = Markdown.objects.get(id=1)
print(markdown_doc.organization)  # ✅ Already available
print(markdown_doc.created_by)    # ✅ Already available
print(markdown_doc.project)       # ✅ Already available

# So transformers can just access these directly
@register_transformer(Markdown, OutputFormat.OUTLINE)
class OutlineTransformer(StructuredDataTransformer):
    def transform(self, source, **context):
        # Access the organization from the source object
        if source.organization.feature_enabled('enhanced'):
            # Custom logic
            pass
        return {"sections": parse_sections(source.content)}
```

**Use context only for:**

1. **Custom transformation options:**
   ```python
   # Options not stored in the model
   transform(doc, OutputFormat.MARKDOWN, include_toc=True, max_depth=3)
   ```

2. **Value objects without organization:**
   ```python
   # MarkdownPayload doesn't have an organization field
   payload = MarkdownPayload(content="# Test")
   transform(payload, OutputFormat.OUTLINE, organization=org)
   ```

3. **Cross-tenant operations:**
   ```python
   # Export using a different org's formatting
   transform(doc, OutputFormat.MARKDOWN, export_for_org=other_org)
   ```

4. **Injecting external services:**
   ```python
   # Service not accessible from the model
   transform(conv, OutputFormat.REACTFLOW, services={'diagram': svc})
   ```

### Performance Considerations

The registry uses caching for O(1) lookup performance:

1. **First lookup**: O(N) where N is MRO depth (typically 2-5 classes)
2. **Subsequent lookups**: O(1) from cache
3. **Factory instantiation**: Per-call (enables dependency injection)

For high-volume transformations, the factory overhead is minimal compared to the actual transformation logic.

### Testing Transformers

Use the test utilities:

```python
import pytest
from transformations import transform, OutputFormat, clear_registry

@pytest.fixture(autouse=True)
def clean_registry():
    """Ensure clean registry for each test."""
    clear_registry()
    yield
    clear_registry()

def test_my_transformer():
    """Test custom transformer."""
    from myapp.transformers import MyTransformer  # Triggers registration

    obj = MyModel.objects.create(name="Test")
    result = transform(obj, OutputFormat.JSON)

    assert result["name"] == "Test"
```

### Error Handling

The system provides helpful error messages:

```python
# If transformer doesn't exist
transform(my_obj, OutputFormat.UNKNOWN)
# ValueError: No transformer registered for MyModel -> unknown
# Available formats for MyModel: json, markdown, outline
# Check that a transformer is registered using @register_transformer(MyModel, OutputFormat.UNKNOWN)

# If format is not an enum
transform(my_obj, "json")  # String instead of enum
# TypeError: output_format must be an OutputFormat enum value, got str: json
```

## API Reference

### Main Functions

#### `transform(source, output_format, **context)`

Transform a source object to the specified format.

**Parameters:**
- `source`: The object to transform (e.g., Markdown, Conversation)
- `output_format`: Target format (OutputFormat enum value)
- `**context`: **Optional** keyword arguments for advanced use cases
  - Not needed for most transformations
  - Source objects already contain organization, user, etc. as model fields
  - Use only when you need to pass custom options, feature flags, or external services

**Returns:** Transformed object (type depends on output format)

**Raises:**
- `ValueError`: No transformer registered for the source type and format
- `TypeError`: Invalid output_format type (must be OutputFormat enum)

**Examples:**

```python
# Basic usage (no context needed)
outline = transform(markdown_doc, OutputFormat.OUTLINE)

# With optional context
result = transform(
    doc,
    OutputFormat.MARKDOWN,
    include_toc=True,  # Custom option
    max_depth=3        # Custom option
)
```

#### `register_transformer(source_type, output_format, *, factory=None)`

Decorator to register a transformer.

**Parameters:**
- `source_type`: Type of object to transform
- `output_format`: Target format (OutputFormat enum)
- `factory`: Optional factory callable (defaults to decorated class)

**Returns:** Decorator function

#### `has_transformer(source_type, output_format)`

Check if a transformer is registered.

**Parameters:**
- `source_type`: Type to check
- `output_format`: Format to check

**Returns:** `bool`

#### `get_available_formats(source_type)`

Get all registered output formats for a type.

**Parameters:**
- `source_type`: Type to query

**Returns:** `list[OutputFormat]`

#### `clear_registry()`

Clear all registered transformers (primarily for testing).

### Base Classes

#### `BaseTransformer[TSource, TTarget]`

Abstract base class for all transformers.

```python
class BaseTransformer(ABC, Generic[TSource, TTarget]):
    @abstractmethod
    def transform(self, source: TSource, **context: Any) -> TTarget:
        pass
```

#### `TextTransformer[TSource]`

Base class for transformers that produce text output.

```python
class TextTransformer(BaseTransformer[TSource, str]):
    pass
```

#### `StructuredDataTransformer[TSource]`

Base class for transformers that produce structured data (dicts).

```python
class StructuredDataTransformer(BaseTransformer[TSource, dict]):
    pass
```

#### `DiagramTransformer[TSource]`

Base class for transformers that produce diagram data structures.

```python
class DiagramTransformer(BaseTransformer[TSource, dict]):
    pass
```

### Value Objects

#### `MarkdownPayload`

Lightweight container for markdown content (for chaining).

```python
@dataclass(frozen=True)
class MarkdownPayload:
    content: str
    title: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)
```

#### `TextPayload`

Generic text content payload.

```python
@dataclass(frozen=True)
class TextPayload:
    content: str
    format: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)
```

#### `ConversationPayload`

Lightweight container for conversation data.

```python
@dataclass(frozen=True)
class ConversationPayload:
    messages: list[tuple[str, str, Optional[datetime]]]
    title: Optional[str] = None
    agent_name: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)
```

#### `DiagramPayload`

Lightweight container for diagram data.

```python
@dataclass(frozen=True)
class DiagramPayload:
    nodes: list[dict[str, Any]]
    edges: list[dict[str, Any]]
    layout: Optional[dict[str, Any]] = None
    metadata: dict[str, Any] = field(default_factory=dict)
```

## Best Practices

1. **Use value objects for chaining** - Avoid creating unsaved Django model instances
2. **Keep transformers stateless** - Use factory pattern for dependencies
3. **Document transformer behavior** - Include docstrings with examples
4. **Test transformers independently** - Use `clear_registry()` fixture
5. **Handle tenant context** - Pass organization in `**context` for multi-tenant apps
6. **Use type-specific base classes** - `TextTransformer`, `StructuredDataTransformer`, etc.
7. **Provide helpful error messages** - Validate inputs and raise clear exceptions
8. **Register along class hierarchies** - Parent class transformers work for subclasses

## Migration from Legacy Functions

If you still have helper functions like `markdown_to_outline(markdown_doc)` or
`conversation_to_markdown(conversation)` lingering in the codebase, move their logic into
a transformer class and delete the helper:

```python
# Legacy helper (remove this once transformer exists)
def markdown_to_outline(markdown: Markdown) -> dict:
    ...

# Replacement transformer (kept in backend/transformations/transformers/)
@register_transformer(Markdown, OutputFormat.OUTLINE)
class MarkdownToOutlineTransformer(StructuredDataTransformer):
    def transform(self, source: Markdown, **context) -> dict:
        ...

# Call sites should always go through the registry API:
outline = transform(markdown_doc, OutputFormat.OUTLINE)
```

All built-in helpers in `backend/transformations/mappings.py` have been removed—new formats must
use the registry so we keep a single codepath for conversions.

## License

This transformation system is part of the Zoea Studio project.
