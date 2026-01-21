# zoea-studio

The React frontend application for Zoea Collab: Agent Cowork Toolkit.

## Overview

`zoea-studio` is a productivity suite frontend built with:

- **React 19** - UI framework
- **Vite** - Build tool
- **Zustand** - State management
- **React Router** - Navigation
- **Tailwind CSS** - Styling
- **@zoea/web-components** - AI chat components

## Installation

```bash
cd packages/zoea-studio
pnpm install
```

## Development

### Running the Development Server

```bash
pnpm dev
```

The app will be available at `http://localhost:5173`.

### Building for Production

```bash
pnpm build
```

### Running Tests

```bash
# Unit tests
pnpm test

# E2E tests
pnpm test:e2e
```

## Project Structure

```
zoea-studio/
├── src/
│   ├── components/       # React components
│   │   ├── layout/       # Layout components (LayoutFrame, etc.)
│   │   ├── documents/    # Document editors
│   │   ├── ui/           # Base UI components
│   │   └── ...
│   ├── pages/            # Route pages
│   ├── stores/           # Zustand stores
│   ├── services/         # API services
│   └── lib/              # Utilities
├── tests/                # Playwright E2E tests
└── public/               # Static assets
```

## Features

### Chat Interface

AI-powered chat with support for:
- Multiple conversations
- Tool artifacts (images, tables)
- File attachments
- Clipboard integration

### Document Management

Rich document editing with:
- Yoopta-based rich text editor
- Excalidraw whiteboard integration
- D2 diagram support
- PDF viewing

### Workflows

Visual workflow builder using React Flow.

## Configuration

Environment variables:

```env
VITE_API_BASE_URL=http://localhost:8000
```

## Styling

Uses Tailwind CSS with a custom theme. See `tailwind.config.js` for configuration.

## State Management

Zustand stores are located in `src/stores/`:

- `conversationStore` - Chat conversations
- `workspaceStore` - Active workspace
- `clipboardStore` - Clipboard items
- `documentStore` - Documents
- ... and more
