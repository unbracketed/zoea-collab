/**
 * AIPromptInput Component
 *
 * Auto-resizing prompt input with submit button and toolbar support.
 * Based on shadcn.io/ai prompt-input component pattern.
 */

import * as React from 'react'
import { useState, useCallback, useRef, useEffect } from 'react'
import { Send, Loader2 } from 'lucide-react'
import { cva } from 'class-variance-authority'
import { cn } from '../../lib/utils'

const AIPromptInputContext = React.createContext({
  value: '',
  setValue: () => {},
  isSubmitting: false,
  disabled: false,
})

const useAIPromptInput = () => {
  return React.useContext(AIPromptInputContext)
}

/**
 * Main form container for the prompt input
 */
const AIPromptInput = React.forwardRef(
  (
    {
      children,
      value: controlledValue,
      defaultValue = '',
      onValueChange,
      onSubmit,
      isSubmitting = false,
      disabled = false,
      className,
      ...props
    },
    ref
  ) => {
    const [internalValue, setInternalValue] = useState(defaultValue)
    const isControlled = controlledValue !== undefined
    const value = isControlled ? controlledValue : internalValue

    const setValue = useCallback(
      (newValue) => {
        if (!isControlled) {
          setInternalValue(newValue)
        }
        onValueChange?.(newValue)
      },
      [isControlled, onValueChange]
    )

    const handleSubmit = useCallback(
      (e) => {
        e.preventDefault()
        if (!value.trim() || isSubmitting || disabled) return
        onSubmit?.(value)
      },
      [value, isSubmitting, disabled, onSubmit]
    )

    const contextValue = React.useMemo(
      () => ({
        value,
        setValue,
        isSubmitting,
        disabled,
      }),
      [value, setValue, isSubmitting, disabled]
    )

    return (
      <AIPromptInputContext.Provider value={contextValue}>
        <form
          ref={ref}
          onSubmit={handleSubmit}
          className={cn(
            'relative flex flex-col gap-2 rounded-xl border border-border bg-card p-2',
            'focus-within:ring-2 focus-within:ring-ring focus-within:ring-offset-1',
            'shadow-sm',
            disabled && 'opacity-50 pointer-events-none',
            className
          )}
          {...props}
        >
          {children}
        </form>
      </AIPromptInputContext.Provider>
    )
  }
)
AIPromptInput.displayName = 'AIPromptInput'

/**
 * Auto-resizing textarea for prompt input
 */
const AIPromptInputTextarea = React.forwardRef(
  (
    {
      placeholder = 'Type a message...',
      minRows = 1,
      maxRows = 6,
      onKeyDown,
      className,
      ...props
    },
    ref
  ) => {
    const { value, setValue, isSubmitting, disabled } = useAIPromptInput()
    const textareaRef = useRef(null)
    const combinedRef = useCombinedRef(ref, textareaRef)

    // Auto-resize textarea
    useEffect(() => {
      const textarea = textareaRef.current
      if (!textarea) return

      // Reset height to auto to get the correct scrollHeight
      textarea.style.height = 'auto'

      // Calculate min and max heights
      const lineHeight = parseInt(getComputedStyle(textarea).lineHeight) || 24
      const minHeight = lineHeight * minRows
      const maxHeight = lineHeight * maxRows

      // Set new height
      const newHeight = Math.min(Math.max(textarea.scrollHeight, minHeight), maxHeight)
      textarea.style.height = `${newHeight}px`
    }, [value, minRows, maxRows])

    const handleKeyDown = useCallback(
      (e) => {
        // Submit on Enter (without shift)
        if (e.key === 'Enter' && !e.shiftKey) {
          e.preventDefault()
          e.currentTarget.form?.requestSubmit()
        }
        onKeyDown?.(e)
      },
      [onKeyDown]
    )

    return (
      <textarea
        ref={combinedRef}
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder={placeholder}
        disabled={isSubmitting || disabled}
        rows={minRows}
        className={cn(
          'w-full resize-none bg-transparent px-2 py-1.5',
          'text-sm text-foreground placeholder:text-muted-foreground',
          'focus:outline-none',
          'disabled:cursor-not-allowed disabled:opacity-50',
          className
        )}
        aria-label="Message input"
        {...props}
      />
    )
  }
)
AIPromptInputTextarea.displayName = 'AIPromptInputTextarea'

/**
 * Footer area containing toolbar and submit button
 */
const AIPromptInputFooter = React.forwardRef(
  ({ children, className, ...props }, ref) => {
    return (
      <div
        ref={ref}
        className={cn('flex items-center justify-between gap-2', className)}
        {...props}
      >
        {children}
      </div>
    )
  }
)
AIPromptInputFooter.displayName = 'AIPromptInputFooter'

/**
 * Container for toolbar action buttons
 */
const AIPromptInputTools = React.forwardRef(
  ({ children, className, ...props }, ref) => {
    return (
      <div
        ref={ref}
        className={cn('flex items-center gap-1', className)}
        {...props}
      >
        {children}
      </div>
    )
  }
)
AIPromptInputTools.displayName = 'AIPromptInputTools'

const toolButtonVariants = cva(
  'inline-flex items-center justify-center rounded-md text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:pointer-events-none disabled:opacity-50',
  {
    variants: {
      variant: {
        default: 'bg-transparent text-muted-foreground hover:text-foreground hover:bg-muted',
        primary: 'bg-primary text-primary-foreground hover:bg-primary/90',
      },
      size: {
        default: 'h-8 px-3',
        sm: 'h-7 px-2 text-xs',
        icon: 'h-8 w-8',
      },
    },
    defaultVariants: {
      variant: 'default',
      size: 'default',
    },
  }
)

/**
 * Toolbar action button
 */
const AIPromptInputButton = React.forwardRef(
  ({ children, variant, size, className, ...props }, ref) => {
    const { isSubmitting, disabled } = useAIPromptInput()

    return (
      <button
        ref={ref}
        type="button"
        disabled={isSubmitting || disabled}
        className={cn(toolButtonVariants({ variant, size }), className)}
        {...props}
      >
        {children}
      </button>
    )
  }
)
AIPromptInputButton.displayName = 'AIPromptInputButton'

/**
 * Submit button with loading state
 */
const AIPromptInputSubmit = React.forwardRef(
  ({ children, className, ...props }, ref) => {
    const { value, isSubmitting, disabled } = useAIPromptInput()
    const canSubmit = value.trim().length > 0 && !isSubmitting && !disabled

    return (
      <button
        ref={ref}
        type="submit"
        disabled={!canSubmit}
        className={cn(
          'inline-flex items-center justify-center rounded-lg px-3 py-1.5',
          'bg-primary text-primary-foreground',
          'text-sm font-medium',
          'transition-colors hover:bg-primary/90',
          'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
          'disabled:pointer-events-none disabled:opacity-50',
          className
        )}
        {...props}
      >
        {isSubmitting ? (
          <Loader2 className="h-4 w-4 animate-spin" />
        ) : (
          children || (
            <>
              <Send className="h-4 w-4" />
              <span className="sr-only">Send message</span>
            </>
          )
        )}
      </button>
    )
  }
)
AIPromptInputSubmit.displayName = 'AIPromptInputSubmit'

// Helper hook to combine refs
function useCombinedRef(...refs) {
  return useCallback(
    (element) => {
      refs.forEach((ref) => {
        if (typeof ref === 'function') {
          ref(element)
        } else if (ref) {
          ref.current = element
        }
      })
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    refs
  )
}

export {
  AIPromptInput,
  AIPromptInputTextarea,
  AIPromptInputFooter,
  AIPromptInputTools,
  AIPromptInputButton,
  AIPromptInputSubmit,
  useAIPromptInput,
}
