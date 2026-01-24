# Transformation System Examples

This document provides complete, working examples of adding new transformers to the system.

## Table of Contents

1. [Simple Transformers](#simple-transformers)
2. [Transformers with Dependencies](#transformers-with-dependencies)
3. [Multi-Source Transformers](#multi-source-transformers)
4. [Chained Transformations](#chained-transformations)
5. [Real-World Scenarios](#real-world-scenarios)

---

## Simple Transformers

### Example 1: PDF to Plain Text

Extract text content from PDF documents.

**File:** `backend/transformations/transformers/document.py`

```python
"""Transformers for Document types (PDF, Image, etc.)."""

from typing import Any

from documents.models import PDF
from transformations.base import TextTransformer
from transformations.enums import OutputFormat
from transformations.registry import register_transformer


@register_transformer(PDF, OutputFormat.MARKDOWN)
class PDFToMarkdownTransformer(TextTransformer):
    """Convert PDF to Markdown text format.

    Extracts text content and formats as markdown with basic structure.
    """

    def transform(self, source: PDF, **context: Any) -> str:
        """Transform PDF to Markdown text.

        Args:
            source: PDF model instance
            **context: Unused for this transformation

        Returns:
            Markdown-formatted text representation
        """
        lines = []

        # Add document title as heading
        lines.append(f"# {source.name}\n")

        # Add metadata
        if source.description:
            lines.append(f"**Description:** {source.description}  \n")

        lines.append(f"**File Size:** {source.file_size} bytes  \n")
        lines.append(f"**Created:** {source.created_at.strftime('%Y-%m-%d')}\n")
        lines.append("---\n")

        # In a real implementation, you'd extract PDF text here
        # For now, placeholder
        lines.append("*PDF text content would appear here*\n")

        return "\n".join(lines)
```

**Usage:**

```python
from transformations import transform, OutputFormat
from documents.models import PDF

pdf_doc = PDF.objects.get(id=1)
markdown_text = transform(pdf_doc, OutputFormat.MARKDOWN)
print(markdown_text)
```

---

### Example 2: Image to JSON Metadata

Export image metadata as JSON.

**File:** `backend/transformations/transformers/document.py`

```python
from documents.models import Image


@register_transformer(Image, OutputFormat.JSON)
class ImageToJSONTransformer(StructuredDataTransformer):
    """Convert Image to JSON-serializable metadata dict."""

    def transform(self, source: Image, **context: Any) -> dict:
        """Transform Image to JSON metadata.

        Args:
            source: Image model instance
            **context: Unused for this transformation

        Returns:
            dict with image metadata
        """
        return {
            "id": source.id,
            "name": source.name,
            "description": source.description,
            "file_path": source.image_file.url if source.image_file else None,
            "width": source.width,
            "height": source.height,
            "file_size": source.file_size,
            "format": source.image_file.name.split('.')[-1] if source.image_file else None,
            "created_at": source.created_at.isoformat(),
            "created_by": source.created_by.username if source.created_by else None,
        }
```

---

## Transformers with Dependencies

### Example 3: Conversation to D2 Diagram (with Service Injection)

Generate D2 diagram markup from conversations using an external service.

**File:** `backend/transformations/transformers/conversation.py`

```python
from typing import Any

from chat.models import Conversation
from transformations.base import TextTransformer
from transformations.enums import OutputFormat
from transformations.registry import register_transformer


class ConversationToD2Transformer(TextTransformer):
    """Convert Conversation to D2 diagram markup.

    Requires a diagram generation service injected via factory.
    """

    def __init__(self, diagram_service):
        self.diagram_service = diagram_service

    def transform(self, source: Conversation, **context: Any) -> str:
        """Transform Conversation to D2 markup.

        Args:
            source: Conversation model instance
            **context: Optional context keys:
                - style: Diagram style preference

        Returns:
            D2 diagram markup string
        """
        # Build conversation text
        messages = []
        for msg in source.messages.all():
            messages.append({
                "role": msg.role,
                "content": msg.content,
            })

        # Use service to generate diagram
        style = context.get('style', 'default')
        d2_markup = self.diagram_service.generate_d2(
            messages=messages,
            title=source.get_title(),
            style=style
        )

        return d2_markup


# Factory function for dependency injection
def make_d2_transformer():
    """Factory to create D2 transformer with injected service."""
    from chat.services import DiagramService
    from django.conf import settings

    service = DiagramService(api_key=settings.DIAGRAM_API_KEY)
    return ConversationToD2Transformer(service)


# Register using the factory
@register_transformer(
    Conversation,
    OutputFormat.D2,
    factory=make_d2_transformer
)
class _ConversationD2Registration:
    """Registration placeholder (factory creates actual instance)."""
    pass
```

**Usage:**

```python
from transformations import transform, OutputFormat

conversation = Conversation.objects.get(id=1)

# With custom style
d2_diagram = transform(
    conversation,
    OutputFormat.D2,
    style='sketch'  # Passed to transformer
)

print(d2_diagram)
# direction: right
# conversation: Conversation Title {
#   user: User says... {
#     shape: rectangle
#   }
#   assistant: Assistant replies... {
#     shape: rectangle
#   }
# }
```

---

### Example 4: Context-Aware Markdown Export

Export markdown with tenant-specific formatting.

**File:** `backend/transformations/transformers/markdown.py`

```python
from documents.models import Markdown


@register_transformer(Markdown, OutputFormat.MARKDOWN)
class EnhancedMarkdownTransformer(TextTransformer):
    """Export markdown with organization-specific enhancements."""

    def transform(self, source: Markdown, **context: Any) -> str:
        """Transform with org-specific formatting.

        Args:
            source: Markdown model instance
            **context: Expected keys:
                - organization: For tenant-specific formatting
                - include_metadata: Whether to add metadata header

        Returns:
            Enhanced markdown text
        """
        lines = []
        org = context.get('organization')
        include_metadata = context.get('include_metadata', True)

        # Add organization branding if configured
        if org and hasattr(org, 'branding_enabled') and org.branding_enabled:
            lines.append(f"<!-- Organization: {org.name} -->\n")

        # Add metadata header
        if include_metadata:
            lines.append("---")
            lines.append(f"title: {source.name}")
            lines.append(f"created: {source.created_at.isoformat()}")
            if source.created_by:
                lines.append(f"author: {source.created_by.username}")
            lines.append("---\n")

        # Add content
        lines.append(source.content)

        return "\n".join(lines)
```

**Usage:**

```python
markdown_doc = Markdown.objects.get(id=1)

# With organization context
result = transform(
    markdown_doc,
    OutputFormat.MARKDOWN,
    organization=request.user.organization,
    include_metadata=True
)
```

---

## Multi-Source Transformers

### Example 5: Generic Document to JSON

Single transformer that works for all Document types.

**File:** `backend/transformations/transformers/document.py`

```python
from documents.models import Document, Image, PDF, Markdown, CSV


@register_transformer(Document, OutputFormat.JSON)
@register_transformer(Image, OutputFormat.JSON)
@register_transformer(PDF, OutputFormat.JSON)
@register_transformer(Markdown, OutputFormat.JSON)
@register_transformer(CSV, OutputFormat.JSON)
class GenericDocumentToJSONTransformer(StructuredDataTransformer):
    """Convert any Document type to JSON.

    Registered for all document types to ensure consistent JSON export.
    """

    def transform(self, source: Document, **context: Any) -> dict:
        """Transform any Document to JSON.

        Args:
            source: Any Document subclass instance
            **context: Unused for this transformation

        Returns:
            dict with common document fields
        """
        result = {
            "id": source.id,
            "type": source.__class__.__name__,
            "name": source.name,
            "description": source.description,
            "file_size": source.file_size,
            "created_at": source.created_at.isoformat(),
            "updated_at": source.updated_at.isoformat(),
        }

        # Add type-specific fields
        if isinstance(source, Image):
            result["width"] = source.width
            result["height"] = source.height
            result["image_url"] = source.image_file.url if source.image_file else None

        elif isinstance(source, Markdown):
            result["content"] = source.content
            result["word_count"] = len(source.content.split())

        elif isinstance(source, CSV):
            result["has_header"] = source.has_header
            result["delimiter"] = source.delimiter

        return result
```

---

## Chained Transformations

### Example 6: Conversation → Markdown → Outline Pipeline

Multi-step transformation pipeline.

**Implementation:**

```python
from transformations import transform, OutputFormat, MarkdownPayload

def analyze_conversation(conversation_id: int) -> dict:
    """Analyze conversation structure via chained transformations.

    Pipeline: Conversation → Markdown → Outline
    """
    from chat.models import Conversation

    # Step 1: Fetch conversation
    conversation = Conversation.objects.prefetch_related('messages').get(
        id=conversation_id
    )

    # Step 2: Convert to Markdown
    markdown_text = transform(conversation, OutputFormat.MARKDOWN)

    # Step 3: Create lightweight payload (no DB write)
    payload = MarkdownPayload(
        content=markdown_text,
        title=conversation.get_title(),
        metadata={"conversation_id": conversation.id}
    )

    # Step 4: Generate outline from markdown
    outline = transform(payload, OutputFormat.OUTLINE)

    # Return analysis results
    return {
        "conversation_id": conversation.id,
        "title": conversation.get_title(),
        "message_count": conversation.message_count(),
        "structure": outline,
        "sections": len(outline["sections"]),
    }
```

**Usage:**

```python
analysis = analyze_conversation(conversation_id=1)
print(f"Conversation has {analysis['sections']} main sections")
```

---

### Example 7: Document Collection to Archive

Transform multiple documents and package them.

```python
from transformations import transform, OutputFormat
from documents.models import Markdown
import json
import zipfile
from io import BytesIO


def export_document_collection(folder_id: int) -> bytes:
    """Export all documents in a folder as a zip archive.

    Each document is transformed to JSON and markdown.
    """
    from documents.models import Folder

    folder = Folder.objects.get(id=folder_id)
    documents = folder.documents.all()

    # Create zip file in memory
    zip_buffer = BytesIO()

    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        for doc in documents:
            # Export as JSON
            json_data = transform(doc, OutputFormat.JSON)
            zip_file.writestr(
                f"{doc.name}_{doc.id}.json",
                json.dumps(json_data, indent=2)
            )

            # Export markdown documents as .md files
            if isinstance(doc, Markdown):
                md_text = transform(doc, OutputFormat.MARKDOWN)
                zip_file.writestr(
                    f"{doc.name}_{doc.id}.md",
                    md_text
                )

    zip_buffer.seek(0)
    return zip_buffer.getvalue()
```

---

## Real-World Scenarios

### Example 8: API Endpoint with Transformations

Django Ninja endpoint using transformations.

**File:** `backend/documents/api.py`

```python
from ninja import Router
from django.http import HttpResponse
from transformations import transform, OutputFormat, get_available_formats
from documents.models import Document

router = Router()


@router.get("/documents/{document_id}/export/{format}")
def export_document(request, document_id: int, format: str):
    """Export document in specified format.

    Supports: json, markdown, outline
    """
    from transformations import OutputFormat

    # Map string to enum
    format_map = {
        "json": OutputFormat.JSON,
        "markdown": OutputFormat.MARKDOWN,
        "outline": OutputFormat.OUTLINE,
    }

    if format not in format_map:
        return {"error": f"Unsupported format: {format}"}, 400

    output_format = format_map[format]

    # Fetch document with organization check
    doc = Document.objects.for_organization(
        request.user.organization
    ).get(id=document_id)

    # Transform with user context
    result = transform(
        doc,
        output_format,
        organization=request.user.organization,
        user=request.user
    )

    # Return appropriate response
    if format == "json":
        return result

    elif format == "markdown":
        return HttpResponse(
            result,
            content_type="text/markdown",
            headers={
                "Content-Disposition": f'attachment; filename="{doc.name}.md"'
            }
        )

    else:  # outline
        return result


@router.get("/documents/{document_id}/formats")
def available_formats(request, document_id: int):
    """Get available export formats for a document."""
    doc = Document.objects.get(id=document_id)

    formats = get_available_formats(type(doc))

    return {
        "document_id": document_id,
        "document_type": doc.__class__.__name__,
        "available_formats": [fmt.value for fmt in formats]
    }
```

---

### Example 9: Background Task with Transformations

Celery task for bulk export.

**File:** `backend/documents/tasks.py`

```python
from celery import shared_task
from transformations import transform, OutputFormat
from documents.models import Folder
import json


@shared_task
def export_folder_to_json(folder_id: int, user_id: int):
    """Export all documents in a folder to JSON files.

    Args:
        folder_id: Folder to export
        user_id: User performing export (for context)
    """
    from documents.models import Folder
    from django.contrib.auth import get_user_model
    import boto3

    User = get_user_model()

    folder = Folder.objects.get(id=folder_id)
    user = User.objects.get(id=user_id)
    documents = folder.documents.all()

    s3 = boto3.client('s3')
    bucket = 'document-exports'

    exported = []

    for doc in documents:
        # Transform to JSON
        json_data = transform(
            doc,
            OutputFormat.JSON,
            organization=folder.organization,
            user=user
        )

        # Upload to S3
        key = f"exports/{folder.organization.id}/{folder.id}/{doc.id}.json"

        s3.put_object(
            Bucket=bucket,
            Key=key,
            Body=json.dumps(json_data, indent=2),
            ContentType='application/json'
        )

        exported.append({
            "document_id": doc.id,
            "document_name": doc.name,
            "s3_key": key
        })

    return {
        "folder_id": folder_id,
        "exported_count": len(exported),
        "documents": exported
    }
```

---

### Example 10: Testing Custom Transformers

Complete test example.

**File:** `backend/transformations/tests/test_custom_transformers.py`

```python
import pytest
from django.contrib.auth import get_user_model

from accounts.models import Account
from organizations.models import OrganizationUser
from documents.models import PDF, Markdown
from projects.models import Project
from transformations import transform, OutputFormat, clear_registry

User = get_user_model()


@pytest.fixture(autouse=True)
def clean_registry():
    """Clear registry before and after each test."""
    clear_registry()
    yield
    clear_registry()


@pytest.fixture
def user_with_org(db):
    """Create user with organization."""
    user = User.objects.create_user(username="testuser", password="pass")
    org = Account.objects.create(name="Test Org")
    OrganizationUser.objects.create(organization=org, user=user)
    return user


@pytest.fixture
def project(db, user_with_org):
    """Create project."""
    org = user_with_org.organization_users.first().organization
    return Project.objects.create(name="Test Project", organization=org)


@pytest.mark.django_db
class TestPDFTransformers:
    """Test PDF document transformers."""

    def test_pdf_to_markdown(self, project, user_with_org):
        """Test PDF to Markdown transformation."""
        from transformations.transformers import document  # Trigger registration

        org = project.organization

        pdf = PDF.objects.create(
            name="Test PDF",
            description="A test document",
            file_size=1024,
            organization=org,
            project=project,
            created_by=user_with_org,
        )

        result = transform(pdf, OutputFormat.MARKDOWN)

        assert isinstance(result, str)
        assert "# Test PDF" in result
        assert "**Description:** A test document" in result
        assert "1024 bytes" in result

    def test_pdf_to_json(self, project, user_with_org):
        """Test PDF to JSON transformation."""
        from transformations.transformers import document

        org = project.organization

        pdf = PDF.objects.create(
            name="Test PDF",
            organization=org,
            project=project,
            created_by=user_with_org,
        )

        result = transform(pdf, OutputFormat.JSON)

        assert isinstance(result, dict)
        assert result["name"] == "Test PDF"
        assert result["type"] == "PDF"
        assert "id" in result
        assert "created_at" in result
```

---

## Summary

These examples demonstrate:

1. **Simple transformers** - Basic conversion without dependencies
2. **Dependency injection** - Using factories for service injection
3. **Multi-source transformers** - Single transformer for multiple types
4. **Chained transformations** - Pipeline processing with value objects
5. **Real-world integration** - API endpoints, background tasks, and testing

For more information, see the [README.md](README.md) documentation.
