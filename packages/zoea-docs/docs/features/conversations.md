# Conversation Schema Documentation

This document provides comprehensive schema information for the chat and conversation models in Zoea Studio.

## Table of Contents
1. [Django Models](#django-models)
2. [SQL Schema](#sql-schema)
3. [Pydantic API Schemas](#pydantic-api-schemas)
4. [Relationships & Design Patterns](#relationships--design-patterns)

---

## Django Models

### Conversation Model

**Location:** `backend/chat/models.py:16`

**Purpose:** A conversation thread between a user and an agent

**Fields:**

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `id` | AutoField | Primary Key | Auto-incrementing conversation ID |
| `organization` | ForeignKey | NOT NULL, CASCADE | Organization this conversation belongs to (→ `organizations.Organization`) |
| `created_by` | ForeignKey | NOT NULL, CASCADE | User who started the conversation (→ `auth.User`) |
| `agent_name` | CharField(100) | NOT NULL, default='ZoeaAssistant' | Name of the AI agent used |
| `title` | CharField(200) | blank=True | Optional conversation title |
| `created_at` | DateTimeField | NOT NULL, auto_now_add | Timestamp when conversation was created |
| `updated_at` | DateTimeField | NOT NULL, auto_now | Timestamp of last update |

**Manager:** `OrganizationScopedQuerySet.as_manager()`
- Provides multi-tenant filtering via `.for_user(user)` and `.for_organization(org)`

**Meta Options:**
- **Ordering:** `['-updated_at']` (most recently updated first)
- **Indexes:**
  - `updated_at` (descending)
  - `organization, updated_at` (descending)
  - `created_by, updated_at` (descending)

**Methods:**

```python
def get_title(self) -> str:
    """
    Get conversation title, auto-generating from first message if not set.
    Returns first 50 chars of first user message + '...' if needed.
    """

def message_count(self) -> int:
    """Get total number of messages in this conversation."""

def user_message_count(self) -> int:
    """Get number of user messages in this conversation."""
```

---

### Message Model

**Location:** `backend/chat/models.py:92`

**Purpose:** A single message in a conversation (user, assistant, or system)

**Fields:**

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `id` | AutoField | Primary Key | Auto-incrementing message ID |
| `conversation` | ForeignKey | NOT NULL, CASCADE | Parent conversation (→ `chat.Conversation`) |
| `role` | CharField(20) | NOT NULL, choices | Message role: 'user', 'assistant', or 'system' |
| `content` | TextField | NOT NULL | Message content |
| `created_at` | DateTimeField | NOT NULL, auto_now_add | Timestamp when message was created |
| `token_count` | IntegerField | NULL, blank | Token count for cost tracking (optional) |
| `model_used` | CharField(100) | blank=True | AI model used to generate message (optional) |

**Role Choices:**
```python
ROLE_CHOICES = [
    ('user', 'User'),
    ('assistant', 'Assistant'),
    ('system', 'System'),
]
```

**Meta Options:**
- **Ordering:** `['created_at']` (chronological)
- **Indexes:**
  - `conversation, created_at`
  - `role, created_at`

**Methods:**

```python
def is_user_message(self) -> bool:
    """Check if this message is from a user."""

def is_assistant_message(self) -> bool:
    """Check if this message is from an assistant."""
```

---

## SQL Schema

### Database Tables (SQLite/PostgreSQL Compatible)

#### `chat_conversation` Table

```sql
CREATE TABLE "chat_conversation" (
    "id" integer NOT NULL PRIMARY KEY AUTOINCREMENT,
    "agent_name" varchar(100) NOT NULL,
    "title" varchar(200) NOT NULL,
    "created_at" datetime NOT NULL,
    "updated_at" datetime NOT NULL,
    "created_by_id" integer NOT NULL
        REFERENCES "auth_user" ("id") DEFERRABLE INITIALLY DEFERRED,
    "organization_id" integer NOT NULL
        REFERENCES "organizations_organization" ("id") DEFERRABLE INITIALLY DEFERRED
);
```

**Indexes:**
```sql
-- Composite index: organization + updated_at (descending)
CREATE INDEX "chat_conver_organiz_4034e8_idx"
    ON "chat_conversation" ("organization_id", "updated_at" DESC);

-- Composite index: created_by + updated_at (descending)
CREATE INDEX "chat_conver_created_f71722_idx"
    ON "chat_conversation" ("created_by_id", "updated_at" DESC);

-- Single column index: updated_at (descending)
CREATE INDEX "chat_conver_updated_1f6ffe_idx"
    ON "chat_conversation" ("updated_at" DESC);

-- Foreign key indexes
CREATE INDEX "chat_conversation_created_by_id_615454ae"
    ON "chat_conversation" ("created_by_id");
CREATE INDEX "chat_conversation_organization_id_37517453"
    ON "chat_conversation" ("organization_id");
```

---

#### `chat_message` Table

```sql
CREATE TABLE "chat_message" (
    "id" integer NOT NULL PRIMARY KEY AUTOINCREMENT,
    "role" varchar(20) NOT NULL,
    "content" text NOT NULL,
    "created_at" datetime NOT NULL,
    "token_count" integer NULL,
    "model_used" varchar(100) NOT NULL,
    "conversation_id" bigint NOT NULL
        REFERENCES "chat_conversation" ("id") DEFERRABLE INITIALLY DEFERRED
);
```

**Indexes:**
```sql
-- Composite index: conversation + created_at
CREATE INDEX "chat_messag_convers_3154fc_idx"
    ON "chat_message" ("conversation_id", "created_at");

-- Composite index: role + created_at
CREATE INDEX "chat_messag_role_35f48a_idx"
    ON "chat_message" ("role", "created_at");

-- Foreign key index
CREATE INDEX "chat_message_conversation_id_a1207bf4"
    ON "chat_message" ("conversation_id");
```

---

## Pydantic API Schemas

**Location:** `backend/chat/schemas.py`

### Request Schemas

#### `ChatRequest`

Used for sending messages to the chat endpoint.

```python
class ChatRequest(BaseModel):
    message: str                          # Required, min_length=1
    agent_name: str = "ZoeaAssistant"    # Optional, default provided
    instructions: str = "You are..."      # Optional, default provided
    conversation_id: Optional[int] = None # Optional, continues existing conversation
    conversation_history: Optional[str] = None  # Optional, for diagram generation
    debug: bool = False                   # Optional, enables debug output
```

---

### Response Schemas

#### `ChatResponse`

Response from the chat endpoint.

```python
class ChatResponse(BaseModel):
    response: str                              # Agent's response text
    agent_name: str                            # Name of agent that responded
    conversation_id: int                       # ID of conversation
    diagram: Optional[DiagramData] = None      # Diagram data (if generated)
    system_instructions: Optional[str] = None  # Debug: system instructions
    organization: Optional[str] = None         # Debug: organization name
```

#### `DiagramData`

Graphologue diagram representation.

```python
class DiagramData(BaseModel):
    annotated_text: str        # Text with entity/relation annotations
    nodes: List[DiagramNode]   # List of concept nodes
    edges: List[DiagramEdge]   # List of relationships
    react_flow: Dict           # React Flow compatible structure
```

#### `DiagramNode`

```python
class DiagramNode(BaseModel):
    id: str       # Unique node identifier (e.g., "N1")
    label: str    # Display label
    raw_id: str   # Original identifier from annotation
```

#### `DiagramEdge`

```python
class DiagramEdge(BaseModel):
    id: str        # Unique edge identifier
    label: str     # Relationship label
    source: str    # Source node ID
    target: str    # Target node ID
    saliency: str  # Importance level ('high', 'medium', 'low')
```

---

#### `ConversationListResponse`

Response for listing conversations.

```python
class ConversationListResponse(BaseModel):
    conversations: List[ConversationListItem]  # List of conversation summaries
    total: int                                 # Total count
```

#### `ConversationListItem`

Summary of a conversation for list view.

```python
class ConversationListItem(BaseModel):
    id: int                # Conversation ID
    title: str             # Conversation title
    agent_name: str        # Agent used
    message_count: int     # Total message count
    created_at: datetime   # Creation timestamp
    updated_at: datetime   # Last update timestamp

    class Config:
        from_attributes = True  # Allows creation from Django model instances
```

---

#### `ConversationDetailResponse`

Response for getting conversation details.

```python
class ConversationDetailResponse(BaseModel):
    id: int                     # Conversation ID
    title: str                  # Conversation title
    agent_name: str             # Agent used
    messages: List[MessageItem] # All messages in conversation
    created_at: datetime        # Creation timestamp
    updated_at: datetime        # Last update timestamp
```

#### `MessageItem`

Individual message in conversation detail.

```python
class MessageItem(BaseModel):
    id: int                           # Message ID
    role: str                         # 'user', 'assistant', or 'system'
    content: str                      # Message content
    created_at: datetime              # Creation timestamp
    model_used: Optional[str] = None  # Model used (assistant messages only)

    class Config:
        from_attributes = True  # Allows creation from Django model instances
```

---

## Relationships & Design Patterns

### Entity Relationship Diagram

```
┌─────────────────────────┐
│  organizations_         │
│  organization           │
└──────────┬──────────────┘
           │ 1
           │
           │ N
┌──────────▼──────────────┐
│  chat_conversation      │
│  ├─ id (PK)            │
│  ├─ organization_id    │◄─────┐
│  ├─ created_by_id      │      │
│  ├─ agent_name         │      │
│  ├─ title              │      │
│  ├─ created_at         │      │
│  └─ updated_at         │      │
└──────────┬──────────────┘      │
           │ 1                   │
           │                     │ Cascade Delete
           │ N                   │
┌──────────▼──────────────┐      │
│  chat_message           │      │
│  ├─ id (PK)            │      │
│  ├─ conversation_id ───┼──────┘
│  ├─ role               │
│  ├─ content            │
│  ├─ created_at         │
│  ├─ token_count (opt)  │
│  └─ model_used (opt)   │
└─────────────────────────┘

        ┌─────────────┐
        │  auth_user  │
        └──────┬──────┘
               │ 1
               │
               │ N
               └─────► conversation.created_by_id
```

### Design Patterns

#### 1. Multi-Tenant Architecture

All conversations are scoped to organizations:

```python
# Custom queryset provides automatic filtering
class OrganizationScopedQuerySet(models.QuerySet):
    def for_user(self, user):
        """Filter to organizations the user belongs to."""
        return self.filter(organization__organization_users__user=user)

    def for_organization(self, organization):
        """Filter to a specific organization."""
        return self.filter(organization=organization)

# Usage in views:
conversations = Conversation.objects.for_user(request.user)
```

#### 2. Cascading Deletes

- When a **Conversation** is deleted → all **Messages** are deleted (CASCADE)
- When an **Organization** is deleted → all **Conversations** are deleted (CASCADE)
- When a **User** is deleted → all **Conversations** they created are deleted (CASCADE)

#### 3. Soft Metadata

Optional fields enable analytics without breaking core functionality:

- `Message.token_count` - for cost tracking
- `Message.model_used` - for model comparison
- `Conversation.title` - auto-generated if not provided

#### 4. Automatic Timestamps

- `created_at` - set once on creation (`auto_now_add=True`)
- `updated_at` - updated on every save (`auto_now=True`)

#### 5. Indexed Queries

Common query patterns are optimized:

```python
# Get user's recent conversations (uses: created_by + updated_at index)
Conversation.objects.filter(created_by=user).order_by('-updated_at')

# Get organization's conversations (uses: organization + updated_at index)
Conversation.objects.filter(organization=org).order_by('-updated_at')

# Get messages in conversation chronologically (uses: conversation + created_at index)
Message.objects.filter(conversation=conv).order_by('created_at')

# Get all assistant messages (uses: role + created_at index)
Message.objects.filter(role='assistant').order_by('created_at')
```

#### 6. API Validation

Pydantic schemas provide:

- **Request validation:** Type checking, field constraints (min_length, etc.)
- **Response serialization:** Automatic conversion from Django models (`from_attributes=True`)
- **API documentation:** Auto-generated OpenAPI docs at `/api/docs`

#### 7. Conversation History Building

Frontend builds conversation history for diagram generation:

```python
# Backend expects this format in conversation_history:
"""
User: First message