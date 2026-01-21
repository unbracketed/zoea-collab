# Rich Text Documents (Yoopta)

Zoea Studio supports rich text editing through [Yoopta-Editor](https://yoopta.dev/), a Notion-like block-based editor. This provides a WYSIWYG experience for creating formatted documents without writing Markdown.

## Features

- **Block-based editing**: Paragraphs, headings (H1-H6), bullet/numbered lists, code blocks, blockquotes
- **Inline formatting**: Bold, italic, underline, strikethrough, inline code
- **Slash commands**: Type `/` to insert blocks quickly
- **Export**: Download as HTML or Markdown
- **Theme support**: Light/dark mode syncs with app theme
- **Search integration**: Content indexed in Gemini for document search

## Creating a Rich Text Document

1. Navigate to Documents in your workspace
2. Click **New Document**
3. Select **Rich Text (Yoopta)** as the document type
4. Enter a document name
5. Start typing in the editor

### Slash Commands

Press `/` in the editor to open the block menu:
- `/p` or `/paragraph` - Plain text
- `/h1`, `/h2`, `/h3` - Headings
- `/bullet` or `/ul` - Bulleted list
- `/numbered` or `/ol` - Numbered list
- `/code` - Code block
- `/quote` - Blockquote

## Editing Documents

- Click on any document in the list to open it
- Click **Edit** to enter edit mode
- Changes auto-save after a brief delay
- Click **View** to return to read-only mode

## Exporting Documents

Rich text documents can be exported to HTML or Markdown:

1. Open the document
2. Click the **Export** dropdown
3. Choose format:
   - **Download as HTML** - Full HTML file
   - **Download as Markdown** - Plain markdown text
   - **Copy HTML** / **Copy Markdown** - Copy to clipboard

## API Reference

### Create Document
```
POST /api/documents/yoopta/create
```
```json
{
  "name": "My Document",
  "description": "Optional description",
  "content": "{...yoopta JSON...}",
  "project_id": 1,
  "workspace_id": 1,
  "folder_id": null
}
```

### Update Document
```
PATCH /api/documents/yoopta/{id}
```
```json
{
  "name": "Updated Name",
  "content": "{...yoopta JSON...}"
}
```

### Export Document
```
GET /api/documents/yoopta/{id}/export?format=markdown
GET /api/documents/yoopta/{id}/export?format=html
```
Returns:
```json
{
  "content": "# Exported content...",
  "format": "markdown",
  "document_id": 123,
  "document_name": "My Document"
}
```

## Architecture

### Backend Model

`YooptaDocument` extends `TextDocument` (multi-table inheritance):

```python
class YooptaDocument(TextDocument):
    yoopta_version = models.CharField(max_length=20, default="4.0")

    def get_text_content(self) -> str:
        """Extract plain text from Yoopta JSON for search indexing."""

    def get_markdown_content(self) -> str:
        """Convert Yoopta JSON to Markdown."""

    def get_html_content(self) -> str:
        """Convert Yoopta JSON to HTML."""
```

Content is stored as JSON in the inherited `content` field.

### Frontend Components

| Component | Location | Purpose |
|-----------|----------|---------|
| `YooptaEditor` | `frontend/src/components/documents/YooptaEditor.jsx` | Editable rich text editor |
| `YooptaViewer` | `frontend/src/components/documents/YooptaViewer.jsx` | Read-only content viewer |

### Yoopta JSON Structure

Content follows the Yoopta block format:

```json
{
  "block-id-1": {
    "id": "block-id-1",
    "meta": { "order": 0 },
    "type": "HeadingOne",
    "value": [
      {
        "id": "element-1",
        "type": "heading-one",
        "children": [{ "text": "My Heading" }]
      }
    ]
  },
  "block-id-2": {
    "id": "block-id-2",
    "meta": { "order": 1 },
    "type": "Paragraph",
    "value": [
      {
        "id": "element-2",
        "type": "paragraph",
        "children": [
          { "text": "Normal text " },
          { "text": "bold", "bold": true }
        ]
      }
    ]
  }
}
```

## Search Integration

Yoopta documents are automatically indexed in Gemini file search:

1. `get_text_content()` extracts plain text from all blocks
2. Text is synced to Gemini via `gemini_file_id`
3. Documents appear in project-wide search results

## Supported Block Types

| Block Type | Yoopta Type | Markdown Export | HTML Export |
|------------|-------------|-----------------|-------------|
| Paragraph | `Paragraph` | Plain text | `<p>` |
| Heading 1-6 | `HeadingOne`-`HeadingSix` | `#` - `######` | `<h1>` - `<h6>` |
| Bulleted List | `BulletedList` | `- item` | `<ul><li>` |
| Numbered List | `NumberedList` | `1. item` | `<ol><li>` |
| Code Block | `Code` | ` ```lang ` | `<pre><code>` |
| Blockquote | `Blockquote` | `> quote` | `<blockquote>` |
| Link | inline | `[text](url)` | `<a href>` |
