/**
 * AIResponse Component
 *
 * Streaming-optimized markdown renderer for AI responses.
 * Wraps ReactMarkdown with enhanced styling and code block support.
 *
 * Based on shadcn.io/ai response component pattern.
 */

import * as React from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { cn } from '../../lib/utils'
import { AICodeBlock } from './AICodeBlock'

/**
 * Parse incomplete markdown for streaming support
 * Auto-completes unclosed formatting like bold, italic, code blocks
 */
function parseIncompleteMarkdown(content) {
  if (!content) return ''

  let result = content

  // Auto-close unclosed code blocks
  const codeBlockMatches = result.match(/```/g)
  if (codeBlockMatches && codeBlockMatches.length % 2 !== 0) {
    result += '\n```'
  }

  // Auto-close unclosed inline code
  const inlineCodeMatches = result.match(/(?<!`)`(?!`)/g)
  if (inlineCodeMatches && inlineCodeMatches.length % 2 !== 0) {
    result += '`'
  }

  // Auto-close unclosed bold
  const boldMatches = result.match(/\*\*/g)
  if (boldMatches && boldMatches.length % 2 !== 0) {
    result += '**'
  }

  // Auto-close unclosed italic (single asterisk, not part of bold)
  const italicMatches = result.match(/(?<!\*)\*(?!\*)/g)
  if (italicMatches && italicMatches.length % 2 !== 0) {
    result += '*'
  }

  return result
}

const AIResponse = React.forwardRef(
  (
    {
      children,
      content,
      streaming = false,
      allowedLinkPrefixes = ['https://', 'http://'],
      allowedImagePrefixes = ['https://', 'http://', '/'],
      className,
      components: customComponents,
      ...props
    },
    ref
  ) => {
    // Use children or content prop
    const rawContent = children || content || ''
    const processedContent = streaming
      ? parseIncompleteMarkdown(rawContent)
      : rawContent

    // URL validation helpers
    const isAllowedUrl = (url, prefixes) => {
      if (!url) return false
      return prefixes.some((prefix) => url.startsWith(prefix))
    }

    // Default markdown components with shadcn styling
    const defaultComponents = {
      // Code blocks with syntax highlighting
      code({ node, inline, className: codeClassName, children: codeChildren, ...codeProps }) {
        const languageMatch = (codeClassName || '').match(/language-(\w+)/)
        const language = languageMatch ? languageMatch[1] : ''

        if (!inline) {
          return (
            <AICodeBlock language={language || 'text'}>
              {String(codeChildren).replace(/\n$/, '')}
            </AICodeBlock>
          )
        }

        return (
          <code
            className={cn(
              'relative rounded bg-muted px-[0.3rem] py-[0.2rem] font-mono text-sm',
              codeClassName
            )}
            {...codeProps}
          >
            {codeChildren}
          </code>
        )
      },

      // Paragraphs
      p({ children: pChildren }) {
        return <p className="mb-4 last:mb-0 leading-relaxed">{pChildren}</p>
      },

      // Links with security check
      a({ href, children: linkChildren }) {
        if (!isAllowedUrl(href, allowedLinkPrefixes)) {
          return <span className="text-muted-foreground">{linkChildren}</span>
        }
        return (
          <a
            href={href}
            target="_blank"
            rel="noopener noreferrer"
            className="text-primary underline underline-offset-4 hover:text-primary/80 transition-colors"
          >
            {linkChildren}
          </a>
        )
      },

      // Images with security check
      img({ src, alt }) {
        if (!isAllowedUrl(src, allowedImagePrefixes)) {
          return <span className="text-muted-foreground">[Image: {alt}]</span>
        }
        return (
          <img
            src={src}
            alt={alt}
            className="max-w-full h-auto rounded-lg my-4"
            loading="lazy"
          />
        )
      },

      // Lists
      ul({ children: ulChildren }) {
        return <ul className="mb-4 list-disc pl-6 space-y-1">{ulChildren}</ul>
      },
      ol({ children: olChildren }) {
        return <ol className="mb-4 list-decimal pl-6 space-y-1">{olChildren}</ol>
      },
      li({ children: liChildren }) {
        return <li className="leading-relaxed">{liChildren}</li>
      },

      // Headings
      h1({ children: h1Children }) {
        return (
          <h1 className="text-2xl font-bold mt-6 mb-4 first:mt-0">
            {h1Children}
          </h1>
        )
      },
      h2({ children: h2Children }) {
        return (
          <h2 className="text-xl font-semibold mt-5 mb-3 first:mt-0">
            {h2Children}
          </h2>
        )
      },
      h3({ children: h3Children }) {
        return (
          <h3 className="text-lg font-semibold mt-4 mb-2 first:mt-0">
            {h3Children}
          </h3>
        )
      },
      h4({ children: h4Children }) {
        return (
          <h4 className="text-base font-semibold mt-4 mb-2 first:mt-0">
            {h4Children}
          </h4>
        )
      },

      // Blockquotes
      blockquote({ children: bqChildren }) {
        return (
          <blockquote className="border-l-4 border-primary/30 pl-4 my-4 text-muted-foreground italic">
            {bqChildren}
          </blockquote>
        )
      },

      // Tables
      table({ children: tableChildren }) {
        return (
          <div className="my-4 overflow-x-auto">
            <table className="w-full border-collapse text-sm">
              {tableChildren}
            </table>
          </div>
        )
      },
      thead({ children: theadChildren }) {
        return <thead className="bg-muted">{theadChildren}</thead>
      },
      th({ children: thChildren }) {
        return (
          <th className="border border-border px-3 py-2 text-left font-semibold">
            {thChildren}
          </th>
        )
      },
      td({ children: tdChildren }) {
        return (
          <td className="border border-border px-3 py-2">{tdChildren}</td>
        )
      },

      // Horizontal rule
      hr() {
        return <hr className="my-6 border-border" />
      },

      // Strong and emphasis
      strong({ children: strongChildren }) {
        return <strong className="font-semibold">{strongChildren}</strong>
      },
      em({ children: emChildren }) {
        return <em className="italic">{emChildren}</em>
      },

      // Strikethrough
      del({ children: delChildren }) {
        return <del className="line-through text-muted-foreground">{delChildren}</del>
      },

      // Task lists (GFM)
      input({ checked, ...inputProps }) {
        return (
          <input
            type="checkbox"
            checked={checked}
            disabled
            className="mr-2 h-4 w-4 rounded border-border"
            {...inputProps}
          />
        )
      },
    }

    // Merge custom components with defaults
    const mergedComponents = {
      ...defaultComponents,
      ...customComponents,
    }

    return (
      <div
        ref={ref}
        className={cn('prose prose-sm max-w-none dark:prose-invert', className)}
        {...props}
      >
        <ReactMarkdown
          remarkPlugins={[remarkGfm]}
          components={mergedComponents}
        >
          {processedContent}
        </ReactMarkdown>
      </div>
    )
  }
)
AIResponse.displayName = 'AIResponse'

export { AIResponse, parseIncompleteMarkdown }
