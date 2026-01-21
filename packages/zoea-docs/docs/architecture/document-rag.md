# Document RAG Architecture

Technical architecture for the Document RAG chat system, which enables conversational AI over document collections using smolagents and Gemini File Search.

## System Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                         Frontend                                 │
├─────────────────────────────────────────────────────────────────┤
│  DocumentRAGModal                                                │
│  ├── RAGChatPanel (messages + input)                            │
│  └── RAGSourcesList (retrieved sources sidebar)                 │
│                                                                  │
│  ragStore.js (Zustand) ←→ ragApi.js                             │
└──────────────────────────┬──────────────────────────────────────┘
                           │ HTTP API
┌──────────────────────────▼──────────────────────────────────────┐
│                         Backend                                  │
├─────────────────────────────────────────────────────────────────┤
│  document_rag/api.py (Django Ninja)                              │
│  ├── POST /api/rag/sessions     → Create session                │
│  ├── GET  /api/rag/sessions/:id → Get session + messages        │
│  ├── POST /api/rag/sessions/:id/chat → Send message             │
│  └── DELETE /api/rag/sessions/:id → Close session               │
│                                                                  │
│  RAGSessionManager                                               │
│  ├── Resolves documents (single/folder/clipboard/collection)    │
│  ├── Creates ephemeral Gemini store                             │
│  └── Uploads documents for indexing                             │
│                                                                  │
│  DocumentRAGAgentService (smolagents CodeAgent)                  │
│  ├── GeminiRetrieverTool → Queries Gemini File Search           │
│  └── ImageAnalyzerTool → Analyzes images via OpenAI Vision      │
└──────────────────────────┬──────────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────────┐
│                   External Services                              │
├─────────────────────────────────────────────────────────────────┤
│  Gemini File Search API                                          │
│  └── Ephemeral vector store for document retrieval              │
│                                                                  │
│  OpenAI API                                                      │
│  ├── CodeAgent LLM (orchestration)                              │
│  └── Vision API (image analysis)                                │
└─────────────────────────────────────────────────────────────────┘
```

## Backend Components

### Django App Structure

```
backend/document_rag/
├── __init__.py
├── admin.py
├── api.py              # Django Ninja router
├── apps.py
├── models.py           # RAGSession, RAGSessionMessage
├── schemas.py          # Pydantic request/response schemas
├── session_manager.py  # Session lifecycle management
├── agent_service.py    # smolagents CodeAgent wrapper
├── management/
│   └── commands/
│       └── cleanup_rag_sessions.py
└── tools/
    ├── __init__.py
    ├── gemini_retriever.py   # Document retrieval tool
    └── image_analyzer.py     # Vision analysis tool
```

### Models

#### RAGSession

Tracks ephemeral chat sessions with multi-tenant isolation:

```python
class RAGSession(models.Model):
    class ContextType(models.TextChoices):
        SINGLE = "single"         # Single document
        FOLDER = "folder"         # All docs in folder
        CLIPBOARD = "clipboard"   # Clipboard items
        COLLECTION = "collection" # Document collection

    class Status(models.TextChoices):
        INITIALIZING = "initializing"
        ACTIVE = "active"
        CLOSED = "closed"
        ERROR = "error"

    session_id = models.UUIDField(unique=True)
    organization = models.ForeignKey(Organization)
    project = models.ForeignKey(Project)
    workspace = models.ForeignKey(Workspace)
    created_by = models.ForeignKey(User)

    context_type = models.CharField(choices=ContextType.choices)
    context_id = models.PositiveIntegerField()
    document_ids = models.JSONField()  # List of document IDs

    gemini_store_id = models.CharField()  # Ephemeral store name
    status = models.CharField(choices=Status.choices)
    expires_at = models.DateTimeField()  # 2hr TTL default
```

#### RAGSessionMessage

Stores conversation history with retrieved sources:

```python
class RAGSessionMessage(models.Model):
    class Role(models.TextChoices):
        USER = "user"
        ASSISTANT = "assistant"

    session = models.ForeignKey(RAGSession, related_name="messages")
    role = models.CharField(choices=Role.choices)
    content = models.TextField()
    retrieved_documents = models.JSONField()  # Source citations
    thinking_steps = models.JSONField()       # Agent reasoning
    created_at = models.DateTimeField(auto_now_add=True)
```

### Session Manager

`RAGSessionManager` handles the session lifecycle:

```python
class RAGSessionManager:
    async def create_session(self, user, context_type, context_id, project, workspace):
        # 1. Resolve documents based on context type
        documents = await self._resolve_documents(context_type, context_id, workspace)

        # 2. Create session record
        session = await RAGSession.objects.acreate(...)

        # 3. Create ephemeral Gemini store
        store = await sync_to_async(self.gemini_service.create_ephemeral_store)(
            f"rag-session-{session.session_id.hex[:8]}"
        )

        # 4. Upload documents to store
        for doc in documents:
            await sync_to_async(self.gemini_service.upload_document)(doc, store["name"])

        return session

    async def close_session(self, session):
        # Delete Gemini store and mark closed
        await sync_to_async(self.gemini_service.delete_store)(session.gemini_store_id)
        session.status = RAGSession.Status.CLOSED
        await session.asave()
```

#### Document Resolution

Different context types resolve to documents differently:

| Context Type | Resolution Logic |
|--------------|------------------|
| `single` | Direct document lookup by ID |
| `folder` | All documents in folder (via MPTT) |
| `clipboard` | Documents referenced by clipboard items (GenericForeignKey) |
| `collection` | Documents in collection M2M relationship |

### Agent Service

`DocumentRAGAgentService` wraps smolagents CodeAgent:

```python
class DocumentRAGAgentService:
    def __init__(self, session: RAGSession):
        # Initialize tools
        self.retriever_tool = GeminiRetrieverTool(store_id=session.gemini_store_id)
        self.image_analyzer_tool = ImageAnalyzerTool()

        # Create CodeAgent with OpenAI
        self.model = OpenAIServerModel(model_id="gpt-4o")
        self.agent = CodeAgent(
            tools=[self.retriever_tool, self.image_analyzer_tool],
            model=self.model,
            max_steps=6,
        )

    async def chat(self, message: str, conversation_history) -> RAGAgentResponse:
        # Build task with conversation context
        task = self._build_task(message, conversation_history)

        # Run agent
        result = await sync_to_async(self.agent.run)(task)

        # Extract sources from retriever tool
        sources = self.retriever_tool.get_last_sources()

        return RAGAgentResponse(
            content=result,
            sources=sources,
            thinking_steps=self.agent.logs,
        )
```

### smolagents Tools

#### GeminiRetrieverTool

Queries the ephemeral Gemini File Search store:

```python
class GeminiRetrieverTool(Tool):
    name = "document_retriever"
    description = "Retrieves relevant passages from indexed documents..."
    inputs = {
        "query": {"type": "string", "description": "Search query"},
        "max_results": {"type": "integer", "nullable": True},
    }
    output_type = "string"

    def forward(self, query: str, max_results: int = 5) -> str:
        # Query Gemini File Search
        response = self.client.models.generate_content(
            model="gemini-2.5-flash",
            contents=query,
            config=GenerateContentConfig(
                tools=[Tool(file_search=FileSearch(store_ids=[self.store_id]))],
            ),
        )

        # Track sources for citation
        self._last_sources = self._extract_sources(response)

        return self._format_results(response)
```

#### ImageAnalyzerTool

Analyzes image documents using OpenAI Vision:

```python
class ImageAnalyzerTool(Tool):
    name = "image_analyzer"
    description = "Analyzes images to extract visual information..."

    def forward(self, image_url: str, question: str) -> str:
        response = self.client.chat.completions.create(
            model="gpt-4o",
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": question},
                    {"type": "image_url", "image_url": {"url": image_url}},
                ],
            }],
        )
        return response.choices[0].message.content
```

### API Endpoints

All endpoints are under `/api/rag/`:

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/sessions` | Create session with context |
| `GET` | `/sessions/{id}` | Get session status and messages |
| `POST` | `/sessions/{id}/chat` | Send message to agent |
| `DELETE` | `/sessions/{id}` | Close session and cleanup |

#### Request/Response Schemas

```python
class CreateRAGSessionRequest(Schema):
    context_type: str  # single, folder, clipboard, collection
    context_id: int
    project_id: int
    workspace_id: int

class RAGChatRequest(Schema):
    message: str

class RAGChatResponse(Schema):
    message_id: int
    content: str
    sources: list[DocumentSourceRef]
    created_at: datetime
```

## Frontend Components

### Zustand Store

`ragStore.js` manages client-side state:

```javascript
export const useRAGStore = create((set, get) => ({
  session: null,
  messages: [],
  sources: [],
  isLoading: false,
  error: null,

  createSession: async ({ contextType, contextId, projectId, workspaceId }) => {
    set({ isLoading: true, error: null });
    const session = await ragApi.createSession({ ... });
    set({ session, isLoading: false });
  },

  sendMessage: async (message) => {
    // Add user message optimistically
    set(state => ({ messages: [...state.messages, userMessage] }));

    // Call API
    const response = await ragApi.chat(session.session_id, { message });

    // Add assistant message and update sources
    set(state => ({
      messages: [...state.messages, assistantMessage],
      sources: response.sources,
    }));
  },

  closeSession: async () => {
    await ragApi.closeSession(session.session_id);
    set({ session: null, messages: [], sources: [] });
  },
}));
```

### Component Hierarchy

```
DocumentRAGModal
├── Header (title, document count, close button)
├── Content
│   ├── RAGChatPanel (70% width)
│   │   ├── Messages list
│   │   │   └── RAGMessageBubble (per message)
│   │   │       └── Sources toggle (for assistant messages)
│   │   └── Input area (textarea + send button)
│   └── RAGSourcesList (30% width, sidebar)
│       └── Source cards with excerpts
└── Loading overlay (during session creation)
```

## Session Lifecycle

### Ephemeral Store Design

Each session creates a dedicated Gemini File Search store:

```
Session Created → Store Created → Documents Uploaded → Ready to Chat
       ↓
Session Closed → Store Deleted → Data Removed
```

**Rationale:**

1. **Isolation**: No cross-session data leakage
2. **Cleanup**: Automatic deletion, no orphaned data
3. **Flexibility**: Different document sets per session
4. **Simplicity**: No complex access control needed

### Cleanup Mechanisms

1. **On modal close**: Frontend calls `DELETE /api/rag/sessions/{id}`
2. **On session fetch**: Expired sessions auto-close
3. **Management command**: `cleanup_rag_sessions` for orphaned sessions

```bash
# Run manually
python manage.py cleanup_rag_sessions

# Dry run to see what would be cleaned
python manage.py cleanup_rag_sessions --dry-run

# Schedule via cron (every 15 minutes)
*/15 * * * * cd /path/to/backend && uv run python manage.py cleanup_rag_sessions
```

## Configuration

### Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `GEMINI_API_KEY` | Google Gemini API key | Yes |
| `OPENAI_API_KEY` | OpenAI API key (for agent LLM) | Yes |

### Session Settings

```python
# document_rag/models.py
DEFAULT_SESSION_TTL = timedelta(hours=2)
```

## Dependencies

Backend (`pyproject.toml`):

```toml
dependencies = [
    "smolagents>=1.14.0",
    # ... other deps
]
```

The `smolagents` package provides:

- `CodeAgent`: Agent that writes Python code to orchestrate tools
- `Tool`: Base class for creating custom tools
- `OpenAIServerModel`: LLM wrapper for OpenAI models

## Security Considerations

### Multi-Tenant Isolation

- Sessions are scoped to organization/project/workspace
- API endpoints verify user access to context resources
- Gemini stores are ephemeral and session-specific

### Data Handling

- Document content is uploaded to Gemini (Google's infrastructure)
- Stores are deleted when sessions close
- No persistent storage of document content in RAG system

### Rate Limiting

- Consider adding rate limits on session creation
- Max concurrent sessions per user (not currently implemented)

## Future Improvements

1. **Streaming responses**: Use Server-Sent Events for real-time output
2. **Persistent sessions**: Option to keep sessions for longer periods
3. **Shared sessions**: Multiple users chatting with same document set
4. **Memory**: Cross-session learning and personalization
5. **Custom prompts**: User-configurable system prompts
