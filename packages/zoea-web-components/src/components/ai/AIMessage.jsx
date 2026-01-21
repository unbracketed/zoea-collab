/**
 * AIMessage Component
 *
 * Chat message bubbles with role-based styling and avatar support.
 * Based on shadcn.io/ai message component pattern.
 */

import * as React from 'react'
import * as Avatar from '@radix-ui/react-avatar'
import { cva } from 'class-variance-authority'
import { cn } from '../../lib/utils'

const messageVariants = cva('group relative flex gap-3 py-4', {
  variants: {
    from: {
      user: 'flex-row-reverse',
      assistant: 'flex-row',
      system: 'flex-row justify-center',
      error: 'flex-row',
    },
  },
  defaultVariants: {
    from: 'assistant',
  },
})

const bubbleVariants = cva(
  'relative rounded-2xl px-4 py-3 text-sm max-w-[85%] md:max-w-[75%]',
  {
    variants: {
      from: {
        user: 'bg-primary text-primary-foreground rounded-br-md',
        assistant: 'bg-muted text-foreground rounded-bl-md',
        system: 'bg-secondary/50 text-secondary-foreground text-center text-xs italic max-w-full',
        error: 'bg-destructive/10 text-destructive border border-destructive/20 rounded-bl-md',
      },
    },
    defaultVariants: {
      from: 'assistant',
    },
  }
)

const AIMessageContext = React.createContext({
  from: 'assistant',
})

const useAIMessage = () => {
  return React.useContext(AIMessageContext)
}

/**
 * Main message container with role-based layout
 */
const AIMessage = React.forwardRef(
  ({ children, from = 'assistant', className, ...props }, ref) => {
    return (
      <AIMessageContext.Provider value={{ from }}>
        <div
          ref={ref}
          className={cn(messageVariants({ from }), className)}
          role="article"
          aria-label={`${from} message`}
          {...props}
        >
          {children}
        </div>
      </AIMessageContext.Provider>
    )
  }
)
AIMessage.displayName = 'AIMessage'

/**
 * Message avatar component
 */
const AIMessageAvatar = React.forwardRef(
  ({ src, fallback, alt, className, ...props }, ref) => {
    const { from } = useAIMessage()

    // Default fallback based on role
    const defaultFallback = from === 'user' ? 'U' : from === 'assistant' ? 'AI' : 'S'

    return (
      <Avatar.Root
        ref={ref}
        className={cn(
          'relative flex h-8 w-8 shrink-0 overflow-hidden rounded-full',
          from === 'system' && 'hidden',
          className
        )}
        {...props}
      >
        <Avatar.Image
          className="aspect-square h-full w-full object-cover"
          src={src}
          alt={alt || `${from} avatar`}
        />
        <Avatar.Fallback
          className={cn(
            'flex h-full w-full items-center justify-center rounded-full text-xs font-medium',
            from === 'user'
              ? 'bg-primary text-primary-foreground'
              : 'bg-muted text-muted-foreground'
          )}
        >
          {fallback || defaultFallback}
        </Avatar.Fallback>
      </Avatar.Root>
    )
  }
)
AIMessageAvatar.displayName = 'AIMessageAvatar'

/**
 * Message content bubble
 */
const AIMessageContent = React.forwardRef(
  ({ children, className, ...props }, ref) => {
    const { from } = useAIMessage()

    return (
      <div ref={ref} className={cn(bubbleVariants({ from }), className)} {...props}>
        {children}
      </div>
    )
  }
)
AIMessageContent.displayName = 'AIMessageContent'

/**
 * Message actions container (shown on hover)
 */
const AIMessageActions = React.forwardRef(
  ({ children, className, ...props }, ref) => {
    const { from } = useAIMessage()

    return (
      <div
        ref={ref}
        className={cn(
          'absolute -bottom-2 opacity-0 group-hover:opacity-100 transition-opacity',
          from === 'user' ? 'right-0' : 'left-11',
          from === 'system' && 'hidden',
          className
        )}
        {...props}
      >
        {children}
      </div>
    )
  }
)
AIMessageActions.displayName = 'AIMessageActions'

/**
 * Timestamp component for messages
 */
const AIMessageTimestamp = React.forwardRef(
  ({ children, className, ...props }, ref) => {
    return (
      <span
        ref={ref}
        className={cn(
          'text-xs text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity',
          className
        )}
        {...props}
      >
        {children}
      </span>
    )
  }
)
AIMessageTimestamp.displayName = 'AIMessageTimestamp'

export {
  AIMessage,
  AIMessageAvatar,
  AIMessageContent,
  AIMessageActions,
  AIMessageTimestamp,
  useAIMessage,
}
