import ReactMarkdown from 'react-markdown';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { oneDark } from 'react-syntax-highlighter/dist/esm/styles/prism';
import remarkGfm from 'remark-gfm';

/**
 * MessageContent Component
 *
 * Renders message content with markdown formatting, including:
 * - Fenced code blocks with syntax highlighting
 * - Inline code formatting
 * - GitHub-flavored markdown (tables, task lists, strikethrough, etc.)
 * - Standard markdown (headings, lists, links, emphasis, etc.)
 */
function MessageContent({ content }) {
  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      components={{
        // Custom code block renderer with syntax highlighting
        code({ node, inline, className, children, ...props }) {
          // Extract language from className (e.g., "language-javascript")
          const languageMatch = (className || '').match(/language-(\w+)/);
          const language = languageMatch ? languageMatch[1] : '';

          return !inline ? (
            <SyntaxHighlighter
              style={oneDark}
              language={language || 'text'}
              PreTag="div"
              className="code-block"
              {...props}
            >
              {String(children).replace(/\n$/, '')}
            </SyntaxHighlighter>
          ) : (
            <code className={className} {...props}>
              {children}
            </code>
          );
        },
        // Ensure paragraphs don't add extra spacing
        p({ children }) {
          return <p className="mb-2">{children}</p>;
        },
        // Style links
        a({ href, children }) {
          return (
            <a href={href} target="_blank" rel="noopener noreferrer" className="text-primary hover:underline">
              {children}
            </a>
          );
        },
        // Style lists
        ul({ children }) {
          return <ul className="mb-2 list-disc pl-5">{children}</ul>;
        },
        ol({ children }) {
          return <ol className="mb-2 list-decimal pl-5">{children}</ol>;
        },
        // Style headings
        h1({ children }) {
          return <h1 className="text-lg font-bold mt-2 mb-2">{children}</h1>;
        },
        h2({ children }) {
          return <h2 className="text-base font-bold mt-2 mb-2">{children}</h2>;
        },
        h3({ children }) {
          return <h3 className="text-base font-semibold mt-2 mb-2">{children}</h3>;
        },
        // Style blockquotes
        blockquote({ children }) {
          return (
            <blockquote className="border-l-4 border-secondary pl-3 mb-2 text-text-secondary">
              {children}
            </blockquote>
          );
        },
        // Style tables
        table({ children }) {
          return <table className="w-full text-sm border border-border mb-2">{children}</table>;
        },
      }}
    >
      {content}
    </ReactMarkdown>
  );
}

export default MessageContent;
