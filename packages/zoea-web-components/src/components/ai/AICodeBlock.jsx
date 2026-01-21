/**
 * AICodeBlock Component
 *
 * A styled code block for AI chat interfaces with syntax highlighting,
 * copy-to-clipboard functionality, and language detection.
 *
 * Based on shadcn.io/ai code-block component pattern.
 */

import * as React from 'react'
import { useState, useCallback } from 'react'
import { Check, Copy, ChevronDown, ChevronUp } from 'lucide-react'
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter'
import { oneDark } from 'react-syntax-highlighter/dist/esm/styles/prism'
import { cn } from '../../lib/utils'

const AICodeBlock = React.forwardRef(
  (
    {
      children,
      language = 'text',
      filename,
      showLineNumbers = false,
      collapsible = false,
      defaultCollapsed = false,
      className,
      ...props
    },
    ref
  ) => {
    const [copied, setCopied] = useState(false)
    const [collapsed, setCollapsed] = useState(defaultCollapsed)

    // Normalize code content
    const code = typeof children === 'string' ? children.replace(/\n$/, '') : String(children || '')

    const handleCopy = useCallback(async () => {
      try {
        await navigator.clipboard.writeText(code)
        setCopied(true)
        setTimeout(() => setCopied(false), 2000)
      } catch (err) {
        console.error('Failed to copy code:', err)
      }
    }, [code])

    const toggleCollapse = useCallback(() => {
      setCollapsed((prev) => !prev)
    }, [])

    return (
      <div
        ref={ref}
        className={cn(
          'group relative my-4 overflow-hidden rounded-lg border border-border bg-muted/50',
          className
        )}
        {...props}
      >
        {/* Header with language/filename and actions */}
        <div className="flex items-center justify-between border-b border-border bg-muted px-4 py-2 text-xs text-muted-foreground">
          <div className="flex items-center gap-2">
            {filename ? (
              <span className="font-medium text-foreground">{filename}</span>
            ) : (
              <span className="uppercase">{language}</span>
            )}
          </div>
          <div className="flex items-center gap-1">
            {collapsible && (
              <button
                type="button"
                onClick={toggleCollapse}
                className="rounded p-1 hover:bg-background/80 transition-colors"
                aria-label={collapsed ? 'Expand code' : 'Collapse code'}
              >
                {collapsed ? (
                  <ChevronDown className="h-4 w-4" />
                ) : (
                  <ChevronUp className="h-4 w-4" />
                )}
              </button>
            )}
            <button
              type="button"
              onClick={handleCopy}
              className="rounded p-1 hover:bg-background/80 transition-colors"
              aria-label={copied ? 'Copied!' : 'Copy code'}
            >
              {copied ? (
                <Check className="h-4 w-4 text-green-500" />
              ) : (
                <Copy className="h-4 w-4" />
              )}
            </button>
          </div>
        </div>

        {/* Code content */}
        {!collapsed && (
          <div className="overflow-x-auto">
            <SyntaxHighlighter
              style={oneDark}
              language={language}
              showLineNumbers={showLineNumbers}
              PreTag="div"
              customStyle={{
                margin: 0,
                padding: '1rem',
                background: 'transparent',
                fontSize: '0.875rem',
              }}
              codeTagProps={{
                style: {
                  fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace',
                },
              }}
            >
              {code}
            </SyntaxHighlighter>
          </div>
        )}

        {collapsed && (
          <div className="px-4 py-3 text-xs text-muted-foreground italic">
            Code collapsed ({code.split('\n').length} lines)
          </div>
        )}
      </div>
    )
  }
)
AICodeBlock.displayName = 'AICodeBlock'

export { AICodeBlock }
