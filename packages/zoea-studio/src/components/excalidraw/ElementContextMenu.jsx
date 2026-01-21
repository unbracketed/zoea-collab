/**
 * Element Context Menu for Excalidraw
 *
 * Provides right-click context menu for canvas elements with customData
 * (document links, AI prompt frames, etc.)
 */

import { useState, useEffect, useCallback, useRef, forwardRef, useImperativeHandle } from 'react';
import { useNavigate } from 'react-router-dom';
import { ExternalLink, Trash2, Edit, Copy, FileText, Sparkles } from 'lucide-react';

const ElementContextMenu = forwardRef(function ElementContextMenu(
  { excalidrawAPI, onRemoveLink },
  ref
) {
  const navigate = useNavigate();
  const [menuState, setMenuState] = useState({
    isOpen: false,
    x: 0,
    y: 0,
    element: null,
  });
  const menuRef = useRef(null);

  // Close menu when clicking outside
  useEffect(() => {
    const handleClickOutside = (e) => {
      if (menuRef.current && !menuRef.current.contains(e.target)) {
        setMenuState((prev) => ({ ...prev, isOpen: false }));
      }
    };

    if (menuState.isOpen) {
      document.addEventListener('mousedown', handleClickOutside);
      document.addEventListener('contextmenu', handleClickOutside);
    }

    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
      document.removeEventListener('contextmenu', handleClickOutside);
    };
  }, [menuState.isOpen]);

  // Close on escape
  useEffect(() => {
    const handleEscape = (e) => {
      if (e.key === 'Escape') {
        setMenuState((prev) => ({ ...prev, isOpen: false }));
      }
    };

    document.addEventListener('keydown', handleEscape);
    return () => document.removeEventListener('keydown', handleEscape);
  }, []);

  // Open document in detail view
  const handleOpenDocument = useCallback(() => {
    const documentId = menuState.element?.customData?.projectDocumentId;
    if (documentId) {
      navigate(`/documents/${documentId}`);
    }
    setMenuState((prev) => ({ ...prev, isOpen: false }));
  }, [menuState.element, navigate]);

  // Copy document name to clipboard
  const handleCopyName = useCallback(async () => {
    const name = menuState.element?.customData?.projectDocumentName;
    if (name) {
      await navigator.clipboard.writeText(name);
    }
    setMenuState((prev) => ({ ...prev, isOpen: false }));
  }, [menuState.element]);

  // Remove the document link (keep element, clear customData)
  const handleRemoveLink = useCallback(() => {
    if (menuState.element && onRemoveLink) {
      onRemoveLink(menuState.element.id);
    }
    setMenuState((prev) => ({ ...prev, isOpen: false }));
  }, [menuState.element, onRemoveLink]);

  // Expose the show function for external use
  const showMenu = useCallback((x, y, element) => {
    setMenuState({ isOpen: true, x, y, element });
  }, []);

  // Expose showMenu via ref
  useImperativeHandle(ref, () => ({
    showMenu,
  }), [showMenu]);

  if (!menuState.isOpen || !menuState.element) return null;

  const { customData } = menuState.element;
  const isDocumentLink = customData?.projectDocumentId;
  const isAIFrame = customData?.isAIPromptFrame;

  // Don't show if no relevant customData
  if (!isDocumentLink && !isAIFrame) return null;

  return (
    <div
      ref={menuRef}
      className="fixed z-[9999] bg-surface rounded-lg shadow-xl border border-border py-1 min-w-48"
      style={{ left: menuState.x, top: menuState.y }}
    >
      {isDocumentLink && (
        <>
          <div className="px-3 py-1.5 text-xs text-text-secondary border-b border-border flex items-center gap-2">
            <FileText className="h-3 w-3" />
            <span className="truncate max-w-40">
              {customData.projectDocumentName || 'Document'}
            </span>
          </div>

          <button
            onClick={handleOpenDocument}
            className="w-full px-3 py-2 text-sm text-left flex items-center gap-2 hover:bg-background"
          >
            <ExternalLink className="h-4 w-4" />
            Open Document
          </button>

          <button
            onClick={handleCopyName}
            className="w-full px-3 py-2 text-sm text-left flex items-center gap-2 hover:bg-background"
          >
            <Copy className="h-4 w-4" />
            Copy Name
          </button>

          <div className="border-t border-border my-1" />

          <button
            onClick={handleRemoveLink}
            className="w-full px-3 py-2 text-sm text-left flex items-center gap-2 hover:bg-background text-red-600"
          >
            <Trash2 className="h-4 w-4" />
            Remove Link
          </button>
        </>
      )}

      {isAIFrame && (
        <>
          <div className="px-3 py-1.5 text-xs text-text-secondary border-b border-border flex items-center gap-2">
            <Sparkles className="h-3 w-3" />
            AI Prompt Frame
          </div>

          <button
            onClick={() => {
              // Focus the frame to trigger overlay
              if (excalidrawAPI) {
                excalidrawAPI.updateScene({
                  appState: {
                    selectedElementIds: { [menuState.element.id]: true },
                  },
                });
              }
              setMenuState((prev) => ({ ...prev, isOpen: false }));
            }}
            className="w-full px-3 py-2 text-sm text-left flex items-center gap-2 hover:bg-background"
          >
            <Edit className="h-4 w-4" />
            Edit Prompt
          </button>

          {customData.prompt && (
            <button
              onClick={async () => {
                await navigator.clipboard.writeText(customData.prompt);
                setMenuState((prev) => ({ ...prev, isOpen: false }));
              }}
              className="w-full px-3 py-2 text-sm text-left flex items-center gap-2 hover:bg-background"
            >
              <Copy className="h-4 w-4" />
              Copy Prompt
            </button>
          )}
        </>
      )}
    </div>
  );
});

export default ElementContextMenu;
