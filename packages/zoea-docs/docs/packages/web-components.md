# @zoea/web-components

Reusable React AI/chat components for building conversational interfaces.

## Overview

`@zoea/web-components` provides a set of headless, composable React components for building AI chat interfaces. Components follow the shadcn/ui pattern - minimal styling, maximum flexibility.

## Installation

```bash
pnpm add @zoea/web-components
# or
npm install @zoea/web-components
```

## Components

### Conversation Components

- **AIConversation** - Container with auto-scroll and keyboard navigation
- **AIConversationMessages** - Wrapper for message list
- **AIConversationEmpty** - Empty state component

### Message Components

- **AIMessage** - Individual message container
- **AIMessageAvatar** - Avatar display
- **AIMessageContent** - Message content wrapper
- **AIMessageActions** - Action buttons container
- **AIMessageTimestamp** - Timestamp display

### Input Components

- **AIPromptInput** - Input container
- **AIPromptInputTextarea** - Auto-resizing textarea
- **AIPromptInputFooter** - Footer area for tools/actions
- **AIPromptInputSubmit** - Submit button

### Response Components

- **AIResponse** - Markdown renderer for AI responses
- **AICodeBlock** - Syntax-highlighted code blocks
- **AILoader** - Loading states (dots, pulse, spinner, text)

### Actions

- **AIActions** - Copy, regenerate, feedback buttons
- **AIActionButton** - Individual action button

### Artifacts

- **AIToolArtifacts** - Container for tool-generated content
- **AIMessageAttachments** - File attachment display

## Usage Example

```jsx
import {
  AIConversation,
  AIConversationMessages,
  AIMessage,
  AIMessageContent,
  AIResponse,
  AIPromptInput,
  AIPromptInputTextarea,
  AIPromptInputSubmit,
} from '@zoea/web-components';

function ChatInterface({ messages, onSend }) {
  return (
    <AIConversation className="h-screen">
      <AIConversationMessages>
        {messages.map((msg) => (
          <AIMessage key={msg.id} role={msg.role}>
            <AIMessageContent>
              <AIResponse>{msg.content}</AIResponse>
            </AIMessageContent>
          </AIMessage>
        ))}
      </AIConversationMessages>

      <AIPromptInput>
        <AIPromptInputTextarea
          placeholder="Type a message..."
          onSubmit={onSend}
        />
        <AIPromptInputSubmit />
      </AIPromptInput>
    </AIConversation>
  );
}
```

## Styling

Components use Tailwind CSS classes and CSS variables for theming. Import the base styles:

```js
import '@zoea/web-components/styles.css';
```

Or use your own Tailwind configuration with the provided class names.

## Hooks

- **useAIConversation** - Access scroll position and controls
- **useAIMessage** - Access message context
- **useAIPromptInput** - Access input state and handlers

## Utilities

- **cn** - Class name merger (clsx + tailwind-merge)
- **copyTextToClipboard** - Cross-browser clipboard helper
