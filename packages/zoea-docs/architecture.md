# Zoea Studio Technical Architecture

## Clipboard System

The app provides a clipboard concept: a managed list of contextual snippets scoped to a user and workspace. Each workspace maintains a single active clipboard per user, plus an optional list of "recent" clipboards that can be reactivated later. Users can build up a clipboard for a task, archive it when finished, and spin up a fresh clipboard for the next workflow. Dedicated views allow listing, deleting, and re-ordering clipboards for the current workspace/project.


### Context Clipboard

This is a special type of collection in the system meant to hold items that the user explicitly assigns throughout the course of a workspace session. It is intended that many different types of content can be linked to this data structure. For example, Conversation, Message, or Document types could all be added to this collection. But it will also accept things like pieces of code blocks within from within Messages, or extracted documents from a process, workflow artifacts, etc. which may be ephemeral or transient, but might be useful for a context or certain operation. 

Items are explicitly added to the Context Clipboard by the user via an action button or context menu.

The clipboard functions like a deque, accepting `ClipboardItem` entries at both ends. A `ClipboardItem` can either reference a Django model (via `content_type`/`object_id`) or store a "virtual" payload for ephemeral nodes created in the workspace.

1. A user uses a diagram editor (feature coming soon) to make a diagram; once they are happy with the result, they can add the diagram to the Context Clipboard via a button or context menu in the UI. 
2. A response Message in a Conversation contains fenced code or markdown block that the user would like to reuse.

## Model Relationships
```d2
Clipboard
ClipboardItem {
  style.multiple: true
  shape: diamond
}
Clipboard -- ClipboardItem
ClipboardItem -- Markdown: reference to
ClipboardItem -- Image: reference to
ClipboardItem -- Conversation Message: reference to
ClipboardItem -- workspace graph: reference to

```

## Agents

### Chat

### Graphologue Extraction

---

## Backend

### Data Models

#### Project

A project is the main unit of organization in Zoea Studio. A Project primarily consists of these main entities:

- Workspace - groups related knowledge, activity, and views for a Project

A project can have multiple workspaces used for organizing multiple lines of work. A project starts with a default workspace. 

Example: 

A research Project about the solar industry could have a few different Workspaces: one for building an index of equipment producers, one for tracking trends, and one for a knowledge base of regional laws and regulations. Each Workspace would share the Project's Documents, Collections, and Workflows while allow per-Workspace differences (filtered collections, dedicated workflows)

#### Workspace

Allows for a lens on the project. 
- Could set a child working directory 
- Filtered sets of the document collection. 
- Track which documents and resources are being used recently and frequently. 
- custom views, settings, configurations. 

#### Document and Collection

Files within the working directory are considered Documents of the project. ZoeaStudio favors working with text-based documents, especially Markdown. D2 diagram files are also well supported. 

Zoea Studio works best with document, text document files, PDFs, images, and spreadsheets. 

A collection is a filtered or manually selected set of project documents. 

There will be several different document types across a hierarchy of classes. Each document class will have a file field or image file field or something analogous associated that can associate the model with a storage class. I'd like to leverage the Django Storage API.  How should this be handled at the Model level? Would each base class be given a file field or image file field? Would there be any need or advantage to defining our own custom Django field type for the document models?  

##### Document Types Hierarchy
```d2
Document -- Image
Document -- Text
Document -- PDF

Text -- Markdown
Text -- Diagram
Text -- CSV

Diagram -- d2
Diagram -- React Flow geometry
```

##### Storage Schema







#### Workflows

Sequenced steps of actions or operations. The workflow system uses PocketFlow for orchestration with smolagents for LLM-powered tool execution.

Chat could be considered a default basic workflow for the application. 

Typically, workflows will involve interacting with a project, documents, and potentially other workflows. 

### User and Accounts

- django-organization
docs/DJANGO_ORGANIZATIONS_GUIDE.md
docs/DJANGO_ORGANIZATIONS_IMPLEMENTATION_PLAN.md

---

## Frontend

React, React Router, context for state

### Command Stack for Undo / Redo

TODO

### Views

#### Dashboard

- summarize recent activity

#### Chat

LLM powered chat feature. 

When the Chat view is activated, follow this sequence of steps to determine the display state:

TODO fix for current conversation
1. Display recent chats in the sidebar 
2. The Chat compononent should fill the content area; don't display the Conversation header / title bar
3. Once the user submits a message, this creates a new Conversation
4. Once a conversation has started, display the Conversation header / title bar at the top. 
5. If the user presses "New Chat" in the Conversation title bar, the current Conversation becomes the top item in the Recent Conversations component and return to the state in step 1.

When the user selects a recent conversation, this sequence of steps should be followed: 

1. Highlight the item in the Recent Conversations widget
2. Display the Conversation component in the main content area. It should be loaded with the existing conversation messages
3. Display the Conversation title bar 



#### Navigator

Display and explore Documents and Collections

#### Workflows

#### Canvas

d2canvas / diagram editor / playground

### State Management

- active conversation
- workspace documents
- undo/redo stack

### Components

#### Diagram 

Utilities (ZoeaStudio/frontend/src/utils/):
  - d2Compiler.js - D2 WASM compilation wrapper
  - d2ToReactFlow.js - Converts D2 graphs to React Flow format (v12 API)
  - d2CustomNodes.js - Custom node components (ContainerNode, DefaultNode)

Components (ZoeaStudio/frontend/src/components/):
  - DiagramPreview.jsx - Presentational component for rendering diagrams
  - DiagramPreview.css - Bootstrap-integrated styles
  - D2DiagramDisplay.jsx - Container component with compilation logic

##### Architecture

```
D2DiagramDisplay (Smart Container)
├─ Compiles D2 source → graph
├─ Converts graph → React Flow nodes/edges
└─> DiagramPreview (Presentational)
    └─ Renders React Flow diagram
```

Usage Example

```
import D2DiagramDisplay from './components/D2DiagramDisplay';

function MyComponent() {
const d2Code = `
    database: Database {
    users: Users Table
    posts: Posts Table
    }

    app: Application {
    api: API Server
    frontend: React App
    }

    app.frontend -> app.api
    app.api -> database.users
    app.api -> database.posts
`;

return (
    <div>
    <h2>System Architecture</h2>
    <D2DiagramDisplay
        d2Source={d2Code}
        compileOptions={{ layout: 'dagre' }}
    />
    </div>
);
}
```
