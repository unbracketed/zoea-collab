/**
 * AILoader Component
 *
 * Loading indicators for AI chat interfaces: typing dots, pulse, spinner, etc.
 * Based on shadcn.io/ai loader component pattern.
 */

import * as React from 'react'
import { cn } from '../../lib/utils'

/**
 * Animated typing dots (three bouncing dots)
 */
const AILoaderDots = React.forwardRef(({ className, ...props }, ref) => {
  return (
    <div
      ref={ref}
      className={cn('flex items-center gap-1', className)}
      role="status"
      aria-label="Loading"
      {...props}
    >
      <span className="sr-only">Loading...</span>
      {[0, 1, 2].map((i) => (
        <span
          key={i}
          className={cn(
            'h-2 w-2 rounded-full bg-muted-foreground/60',
            'animate-bounce'
          )}
          style={{
            animationDelay: `${i * 150}ms`,
            animationDuration: '600ms',
          }}
        />
      ))}
    </div>
  )
})
AILoaderDots.displayName = 'AILoaderDots'

/**
 * Pulsing dot indicator
 */
const AILoaderPulse = React.forwardRef(({ className, ...props }, ref) => {
  return (
    <div
      ref={ref}
      className={cn('flex items-center gap-2', className)}
      role="status"
      aria-label="Loading"
      {...props}
    >
      <span className="sr-only">Loading...</span>
      <span className="relative flex h-3 w-3">
        <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-primary/50" />
        <span className="relative inline-flex h-3 w-3 rounded-full bg-primary" />
      </span>
    </div>
  )
})
AILoaderPulse.displayName = 'AILoaderPulse'

/**
 * Spinning circle loader
 */
const AILoaderSpinner = React.forwardRef(({ className, size = 'default', ...props }, ref) => {
  const sizeClasses = {
    sm: 'h-4 w-4',
    default: 'h-5 w-5',
    lg: 'h-6 w-6',
  }

  return (
    <div
      ref={ref}
      className={cn('flex items-center', className)}
      role="status"
      aria-label="Loading"
      {...props}
    >
      <span className="sr-only">Loading...</span>
      <svg
        className={cn('animate-spin text-muted-foreground', sizeClasses[size])}
        xmlns="http://www.w3.org/2000/svg"
        fill="none"
        viewBox="0 0 24 24"
      >
        <circle
          className="opacity-25"
          cx="12"
          cy="12"
          r="10"
          stroke="currentColor"
          strokeWidth="4"
        />
        <path
          className="opacity-75"
          fill="currentColor"
          d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
        />
      </svg>
    </div>
  )
})
AILoaderSpinner.displayName = 'AILoaderSpinner'

/**
 * Text with animated ellipsis
 */
const AILoaderText = React.forwardRef(
  ({ text = 'Thinking', className, ...props }, ref) => {
    return (
      <div
        ref={ref}
        className={cn('flex items-center text-muted-foreground text-sm', className)}
        role="status"
        aria-label="Loading"
        {...props}
      >
        <span>{text}</span>
        <span className="inline-flex w-6 overflow-hidden">
          <span className="animate-ellipsis">...</span>
        </span>
      </div>
    )
  }
)
AILoaderText.displayName = 'AILoaderText'

/**
 * Combined loader with optional text
 */
const AILoader = React.forwardRef(
  ({ variant = 'dots', text, className, ...props }, ref) => {
    const LoaderComponent = {
      dots: AILoaderDots,
      pulse: AILoaderPulse,
      spinner: AILoaderSpinner,
      text: AILoaderText,
    }[variant]

    if (variant === 'text') {
      return <AILoaderText ref={ref} text={text} className={className} {...props} />
    }

    return (
      <div ref={ref} className={cn('flex items-center gap-2', className)} {...props}>
        <LoaderComponent />
        {text && <span className="text-sm text-muted-foreground">{text}</span>}
      </div>
    )
  }
)
AILoader.displayName = 'AILoader'

export { AILoader, AILoaderDots, AILoaderPulse, AILoaderSpinner, AILoaderText }
