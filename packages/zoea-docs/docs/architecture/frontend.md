# Frontend Architecture

The Zoea Studio frontend is a modern React application built with Vite, featuring a modular layout system, page-based routing, and comprehensive state management with Zustand.

## Technology Stack

- **React 18** - UI framework with hooks
- **Vite** - Build tool and dev server
- **Zustand** - Lightweight state management
- **React Router** - Client-side routing with lazy loading
- **Tailwind CSS** - Utility-first CSS with shadcn.io semantic tokens
- **shadcn.io Theme System** - OKLCH-based themes with light/dark mode

!!! important "React StrictMode"
    The application runs with StrictMode enabled in development. Read `docs/react-strictmode-patterns.md` **before** implementing data loading to avoid infinite loops.

## Project Structure

```
frontend/
├── src/
│   ├── main.jsx                        # Entry point
│   ├── App.jsx                         # Root component
│   ├── Routes.jsx                      # Route definitions with lazy loading
│   ├── pages/                          # Page components
│   │   ├── DashboardPage.jsx
│   │   ├── ChatPage.jsx
│   │   ├── CanvasPage.jsx
│   │   ├── ClipboardsPage.jsx
│   │   ├── DocumentsPage.jsx
│   │   ├── DocumentDetailPage.jsx
│   │   ├── DocumentEditorPage.jsx
│   │   ├── ImageUploadPage.jsx
│   │   ├── ProjectsPage.jsx
│   │   ├── WorkspacesPage.jsx
│   │   ├── WorkflowsPage.jsx
│   │   └── SettingsPage.jsx
│   ├── components/
│   │   ├── layout/                     # Layout system
│   │   │   ├── LayoutFrame.jsx         # Main layout wrapper
│   │   │   ├── app/                    # App shell components
│   │   │   │   ├── AppContainer.jsx
│   │   │   │   ├── AppHeader.jsx
│   │   │   │   ├── NavigationBar.jsx
│   │   │   │   └── ProjectsBar.jsx
│   │   │   ├── sidebar/                # Sidebar components
│   │   │   │   ├── Sidebar.jsx
│   │   │   │   └── SidebarSection.jsx
│   │   │   └── view/                   # View layout variants
│   │   │       ├── ViewContainer.jsx
│   │   │       ├── ViewContext.jsx
│   │   │       ├── ViewHeader.jsx
│   │   │       ├── ViewPrimaryActions.jsx
│   │   │       ├── FullContentView.jsx
│   │   │       ├── TwoPaneView.jsx
│   │   │       └── ContentCenteredView.jsx
│   │   ├── documents/                  # Document components
│   │   │   ├── DocumentsList.jsx
│   │   │   └── DocumentsView.jsx
│   │   ├── AuthGuard.jsx               # Route protection
│   │   ├── Login.jsx                   # Authentication UI
│   │   ├── MessageContent.jsx          # Chat message rendering
│   │   ├── MarkdownViewer.jsx          # Markdown display
│   │   ├── DiagramPreview.jsx          # Diagram visualization
│   │   ├── ReactFlowDiagram.jsx        # React Flow wrapper
│   │   ├── D2DiagramDisplay.jsx        # D2 compilation container
│   │   ├── ClipboardPanel.jsx          # Clipboard sidebar
│   │   ├── ConversationHeader.jsx
│   │   ├── ConversationList.jsx
│   │   ├── ProjectWorkspaceSelector.jsx
│   │   └── ThemeToggler.jsx            # Dark/light mode toggle
│   ├── stores/                         # Zustand stores
│   │   ├── index.js                    # Central exports
│   │   ├── authStore.js                # Authentication state
│   │   ├── workspaceStore.js           # Project/workspace selection
│   │   ├── documentStore.js            # Document management
│   │   ├── conversationStore.js        # Chat conversations
│   │   ├── clipboardStore.js           # Clipboard items
│   │   ├── layoutStore.js              # Sidebar/layout state
│   │   ├── navigationStore.js          # Navigation state
│   │   └── diagramStore.js             # Diagram visualization
│   ├── services/
│   │   └── api.js                      # Axios API client
│   ├── utils/
│   │   ├── d2Compiler.js               # D2 WASM wrapper
│   │   ├── d2ToReactFlow.js            # D2 → React Flow converter
│   │   └── d2CustomNodes.jsx           # Custom node components
│   └── styles/
│       ├── App.css                     # Global styles
│       ├── shadcn-themes.css           # Theme definitions (OKLCH)
│       └── index.css                   # Base styles and Tailwind imports
├── tests/                              # Playwright E2E tests
│   ├── pages/                          # Page Object Models
│   └── e2e/                            # Test specs
├── package.json
└── vite.config.js
```

## Layout System

The frontend uses a modular layout system that provides consistent structure across all pages.

### LayoutFrame

The main layout wrapper that coordinates all layout components:

```jsx
import LayoutFrame from '../components/layout/LayoutFrame';

function MyPage() {
  return (
    <LayoutFrame
      title="Page Title"
      actions={<ActionButtons />}
      sidebar={<CustomSidebar />}
      variant="full"  // 'full', 'two-pane', or 'content-centered'
    >
      {/* Page content */}
    </LayoutFrame>
  );
}
```

**Props:**

| Prop | Type | Description |
|------|------|-------------|
| `title` | string | Page header title |
| `actions` | ReactNode | Header action buttons |
| `sidebar` | ReactNode | Custom sidebar content |
| `variant` | string | Layout variant: `full`, `two-pane`, `content-centered` |
| `leftSlot` | ReactNode | Left pane content (two-pane only) |
| `rightSlot` | ReactNode | Right pane content (two-pane only) |
| `maxWidth` | string | Max content width (content-centered only) |
| `noPadding` | boolean | Remove content padding |

### Layout Variants

#### FullContentView

Full-width content area with optional sidebar:

```jsx
<LayoutFrame variant="full" title="Documents">
  <DocumentsList />
</LayoutFrame>
```

#### TwoPaneView

Split view with left and right panels:

```jsx
<LayoutFrame
  variant="two-pane"
  title="Chat"
  leftSlot={<ConversationList />}
  rightSlot={<ChatMessages />}
/>
```

#### ContentCenteredView

Centered content with maximum width constraint:

```jsx
<LayoutFrame
  variant="content-centered"
  title="Settings"
  maxWidth="800px"
>
  <SettingsForm />
</LayoutFrame>
```

### AppContainer

The full application shell with navigation:

```
┌─────────────────────────────────────────────────────────────┐
│  AppHeader (logo, theme toggle, user menu)                  │
├──────────┬──────────────────────────────────────────────────┤
│ Projects │  NavigationBar (Dashboard, Chat, Documents...)   │
│   Bar    ├──────────────────────────────────────────────────┤
│          │                                                   │
│          │  ViewContainer (page content)                     │
│          │                                                   │
│          │                                                   │
│          ├──────────────────────────────────────────────────┤
│          │  Sidebar (clipboards, context items)              │
└──────────┴──────────────────────────────────────────────────┘
```

### Navigation Items

Defined in `LayoutFrame.jsx`:

```javascript
const NAV_ITEMS = [
  { id: 'dashboard', label: 'Dashboard', icon: 'layout-dashboard', path: '/dashboard' },
  { id: 'chat', label: 'Chat', icon: 'chat', path: '/chat' },
  { id: 'documents', label: 'Documents', icon: 'documents', path: '/documents' },
  { id: 'clipboards', label: 'Clipboards', icon: 'clipboards', path: '/clipboards' },
  { id: 'canvas', label: 'Canvas', icon: 'canvas', path: '/canvas' },
  { id: 'workflows', label: 'Workflows', icon: 'workflows', path: '/workflows' },
  { id: 'settings', label: 'Settings', icon: 'settings', path: '/settings' },
];
```

## State Management

### Zustand Stores

Zoea Studio uses Zustand for lightweight, hook-based state management:

```javascript
import { create } from 'zustand';

const useWorkspaceStore = create((set, get) => ({
  projects: [],
  workspaces: [],
  currentProjectId: null,
  currentWorkspaceId: null,

  setProjects: (projects) => set({ projects }),
  setCurrentProject: (id) => set({ currentProjectId: id }),

  // Async actions
  loadProjects: async () => {
    const projects = await api.getProjects();
    set({ projects });
  },
}));
```

### Available Stores

| Store | Purpose |
|-------|---------|
| `authStore` | User authentication, login/logout |
| `workspaceStore` | Project and workspace selection |
| `documentStore` | Document CRUD operations |
| `conversationStore` | Chat conversation management |
| `clipboardStore` | Clipboard items for current workspace |
| `layoutStore` | Sidebar expanded/collapsed state |
| `navigationStore` | Current navigation state |
| `diagramStore` | Diagram visualization state |

### Using Stores

```javascript
import { useWorkspaceStore, useDocumentStore } from '../stores';
import { useShallow } from 'zustand/react/shallow';

function MyComponent() {
  // Select specific state slices
  const { projects, currentProjectId } = useWorkspaceStore(
    useShallow((state) => ({
      projects: state.projects,
      currentProjectId: state.currentProjectId,
    }))
  );

  // Access actions
  const loadDocuments = useDocumentStore((state) => state.loadDocuments);

  useEffect(() => {
    loadDocuments(currentProjectId);
  }, [currentProjectId]);

  return <ProjectList projects={projects} />;
}
```

## Routing

### Route Definitions

Routes are defined in `Routes.jsx` with lazy loading:

```javascript
import { lazy, Suspense } from 'react';
import { Routes, Route, Navigate, Outlet } from 'react-router-dom';
import AuthGuard from './components/AuthGuard';

const DashboardPage = lazy(() => import('./pages/DashboardPage'));
const ChatPage = lazy(() => import('./pages/ChatPage'));
// ... other lazy imports

function AppRoutes() {
  return (
    <Suspense fallback={<Loader />}>
      <Routes>
        <Route element={<AuthGuard><Outlet /></AuthGuard>}>
          <Route path="/" element={<Navigate to="/dashboard" replace />} />
          <Route path="/dashboard" element={<DashboardPage />} />
          <Route path="/chat" element={<ChatPage />} />
          <Route path="/chat/:conversationId" element={<ChatPage />} />
          <Route path="/documents" element={<DocumentsPage />} />
          <Route path="/documents/:documentId" element={<DocumentDetailPage />} />
          <Route path="/workflows" element={<WorkflowsPage />} />
          <Route path="/settings" element={<SettingsPage />} />
        </Route>
      </Routes>
    </Suspense>
  );
}
```

### Protected Routes

All routes are wrapped with `AuthGuard` for authentication:

```javascript
function AuthGuard({ children }) {
  const { isAuthenticated, loading } = useAuthStore();

  if (loading) return <Loader />;
  if (!isAuthenticated) return <Navigate to="/login" />;

  return children;
}
```

### URL Parameters

Workspace context is passed via URL search params:

```
/documents?project=1&workspace=2
```

`LayoutFrame` automatically reads and initializes store state from URL:

```javascript
const [searchParams] = useSearchParams();
const projectId = searchParams.get('project');
const workspaceId = searchParams.get('workspace');

useEffect(() => {
  initializeFromUrl(projectId, workspaceId);
}, [projectId, workspaceId]);
```

## Key Pages

### DashboardPage

Overview of recent activity and quick access:

- Recent conversations
- Recent documents
- Workspace statistics

### ChatPage

AI-powered chat interface:

- Conversation list sidebar
- Message history
- Diagram preview integration
- Real-time message streaming (planned)

### DocumentsPage

Document management:

- Folder tree navigation
- Document list with filtering
- Bulk actions

### CanvasPage

D2 diagram editor and playground:

- Live D2 code editor
- Real-time diagram preview
- Export options

### WorkflowsPage

Workflow discovery and execution (UI planned):

- Available workflow list
- Workflow details view
- Run workflow interface

## Styling

The application uses a shadcn.io-based theme system with OKLCH color space. See [Theme System](../development/theme-system.md) for complete documentation.

### Quick Reference

```jsx
// Content areas
<div className="bg-background text-foreground">
  <div className="bg-card border border-border rounded-lg p-4">
    <h2 className="text-foreground">Title</h2>
    <p className="text-muted-foreground">Secondary text</p>
    <button className="bg-primary text-primary-foreground">Action</button>
  </div>
</div>

// Sidebar/navigation areas
<nav className="bg-sidebar text-sidebar-foreground border-r border-sidebar-border">
  <button className="hover:bg-sidebar-accent">Item</button>
  <button className="bg-sidebar-primary text-sidebar-primary-foreground">Active</button>
</nav>
```

### Dark Mode

Dark mode uses the `.dark` class on `<html>`, managed by `themeStore`:

```javascript
import { useThemeStore } from '../stores/themeStore';

function ModeToggle() {
  const { mode, setMode } = useThemeStore();
  return (
    <button onClick={() => setMode(mode === 'dark' ? 'light' : 'dark')}>
      Toggle Mode
    </button>
  );
}
```

### Available Themes

11 themes available: `amber-minimal`, `claude` (default), `corporate`, `modern-minimal`, `nature`, `slack`, `twitter`, `cyberpunk`, `red`, `summer`, `notebook`

## API Communication

### API Client

Centralized Axios client in `services/api.js`:

```javascript
import axios from 'axios';

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || 'http://localhost:8000',
  withCredentials: true,
});

// Request interceptor for auth
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

export default api;
```

### API Methods

```javascript
// Documents
export const getDocuments = (params) => api.get('/api/documents/', { params });
export const createDocument = (data) => api.post('/api/documents/', data);

// Conversations
export const getConversations = (params) => api.get('/api/conversations/', { params });
export const sendMessage = (conversationId, message) =>
  api.post(`/api/conversations/${conversationId}/messages/`, { message });
```

## Testing

### E2E Tests with Playwright

```
frontend/tests/
├── pages/                    # Page Object Models
│   ├── BasePage.js
│   ├── DashboardPage.js
│   ├── ChatPage.js
│   └── DocumentsPage.js
└── e2e/
    ├── auth/
    │   └── login.spec.js
    ├── chat/
    │   └── messaging.spec.js
    └── documents/
        └── crud.spec.js
```

**Example Test:**

```javascript
import { test, expect } from '@playwright/test';
import { ChatPage } from '../../pages/ChatPage';

test('user can send a message', async ({ page }) => {
  const chatPage = new ChatPage(page);

  await chatPage.goto();
  await chatPage.sendMessage('Hello, AI!');

  await expect(chatPage.lastMessage).toContainText('Hello, AI!');
});
```

**Running Tests:**

```bash
# Headless
mise run test-e2e

# With UI
mise run test-e2e-ui

# Specific test
cd frontend && npm run test:e2e -- tests/e2e/chat/messaging.spec.js
```

## React StrictMode Patterns

!!! danger "Critical: Avoid Infinite Loops"
    React StrictMode causes components to mount twice in development.

**Safe Data Loading Pattern:**

```javascript
function MyComponent() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      const result = await api.getData();
      if (!cancelled) {
        setData(result);
        setLoading(false);
      }
    }

    load();

    return () => {
      cancelled = true;
    };
  }, []); // Empty dependency array

  if (loading) return <Spinner />;
  return <DataView data={data} />;
}
```

See `docs/react-strictmode-patterns.md` for comprehensive patterns.

## Related Documentation

- [Backend Architecture](backend.md) - API endpoints and services
- [Theme System](../development/theme-system.md) - Color themes and styling
- [React Patterns](../development/react-patterns.md) - StrictMode safe patterns
- [Testing Guide](../development/testing.md) - E2E test patterns
- [Configuration](../reference/configuration.md) - Environment variables
