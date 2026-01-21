/**
 * AIActions Component
 *
 * Action buttons for AI chat messages (copy, regenerate, thumbs up/down, etc.).
 * Based on shadcn.io/ai actions component pattern.
 */

import * as React from 'react'
import { useState, useCallback } from 'react'
import { Check, Copy, RefreshCw, ThumbsUp, ThumbsDown, MoreHorizontal } from 'lucide-react'
import { cn } from '../../lib/utils'
import { copyTextToClipboard } from '../../lib/clipboard'

const AIActionButton = React.forwardRef(
  ({ children, className, tooltip, active, ...props }, ref) => {
    return (
      <button
        ref={ref}
        type="button"
        className={cn(
          'inline-flex items-center justify-center rounded p-1.5',
          'text-muted-foreground hover:text-foreground hover:bg-muted',
          'transition-colors focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-1',
          'disabled:pointer-events-none disabled:opacity-50',
          active && 'text-foreground bg-muted',
          className
        )}
        title={tooltip}
        {...props}
      >
        {children}
      </button>
    )
  }
)
AIActionButton.displayName = 'AIActionButton'

const AIActions = React.forwardRef(
  (
    {
      content,
      onCopy,
      onCopyError,
      onRegenerate,
      onFeedback,
      showCopy = true,
      showRegenerate = false,
      showFeedback = false,
      className,
      children,
      ...props
    },
    ref
  ) => {
    const [copied, setCopied] = useState(false)
    const [feedback, setFeedback] = useState(null) // 'up' | 'down' | null

    const handleCopy = useCallback(async () => {
      try {
        if (content !== undefined && content !== null) {
          await copyTextToClipboard(content)
        }
        setCopied(true)
        setTimeout(() => setCopied(false), 2000)
        onCopy?.()
      } catch (err) {
        console.error('Failed to copy:', err)
        onCopyError?.(err)
      }
    }, [content, onCopy, onCopyError])

    const handleFeedback = useCallback(
      (type) => {
        const newFeedback = feedback === type ? null : type
        setFeedback(newFeedback)
        onFeedback?.(newFeedback)
      },
      [feedback, onFeedback]
    )

    return (
      <div
        ref={ref}
        className={cn(
          'flex items-center gap-0.5 opacity-0 group-hover:opacity-100 transition-opacity',
          className
        )}
        {...props}
      >
        {showCopy && (
          <AIActionButton
            onClick={handleCopy}
            tooltip={copied ? 'Copied!' : 'Copy message'}
          >
            {copied ? (
              <Check className="h-4 w-4 text-green-500" />
            ) : (
              <Copy className="h-4 w-4" />
            )}
          </AIActionButton>
        )}

        {showRegenerate && (
          <AIActionButton
            onClick={onRegenerate}
            tooltip="Regenerate response"
          >
            <RefreshCw className="h-4 w-4" />
          </AIActionButton>
        )}

        {showFeedback && (
          <>
            <AIActionButton
              onClick={() => handleFeedback('up')}
              tooltip="Good response"
              active={feedback === 'up'}
            >
              <ThumbsUp className="h-4 w-4" />
            </AIActionButton>
            <AIActionButton
              onClick={() => handleFeedback('down')}
              tooltip="Bad response"
              active={feedback === 'down'}
            >
              <ThumbsDown className="h-4 w-4" />
            </AIActionButton>
          </>
        )}

        {children}
      </div>
    )
  }
)
AIActions.displayName = 'AIActions'

export { AIActions, AIActionButton }
