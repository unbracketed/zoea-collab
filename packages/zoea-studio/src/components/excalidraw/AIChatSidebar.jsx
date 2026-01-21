/**
 * AI Chat Sidebar for Excalidraw
 *
 * Sidebar panel for AI chat interactions that can generate
 * canvas elements from natural language prompts.
 */

import { useState, useRef, useEffect } from 'react';
import { Sidebar } from '@excalidraw/excalidraw';
import { Send, Loader2, Sparkles, Trash2, Plus } from 'lucide-react';
import { convertAIResponseToElements, detectContentTypes } from './aiResponseConverter';
import { useWorkspaceStore } from '../../stores';
import api from '../../services/api';

export default function AIChatSidebar({ excalidrawAPI, onElementsGenerated }) {
  const [prompt, setPrompt] = useState('');
  const [messages, setMessages] = useState([]);
  const [isGenerating, setIsGenerating] = useState(false);
  const [error, setError] = useState(null);
  const messagesEndRef = useRef(null);

  const currentProjectId = useWorkspaceStore((state) => state.currentProjectId);
  const currentWorkspaceId = useWorkspaceStore((state) => state.currentWorkspaceId);

  // Auto-scroll to bottom of messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSubmit = async (e) => {
    e?.preventDefault();
    if (!prompt.trim() || isGenerating) return;

    const userMessage = {
      id: Date.now(),
      role: 'user',
      content: prompt,
      timestamp: new Date().toISOString(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setPrompt('');
    setIsGenerating(true);
    setError(null);

    try {
      // Send to canvas chat API
      const response = await api.sendCanvasChat({
        message: prompt,
        project_id: currentProjectId,
        workspace_id: currentWorkspaceId,
        context: {
          canvasName: 'Excalidraw Canvas',
          // Could include selected elements here
        },
      });

      const assistantMessage = {
        id: Date.now() + 1,
        role: 'assistant',
        content: response.content || response.message,
        contentTypes: detectContentTypes(response.content || response.message),
        timestamp: new Date().toISOString(),
        canInsert: true,
      };

      setMessages((prev) => [...prev, assistantMessage]);
    } catch (err) {
      setError(err.message || 'Failed to get AI response');
      const errorMessage = {
        id: Date.now() + 1,
        role: 'assistant',
        content: `Error: ${err.message || 'Failed to get AI response'}`,
        isError: true,
        timestamp: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      setIsGenerating(false);
    }
  };

  const handleInsertToCanvas = async (message) => {
    if (!excalidrawAPI || !message.content) return;

    try {
      // Get viewport center for placement
      const appState = excalidrawAPI.getAppState();
      const { width, height, scrollX, scrollY, zoom } = appState;
      const position = {
        x: (-scrollX + width / 2) / zoom.value,
        y: (-scrollY + height / 2) / zoom.value,
      };

      const { elements, files } = await convertAIResponseToElements(
        { content: message.content },
        position,
        { messageId: message.id }
      );

      // Add files to Excalidraw if any
      if (Object.keys(files).length > 0) {
        excalidrawAPI.addFiles(Object.values(files));
      }

      // Add elements to canvas
      const currentElements = excalidrawAPI.getSceneElements();
      excalidrawAPI.updateScene({
        elements: [...currentElements, ...elements],
      });

      // Notify parent
      onElementsGenerated?.(elements);

      // Mark message as inserted
      setMessages((prev) =>
        prev.map((m) => (m.id === message.id ? { ...m, inserted: true } : m))
      );
    } catch (err) {
      setError(`Failed to insert elements: ${err.message}`);
    }
  };

  const handleClearChat = () => {
    setMessages([]);
    setError(null);
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  return (
    <Sidebar name="ai-chat" docked={false}>
      <Sidebar.Header className="flex items-center gap-2">
        <Sparkles className="h-4 w-4" />
        <span>AI Canvas Assistant</span>
      </Sidebar.Header>

      <Sidebar.Tabs>
        <Sidebar.Tab tab="chat">
        <div className="flex flex-col h-full bg-surface">
          {/* Messages area */}
          <div className="flex-1 overflow-y-auto p-3 space-y-3">
            {messages.length === 0 ? (
              <div className="text-center text-text-secondary py-8">
                <Sparkles className="h-8 w-8 mx-auto mb-3 opacity-50" />
                <p className="text-sm">Ask me to create diagrams, flowcharts, or add content to your canvas.</p>
                <p className="text-xs mt-2 opacity-70">Try: &quot;Create a flowchart for user login&quot;</p>
              </div>
            ) : (
              messages.map((message) => (
                <div
                  key={message.id}
                  className={`rounded-lg p-3 text-sm ${
                    message.role === 'user'
                      ? 'bg-primary text-white ml-4'
                      : message.isError
                      ? 'bg-red-100 text-red-800 mr-4'
                      : 'bg-background mr-4'
                  }`}
                >
                  <div className="whitespace-pre-wrap">{message.content}</div>

                  {message.role === 'assistant' && message.canInsert && !message.isError && (
                    <div className="mt-2 pt-2 border-t border-border/50">
                      {message.contentTypes?.length > 0 && (
                        <p className="text-xs text-text-secondary mb-2">
                          Contains: {message.contentTypes.join(', ')}
                        </p>
                      )}
                      <button
                        onClick={() => handleInsertToCanvas(message)}
                        disabled={message.inserted}
                        className={`text-xs px-3 py-1 rounded flex items-center gap-1 ${
                          message.inserted
                            ? 'bg-green-100 text-green-700'
                            : 'bg-primary text-white hover:bg-primary/90'
                        }`}
                      >
                        <Plus className="h-3 w-3" />
                        {message.inserted ? 'Added to canvas' : 'Add to canvas'}
                      </button>
                    </div>
                  )}
                </div>
              ))
            )}

            {isGenerating && (
              <div className="flex items-center gap-2 text-text-secondary text-sm mr-4">
                <Loader2 className="h-4 w-4 animate-spin" />
                <span>Generating...</span>
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>

          {/* Error display */}
          {error && (
            <div className="px-3 py-2 bg-red-50 text-red-700 text-xs">
              {error}
            </div>
          )}

          {/* Input area */}
          <div className="border-t border-border p-3">
            <form onSubmit={handleSubmit} className="flex flex-col gap-2">
              <textarea
                value={prompt}
                onChange={(e) => setPrompt(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Describe what you want to create..."
                className="w-full px-3 py-2 text-sm rounded-md border border-border bg-background resize-none focus:outline-none focus:ring-2 focus:ring-primary"
                rows={3}
                disabled={isGenerating}
              />

              <div className="flex justify-between items-center">
                <button
                  type="button"
                  onClick={handleClearChat}
                  className="text-xs text-text-secondary hover:text-text flex items-center gap-1"
                  disabled={messages.length === 0}
                >
                  <Trash2 className="h-3 w-3" />
                  Clear
                </button>

                <button
                  type="submit"
                  disabled={!prompt.trim() || isGenerating}
                  className="px-4 py-1.5 bg-primary text-white rounded-md text-sm flex items-center gap-2 hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {isGenerating ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <Send className="h-4 w-4" />
                  )}
                  {isGenerating ? 'Generating...' : 'Generate'}
                </button>
              </div>
            </form>
          </div>
        </div>
      </Sidebar.Tab>
    </Sidebar.Tabs>
  </Sidebar>
  );
}
