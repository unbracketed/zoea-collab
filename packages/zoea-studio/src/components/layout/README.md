# Layout Components Scaffold

This directory holds the new Slack-inspired layout system.

- `app/`: AppContainer, AppHeader (with manual ProjectsBar toggle), ProjectsBar, NavigationBar.
- `sidebar/`: Sidebar shell plus collapsible sections for Project Workspaces, Context Clipboard, and optional view-specific sections.
- `view/`: ViewContainer, ViewHeader (80px min height alignment with sidebar header), and view-type wrappers (FullContentView, ContentCenteredView, TwoPaneView).

Notes:
- Follow `docs/react-strictmode-patterns.md` for all data loading and effect usage; components must be StrictMode-safe.
- Preserve 80px alignment between SidebarHeader and ViewHeader.
- ProjectsBar collapse is manual-only; avoid auto-collapse for responsive breakpoints.
- Shared layout state (ProjectsBar open/closed, sidebar section collapse) lives in `useLayoutStore` (`frontend/src/stores/layoutStore.js`, exported via `stores/index.js`).
- Core primitives implemented: AppContainer, AppHeader (search + theme toggle + ProjectsBar toggle), ProjectsBar, NavigationBar (64px), Sidebar with required collapsible sections, ViewContainer, and ViewHeader. View wrappers (FullContentView, ContentCenteredView, TwoPaneView) accept optional `sidebar` content via ViewSidebarProvider and `safeAreaBottom` for floating controls (e.g., Chat input).
