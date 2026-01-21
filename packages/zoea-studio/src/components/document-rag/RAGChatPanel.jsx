/**
 * RAG Chat Panel
 *
 * Chat interface with message history and input for RAG sessions.
 */

import { useState, useRef, useEffect } from 'react';
import { Send, Loader2, FileText } from 'lucide-react';
import { useRAGStore } from '../../stores/ragStore';
import RAGMessageBubble from './RAGMessageBubble';

export default function RAGChatPanel() {
  const [input, setInput] = useState('');
  const messagesEndRef = useRef(null);
  const inputRef = useRef(null);

  const { messages, isStreaming, error, sendMessage } = useRAGStore();

  // Auto-scroll to bottom on new messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Focus input on mount
  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  const handleSubmit = async (e) => {
    e?.preventDefault();
    if (!input.trim() || isStreaming) return;

    const message = input.trim();
    setInput('');

    try {
      await sendMessage(message);
    } catch (err) {
      console.error('Failed to send message:', err);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  return (
    <div className="flex flex-col h-full">
      {/* Messages area */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.length === 0 ? (
          <div className="text-center text-text-secondary py-12">
            <FileText className="h-12 w-12 mx-auto mb-4 opacity-50" />
            <p className="font-medium">Ask questions about your documents</p>
            <p className="text-sm mt-2">
              The AI will search through the content and provide relevant answers with sources.
            </p>
          </div>
        ) : (
          messages.map((message) => (
            <RAGMessageBubble key={message.id} message={message} />
          ))
        )}

        {isStreaming && (
          <div className="flex items-center gap-2 text-text-secondary text-sm">
            <Loader2 className="h-4 w-4 animate-spin" />
            <span>Searching documents...</span>
          </div>
        )}

        {error && !isStreaming && (
          <div className="p-3 bg-red-50 text-red-700 rounded-lg text-sm">
            {error}
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input area */}
      <div className="border-t border-border p-4">
        <form onSubmit={handleSubmit} className="flex gap-2">
          <textarea
            ref={inputRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask a question about your documents..."
            className="flex-1 px-4 py-2 rounded-lg border border-border bg-background resize-none focus:outline-none focus:ring-2 focus:ring-primary text-sm"
            rows={2}
            disabled={isStreaming}
          />
          <button
            type="submit"
            disabled={!input.trim() || isStreaming}
            className="px-4 py-2 bg-primary text-white rounded-lg hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed self-end"
            aria-label="Send message"
          >
            {isStreaming ? (
              <Loader2 className="h-5 w-5 animate-spin" />
            ) : (
              <Send className="h-5 w-5" />
            )}
          </button>
        </form>
        <p className="text-xs text-text-secondary mt-2">
          Press Enter to send, Shift+Enter for new line
        </p>
      </div>
    </div>
  );
}
