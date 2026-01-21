/**
 * AI Prompt Frame Overlay
 *
 * Renders an overlay UI when an AI prompt frame is selected on the canvas.
 * Allows users to enter prompts and generate content directly on the canvas.
 */

import { useState, useEffect, useCallback } from 'react';
import { Sparkles, Loader2, X, Check, AlertCircle } from 'lucide-react';
import { convertAIResponseToElements } from './aiResponseConverter';
import { updateAIPromptFrame } from './canvasUtils';
import { useWorkspaceStore } from '../../stores';
import api from '../../services/api';

export default function AIPromptFrameOverlay({ excalidrawAPI, onElementsGenerated }) {
  const [activeFrame, setActiveFrame] = useState(null);
  const [prompt, setPrompt] = useState('');
  const [isGenerating, setIsGenerating] = useState(false);
  const [error, setError] = useState(null);
  const [overlayPosition, setOverlayPosition] = useState({ x: 0, y: 0 });

  const currentProjectId = useWorkspaceStore((state) => state.currentProjectId);
  const currentWorkspaceId = useWorkspaceStore((state) => state.currentWorkspaceId);

  // Listen for selection changes to detect AI prompt frames
  useEffect(() => {
    if (!excalidrawAPI) return;

    const checkSelection = () => {
      const appState = excalidrawAPI.getAppState();
      const selectedIds = Object.keys(appState.selectedElementIds || {});

      if (selectedIds.length === 1) {
        const elements = excalidrawAPI.getSceneElements();
        const selectedElement = elements.find((el) => el.id === selectedIds[0]);

        if (selectedElement?.customData?.isAIPromptFrame) {
          setActiveFrame(selectedElement);
          setPrompt(selectedElement.customData.prompt || '');
          setError(null);

          // Calculate overlay position based on frame position
          const { scrollX, scrollY, zoom } = appState;
          const screenX = (selectedElement.x + scrollX) * zoom.value;
          const screenY = (selectedElement.y + scrollY) * zoom.value;
          setOverlayPosition({ x: screenX, y: screenY });
          return;
        }
      }

      setActiveFrame(null);
    };

    // Check on mount and subscribe to changes
    checkSelection();

    const unsubscribe = excalidrawAPI.onChange(() => {
      checkSelection();
    });

    return () => {
      if (unsubscribe) unsubscribe();
    };
  }, [excalidrawAPI]);

  // Handle prompt generation
  const handleGenerate = useCallback(async () => {
    if (!activeFrame || !prompt.trim() || isGenerating) return;

    setIsGenerating(true);
    setError(null);

    // Update frame status to pending
    updateAIPromptFrame(excalidrawAPI, activeFrame.id, {
      status: 'pending',
      prompt: prompt.trim(),
    });

    try {
      // Send to canvas chat API
      const response = await api.sendCanvasChat({
        message: prompt,
        project_id: currentProjectId,
        workspace_id: currentWorkspaceId,
        context: {
          canvasName: 'AI Prompt Frame',
          frameId: activeFrame.id,
        },
      });

      // Convert response to elements
      const frameX = activeFrame.x + 20;
      const frameY = activeFrame.y + 40;

      const { elements: newElements, files } = await convertAIResponseToElements(
        { content: response.content || response.message },
        { x: frameX, y: frameY },
        { frameId: activeFrame.id, prompt: prompt.trim() }
      );

      // Add files if any
      if (files && Object.keys(files).length > 0) {
        excalidrawAPI.addFiles(Object.values(files));
      }

      // Add elements to canvas
      const currentElements = excalidrawAPI.getSceneElements();
      excalidrawAPI.updateScene({
        elements: [...currentElements, ...newElements],
      });

      // Update frame status to complete
      updateAIPromptFrame(excalidrawAPI, activeFrame.id, {
        status: 'complete',
      });

      onElementsGenerated?.(newElements);
    } catch (err) {
      setError(err.message || 'Failed to generate content');
      updateAIPromptFrame(excalidrawAPI, activeFrame.id, {
        status: 'error',
      });
    } finally {
      setIsGenerating(false);
    }
  }, [activeFrame, prompt, isGenerating, excalidrawAPI, currentProjectId, currentWorkspaceId, onElementsGenerated]);

  // Handle keyboard shortcuts
  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
      e.preventDefault();
      handleGenerate();
    }
    if (e.key === 'Escape') {
      setActiveFrame(null);
    }
  };

  // Close overlay
  const handleClose = () => {
    setActiveFrame(null);
  };

  if (!activeFrame) return null;

  const status = activeFrame.customData?.status || 'idle';

  return (
    <div
      className="absolute z-50 pointer-events-none"
      style={{
        left: overlayPosition.x,
        top: overlayPosition.y - 120,
      }}
    >
      <div className="pointer-events-auto bg-surface rounded-lg shadow-xl border border-border p-3 w-80">
        {/* Header */}
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-2">
            <Sparkles className="h-4 w-4 text-primary" />
            <span className="text-sm font-medium">AI Prompt Frame</span>
          </div>
          <button
            onClick={handleClose}
            className="p-1 rounded hover:bg-background text-text-secondary"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* Status indicator */}
        {status !== 'idle' && (
          <div
            className={`flex items-center gap-2 text-xs mb-2 px-2 py-1 rounded ${
              status === 'pending'
                ? 'bg-blue-50 text-blue-700'
                : status === 'complete'
                ? 'bg-green-50 text-green-700'
                : status === 'error'
                ? 'bg-red-50 text-red-700'
                : ''
            }`}
          >
            {status === 'pending' && <Loader2 className="h-3 w-3 animate-spin" />}
            {status === 'complete' && <Check className="h-3 w-3" />}
            {status === 'error' && <AlertCircle className="h-3 w-3" />}
            <span>
              {status === 'pending' && 'Generating...'}
              {status === 'complete' && 'Content generated'}
              {status === 'error' && 'Generation failed'}
            </span>
          </div>
        )}

        {/* Error message */}
        {error && (
          <div className="text-xs text-red-600 mb-2 bg-red-50 px-2 py-1 rounded">
            {error}
          </div>
        )}

        {/* Prompt input */}
        <textarea
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Describe what you want to create..."
          className="w-full px-3 py-2 text-sm rounded-md border border-border bg-background resize-none focus:outline-none focus:ring-2 focus:ring-primary"
          rows={3}
          disabled={isGenerating}
          autoFocus
        />

        {/* Actions */}
        <div className="flex justify-between items-center mt-2">
          <span className="text-xs text-text-secondary">
            {navigator.platform.includes('Mac') ? '⌘' : 'Ctrl'}+Enter to generate
          </span>
          <button
            onClick={handleGenerate}
            disabled={!prompt.trim() || isGenerating}
            className="px-3 py-1.5 bg-primary text-white rounded-md text-sm flex items-center gap-2 hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {isGenerating ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                Generating...
              </>
            ) : (
              <>
                <Sparkles className="h-4 w-4" />
                Generate
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
