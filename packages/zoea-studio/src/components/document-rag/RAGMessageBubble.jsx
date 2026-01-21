/**
 * RAG Message Bubble
 *
 * Individual message display with source citations for assistant messages.
 */

import { useState } from 'react';
import { User, Bot, FileText, ChevronDown, ChevronUp } from 'lucide-react';

export default function RAGMessageBubble({ message }) {
  const [showSources, setShowSources] = useState(false);
  const isUser = message.role === 'user';
  const hasSources = message.sources && message.sources.length > 0;

  return (
    <div
      className={`flex gap-3 ${isUser ? 'flex-row-reverse' : 'flex-row'}`}
    >
      {/* Avatar */}
      <div
        className={`flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center ${
          isUser ? 'bg-primary text-white' : 'bg-gray-200 text-gray-600'
        }`}
      >
        {isUser ? <User className="h-4 w-4" /> : <Bot className="h-4 w-4" />}
      </div>

      {/* Message content */}
      <div
        className={`flex-1 max-w-[80%] ${isUser ? 'text-right' : 'text-left'}`}
      >
        <div
          className={`inline-block rounded-lg px-4 py-2 text-sm ${
            isUser
              ? 'bg-primary text-white'
              : 'bg-background text-text border border-border'
          }`}
        >
          <div className="whitespace-pre-wrap">{message.content}</div>
        </div>

        {/* Sources toggle for assistant messages */}
        {!isUser && hasSources && (
          <div className="mt-2">
            <button
              onClick={() => setShowSources(!showSources)}
              className="flex items-center gap-1 text-xs text-text-secondary hover:text-text"
            >
              <FileText className="h-3 w-3" />
              <span>{message.sources.length} sources</span>
              {showSources ? (
                <ChevronUp className="h-3 w-3" />
              ) : (
                <ChevronDown className="h-3 w-3" />
              )}
            </button>

            {showSources && (
              <div className="mt-2 space-y-2">
                {message.sources.map((source, idx) => (
                  <div
                    key={idx}
                    className="p-2 bg-gray-50 rounded text-xs text-left"
                  >
                    <div className="font-medium text-text">
                      {source.title || source.document_name || `Source ${idx + 1}`}
                    </div>
                    {source.excerpt && (
                      <div className="mt-1 text-text-secondary line-clamp-2">
                        {source.excerpt}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Timestamp */}
        <div
          className={`text-xs text-text-secondary mt-1 ${
            isUser ? 'text-right' : 'text-left'
          }`}
        >
          {new Date(message.timestamp).toLocaleTimeString([], {
            hour: '2-digit',
            minute: '2-digit',
          })}
        </div>
      </div>
    </div>
  );
}
