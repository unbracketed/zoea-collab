# Document RAG Chat

Chat with your documents using AI-powered retrieval augmented generation (RAG). Ask questions about document contents and get answers with source citations.

## Overview

The Document RAG feature lets you have conversations with your documents. The AI agent retrieves relevant passages from your documents to answer questions accurately, showing which sources it used.

**Supported document types:**

- Markdown documents
- PDF files
- Images (analyzed via vision AI)
- Text documents

## Getting Started

### Chat with a Single Document

1. Navigate to any document detail page
2. Click the **chat icon** (💬) in the header
3. A chat modal opens with the document indexed
4. Ask questions about the document content

### Chat with Folder Contents

1. Go to the **Documents** page
2. Select a folder from the sidebar
3. Click **New** → **Chat with documents**
4. All documents in that folder are indexed for the session

### Chat with Clipboard Items

1. Go to the **Clipboards** page
2. Ensure your clipboard has document items
3. Click the **chat icon** (💬) in the header
4. All clipboard documents are indexed together

## Using the Chat Interface

### Chat Panel

The left side of the modal shows your conversation:

- Type questions in the input field at the bottom
- Press Enter or click Send to submit
- AI responses appear with typing animation
- Each response can show source citations

### Sources Sidebar

The right sidebar shows retrieved sources:

- Displays documents used to answer your question
- Shows document name and type
- Includes excerpt snippets from retrieved passages
- Updates after each response

### Example Questions

**For a project README:**
```
What technologies does this project use?
How do I run the tests?
What are the environment variables I need to set?
```

**For meeting notes folder:**
```
What decisions were made about the API design?
Summarize the action items from the last sprint
Who is responsible for the authentication feature?
```

**For research documents:**
```
What are the key findings about X?
Compare the approaches mentioned in these papers
What methodology was used in the study?
```

## Session Lifecycle

### Session Creation

When you open the chat modal:

1. Documents are resolved based on context (single/folder/clipboard)
2. A temporary Gemini File Search store is created
3. Documents are uploaded and indexed
4. Session becomes active (ready to chat)

### Session Duration

- Sessions have a 2-hour time-to-live (TTL)
- The session remains active while the modal is open
- Closing the modal ends the session immediately

### Session Cleanup

When you close the chat modal:

1. The Gemini store is deleted
2. Session is marked as closed
3. No document data persists after the session

## Tips for Better Results

### Be Specific

Instead of vague questions, ask specific ones:

| Less Effective | More Effective |
|----------------|----------------|
| "Tell me about this" | "What is the main purpose of this document?" |
| "How does it work?" | "How does the authentication flow work?" |
| "What's important?" | "What are the key configuration options?" |

### Reference Document Context

The AI knows the document context, so you can ask:

- "In section 2, what does X mean?"
- "Based on this document, should I use approach A or B?"
- "Summarize the main points from pages 1-5"

### Multi-Document Queries

When chatting with folders or clipboards:

- "Compare these documents..."
- "What do all these documents have in common?"
- "Which document discusses X?"

## Limitations

- **Session-based**: Each session creates a fresh index; no persistent memory
- **Document size**: Very large documents may take longer to index
- **Image analysis**: Works best with clear text and diagrams
- **No streaming**: Responses appear after full generation (not streamed)

## Troubleshooting

### "No documents found"

- Ensure the folder/clipboard contains documents
- Check that documents have content (not empty)

### Slow initial load

- Large documents or many files take longer to index
- The first message may take 10-30 seconds while indexing completes

### Unexpected answers

- Try rephrasing your question
- Check the Sources sidebar to see what was retrieved
- Use more specific terminology from your documents

## Related Features

- [Gemini File Search](gemini-search.md) - CLI-based document search
- [Clipboard System](clipboard.md) - Managing clipboard items
