// Utility functions
export { cn } from './lib/utils'
export { copyTextToClipboard } from './lib/clipboard'

// Phase 1 - Foundation components
export { AICodeBlock } from './components/ai/AICodeBlock'
export { AIActions, AIActionButton } from './components/ai/AIActions'
export { AILoader, AILoaderDots, AILoaderPulse, AILoaderSpinner, AILoaderText } from './components/ai/AILoader'

// Phase 2 - Core conversation components
export {
  AIConversation,
  AIConversationMessages,
  AIConversationEmpty,
  useAIConversation,
} from './components/ai/AIConversation'

export {
  AIMessage,
  AIMessageAvatar,
  AIMessageContent,
  AIMessageActions,
  AIMessageTimestamp,
  useAIMessage,
} from './components/ai/AIMessage'

export {
  AIPromptInput,
  AIPromptInputTextarea,
  AIPromptInputFooter,
  AIPromptInputTools,
  AIPromptInputButton,
  AIPromptInputSubmit,
  useAIPromptInput,
} from './components/ai/AIPromptInput'

export { AIResponse, parseIncompleteMarkdown } from './components/ai/AIResponse'

export { AIToolArtifacts, AIToolArtifactItem } from './components/ai/AIToolArtifacts'

export { AIMessageAttachments, ImagePreviewModal } from './components/ai/AIMessageAttachments'
