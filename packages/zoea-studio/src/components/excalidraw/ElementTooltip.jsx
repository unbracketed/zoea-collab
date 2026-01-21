/**
 * Element Tooltip for Excalidraw
 *
 * Shows tooltip when hovering over canvas elements with customData
 * (document links, AI prompt frames, etc.)
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import { FileText, Image, FileCode, Sparkles, ExternalLink } from 'lucide-react';

const TOOLTIP_DELAY = 500; // ms before showing tooltip

export default function ElementTooltip({ excalidrawAPI }) {
  const [tooltipState, setTooltipState] = useState({
    isVisible: false,
    x: 0,
    y: 0,
    element: null,
  });
  const hoverTimer = useRef(null);
  const lastPointerPos = useRef({ x: 0, y: 0 });

  // Get icon for document type
  const getDocumentIcon = (docType) => {
    switch (docType) {
      case 'Image':
        return <Image className="h-3 w-3" />;
      case 'MarkdownDocument':
      case 'Markdown':
        return <FileText className="h-3 w-3" />;
      case 'D2Diagram':
      case 'MermaidDiagram':
      case 'ExcalidrawDiagram':
        return <FileCode className="h-3 w-3" />;
      default:
        return <FileText className="h-3 w-3" />;
    }
  };

  // Find element at screen position
  const findElementAtScreenPosition = useCallback(
    (screenX, screenY) => {
      if (!excalidrawAPI) return null;

      const appState = excalidrawAPI.getAppState();
      const { scrollX, scrollY, zoom } = appState;

      // Convert screen coordinates to canvas coordinates
      const canvasX = (screenX - scrollX * zoom.value) / zoom.value;
      const canvasY = (screenY - scrollY * zoom.value) / zoom.value;

      // Get elements and find one at position
      const elements = excalidrawAPI.getSceneElements();

      for (let i = elements.length - 1; i >= 0; i--) {
        const el = elements[i];
        if (el.isDeleted) continue;

        // Check bounding box
        if (
          canvasX >= el.x &&
          canvasX <= el.x + (el.width || 0) &&
          canvasY >= el.y &&
          canvasY <= el.y + (el.height || 0)
        ) {
          // Only return if has relevant customData
          if (el.customData?.projectDocumentId || el.customData?.isAIPromptFrame) {
            return el;
          }
        }
      }

      return null;
    },
    [excalidrawAPI]
  );

  // Handle pointer move
  useEffect(() => {
    if (!excalidrawAPI) return;

    const handlePointerMove = (e) => {
      // Get position relative to the excalidraw container
      const container = document.querySelector('.excalidraw');
      if (!container) return;

      const rect = container.getBoundingClientRect();
      const relX = e.clientX - rect.left;
      const relY = e.clientY - rect.top;

      lastPointerPos.current = { x: e.clientX, y: e.clientY };

      // Clear existing timer
      if (hoverTimer.current) {
        clearTimeout(hoverTimer.current);
        hoverTimer.current = null;
      }

      // Hide tooltip immediately when moving
      if (tooltipState.isVisible) {
        setTooltipState((prev) => ({ ...prev, isVisible: false }));
      }

      // Start new hover timer
      hoverTimer.current = setTimeout(() => {
        const element = findElementAtScreenPosition(relX, relY);
        if (element) {
          setTooltipState({
            isVisible: true,
            x: e.clientX + 10,
            y: e.clientY + 10,
            element,
          });
        }
      }, TOOLTIP_DELAY);
    };

    const handlePointerLeave = () => {
      if (hoverTimer.current) {
        clearTimeout(hoverTimer.current);
        hoverTimer.current = null;
      }
      setTooltipState((prev) => ({ ...prev, isVisible: false }));
    };

    // Attach to the excalidraw container
    const container = document.querySelector('.excalidraw');
    if (container) {
      container.addEventListener('pointermove', handlePointerMove);
      container.addEventListener('pointerleave', handlePointerLeave);
    }

    return () => {
      if (hoverTimer.current) {
        clearTimeout(hoverTimer.current);
      }
      if (container) {
        container.removeEventListener('pointermove', handlePointerMove);
        container.removeEventListener('pointerleave', handlePointerLeave);
      }
    };
  }, [excalidrawAPI, findElementAtScreenPosition, tooltipState.isVisible]);

  if (!tooltipState.isVisible || !tooltipState.element) return null;

  const { customData } = tooltipState.element;
  const isDocumentLink = customData?.projectDocumentId;
  const isAIFrame = customData?.isAIPromptFrame;

  return (
    <div
      className="fixed z-[9998] bg-surface rounded-md shadow-lg border border-border px-2 py-1.5 pointer-events-none max-w-64"
      style={{ left: tooltipState.x, top: tooltipState.y }}
    >
      {isDocumentLink && (
        <div className="flex flex-col gap-1">
          <div className="flex items-center gap-2 text-sm font-medium">
            {getDocumentIcon(customData.documentType)}
            <span className="truncate">{customData.projectDocumentName || 'Document'}</span>
          </div>
          <div className="text-xs text-text-secondary flex items-center gap-1">
            <ExternalLink className="h-3 w-3" />
            Double-click to open
          </div>
        </div>
      )}

      {isAIFrame && (
        <div className="flex flex-col gap-1">
          <div className="flex items-center gap-2 text-sm font-medium">
            <Sparkles className="h-3 w-3 text-primary" />
            AI Prompt Frame
          </div>
          {customData.prompt ? (
            <div className="text-xs text-text-secondary truncate">
              &quot;{customData.prompt.substring(0, 50)}
              {customData.prompt.length > 50 ? '...' : ''}&quot;
            </div>
          ) : (
            <div className="text-xs text-text-secondary">Click to add prompt</div>
          )}
          {customData.status && customData.status !== 'idle' && (
            <div
              className={`text-xs capitalize ${
                customData.status === 'complete'
                  ? 'text-green-600'
                  : customData.status === 'error'
                  ? 'text-red-600'
                  : 'text-blue-600'
              }`}
            >
              Status: {customData.status}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
