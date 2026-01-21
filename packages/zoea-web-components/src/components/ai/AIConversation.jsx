/**
 * AIConversation Component
 *
 * Container for AI chat conversations with automatic scroll-to-bottom behavior,
 * floating scroll button, and keyboard navigation support.
 *
 * Based on shadcn.io/ai conversation component pattern.
 * Uses the `use-stick-to-bottom` library for scroll management.
 */

import * as React from 'react'
import { useCallback, useEffect } from 'react'
import { useStickToBottom } from 'use-stick-to-bottom'
import { ArrowDown } from 'lucide-react'
import { cn } from '../../lib/utils'

const AIConversationContext = React.createContext({
  isAtBottom: true,
  scrollToBottom: () => {},
  getScrollPosition: () => 0,
  setScrollPosition: () => {},
})

const useAIConversation = () => {
  const context = React.useContext(AIConversationContext)
  if (!context) {
    throw new Error('useAIConversation must be used within AIConversation')
  }
  return context
}

const AIConversation = React.forwardRef(
  (
    {
      children,
      className,
      showScrollButton = true,
      scrollButtonThreshold = 100,
      onScrollChange,
      ...props
    },
    ref
  ) => {
    const {
      scrollRef,
      contentRef,
      isAtBottom,
      scrollToBottom,
    } = useStickToBottom({
      initial: 'smooth',
      resize: 'smooth',
    })

    // Notify parent of scroll state changes
    useEffect(() => {
      onScrollChange?.(isAtBottom)
    }, [isAtBottom, onScrollChange])

    // Keyboard navigation
    const handleKeyDown = useCallback(
      (e) => {
        const container = scrollRef.current
        if (!container) return

        switch (e.key) {
          case 'End':
            e.preventDefault()
            scrollToBottom('smooth')
            break
          case 'Home':
            e.preventDefault()
            container.scrollTo({ top: 0, behavior: 'smooth' })
            break
          case 'PageDown':
            e.preventDefault()
            container.scrollBy({ top: container.clientHeight * 0.8, behavior: 'smooth' })
            break
          case 'PageUp':
            e.preventDefault()
            container.scrollBy({ top: -container.clientHeight * 0.8, behavior: 'smooth' })
            break
        }
      },
      [scrollRef, scrollToBottom]
    )

    const getScrollPosition = useCallback(() => {
      return scrollRef.current?.scrollTop ?? 0
    }, [scrollRef])

    const setScrollPosition = useCallback((position, behavior = 'auto') => {
      if (scrollRef.current) {
        scrollRef.current.scrollTo({ top: position, behavior })
      }
    }, [scrollRef])

    const contextValue = React.useMemo(
      () => ({
        isAtBottom,
        scrollToBottom: () => scrollToBottom('smooth'),
        getScrollPosition,
        setScrollPosition,
      }),
      [isAtBottom, scrollToBottom, getScrollPosition, setScrollPosition]
    )

    return (
      <AIConversationContext.Provider value={contextValue}>
        <div
          ref={ref}
          className={cn('relative flex flex-col h-full', className)}
          onKeyDown={handleKeyDown}
          tabIndex={0}
          role="log"
          aria-label="Conversation"
          aria-live="polite"
          {...props}
        >
          {/* Scrollable container */}
          <div
            ref={scrollRef}
            className="flex-1 overflow-y-auto overflow-x-hidden scroll-smooth"
          >
            <div ref={contentRef} className="min-h-full">
              {children}
            </div>
          </div>

          {/* Floating scroll-to-bottom button */}
          {showScrollButton && !isAtBottom && (
            <button
              type="button"
              onClick={() => scrollToBottom('smooth')}
              className={cn(
                'absolute bottom-4 left-1/2 -translate-x-1/2 z-10',
                'flex items-center gap-2 px-3 py-2 rounded-full',
                'bg-card border border-border shadow-lg',
                'text-sm text-muted-foreground hover:text-foreground',
                'transition-all hover:shadow-xl',
                'focus:outline-none focus:ring-2 focus:ring-ring'
              )}
              aria-label="Scroll to bottom"
            >
              <ArrowDown className="h-4 w-4" />
              <span>New messages</span>
            </button>
          )}
        </div>
      </AIConversationContext.Provider>
    )
  }
)
AIConversation.displayName = 'AIConversation'

/**
 * Wrapper for conversation messages list
 */
const AIConversationMessages = React.forwardRef(
  ({ children, className, ...props }, ref) => {
    return (
      <div
        ref={ref}
        className={cn('flex flex-col gap-4 p-4', className)}
        {...props}
      >
        {children}
      </div>
    )
  }
)
AIConversationMessages.displayName = 'AIConversationMessages'

/**
 * Empty state component for when there are no messages
 */
const AIConversationEmpty = React.forwardRef(
  ({ children, className, ...props }, ref) => {
    return (
      <div
        ref={ref}
        className={cn(
          'flex flex-col items-center justify-center h-full p-8 text-center',
          className
        )}
        {...props}
      >
        {children}
      </div>
    )
  }
)
AIConversationEmpty.displayName = 'AIConversationEmpty'

export {
  AIConversation,
  AIConversationMessages,
  AIConversationEmpty,
  useAIConversation,
}
