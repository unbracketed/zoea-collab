/**
 * ExcalidrawEditor Component
 *
 * Reusable Excalidraw editor component with theme support.
 * Integrates with the app's light/dark mode settings.
 * Supports custom menus, document insertion, and AI chat sidebar.
 *
 * Reference: https://docs.excalidraw.com/docs/@excalidraw/excalidraw/customizing-styles
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Excalidraw, exportToBlob } from '@excalidraw/excalidraw';
import '@excalidraw/excalidraw/index.css';
import { Sparkles, FolderOpen } from 'lucide-react';
import { useThemeStore } from '../stores/themeStore';
import ExcalidrawMainMenu from './excalidraw/ExcalidrawMainMenu';
import DocumentPickerModal from './excalidraw/DocumentPickerModal';
import AIChatSidebar from './excalidraw/AIChatSidebar';
import AIPromptFrameOverlay from './excalidraw/AIPromptFrameOverlay';
import ElementContextMenu from './excalidraw/ElementContextMenu';
import ElementTooltip from './excalidraw/ElementTooltip';
import {
  insertImageOnCanvas,
  insertTextDocumentOnCanvas,
  createAIPromptFrame,
  getElementAtPosition,
} from './excalidraw/canvasUtils';

/**
 * Get the current system color scheme preference
 */
const getSystemPreference = () => {
  if (typeof window === 'undefined') return 'light';
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
};

/**
 * ExcalidrawEditor - A wrapper component for the Excalidraw canvas
 *
 * @param {Object} props
 * @param {Object} props.initialData - Initial Excalidraw scene data (elements, appState, files)
 * @param {Function} props.onDataChange - Callback when scene data changes (debounced)
 * @param {boolean} props.readOnly - Whether the editor is read-only
 * @param {number} props.debounceMs - Debounce delay for onChange (default: 300)
 * @param {Function} props.excalidrawRef - Ref callback to access Excalidraw API
 * @param {boolean} props.enableCustomMenu - Enable custom project menu (default: true when not readOnly)
 * @param {boolean} props.enableAIChat - Enable AI chat sidebar (default: true when not readOnly)
 */
export default function ExcalidrawEditor({
  initialData = null,
  onDataChange = null,
  readOnly = false,
  debounceMs = 300,
  excalidrawRef = null,
  enableCustomMenu = null,
  enableAIChat = null,
}) {
  const navigate = useNavigate();
  const mode = useThemeStore((state) => state.mode);
  const [excalidrawAPI, setExcalidrawAPI] = useState(null);
  const [systemPreference, setSystemPreference] = useState(getSystemPreference);
  const [showDocumentPicker, setShowDocumentPicker] = useState(false);
  const [showImagePicker, setShowImagePicker] = useState(false);
  const debounceTimer = useRef(null);
  const isInitialMount = useRef(true);
  const containerRef = useRef(null);
  const contextMenuRef = useRef(null);

  // Default enableCustomMenu and enableAIChat based on readOnly
  const showCustomMenu = enableCustomMenu ?? !readOnly;
  const showAIChat = enableAIChat ?? !readOnly;

  // Listen for system preference changes when mode is 'auto'
  useEffect(() => {
    if (typeof window === 'undefined') return;
    const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');
    const handler = (e) => setSystemPreference(e.matches ? 'dark' : 'light');
    mediaQuery.addEventListener('change', handler);
    return () => mediaQuery.removeEventListener('change', handler);
  }, []);

  // Get the resolved theme mode (light/dark)
  const theme = mode === 'auto' ? systemPreference : mode;

  // Pass the API reference back to parent if requested
  useEffect(() => {
    if (excalidrawRef && excalidrawAPI) {
      excalidrawRef(excalidrawAPI);
    }
  }, [excalidrawAPI, excalidrawRef]);

  // Handle scene changes with debounce
  const handleChange = useCallback(
    (elements, appState, files) => {
      // Skip the initial render
      if (isInitialMount.current) {
        isInitialMount.current = false;
        return;
      }

      if (!onDataChange) return;

      // Clear existing timer
      if (debounceTimer.current) {
        clearTimeout(debounceTimer.current);
      }

      // Set new debounced callback
      debounceTimer.current = setTimeout(() => {
        const sceneData = {
          type: 'excalidraw',
          version: 2,
          source: 'zoea-studio',
          elements,
          appState: {
            // Only persist relevant appState properties
            viewBackgroundColor: appState.viewBackgroundColor,
            gridSize: appState.gridSize,
          },
          files,
        };
        onDataChange(sceneData);
      }, debounceMs);
    },
    [onDataChange, debounceMs]
  );

  // Cleanup debounce timer on unmount
  useEffect(() => {
    return () => {
      if (debounceTimer.current) {
        clearTimeout(debounceTimer.current);
      }
    };
  }, []);

  // Parse initial data if it's a string
  const parsedInitialData = typeof initialData === 'string'
    ? JSON.parse(initialData)
    : initialData;

  // Handle document selection from picker
  const handleDocumentSelect = async (doc) => {
    if (!excalidrawAPI) return;

    try {
      if (doc.document_type === 'Image') {
        await insertImageOnCanvas(excalidrawAPI, doc);
      } else {
        insertTextDocumentOnCanvas(excalidrawAPI, doc);
      }
    } catch (error) {
      console.error('Failed to insert document:', error);
    }
  };

  // Handle image selection from picker
  const handleImageSelect = async (doc) => {
    if (!excalidrawAPI) return;

    try {
      await insertImageOnCanvas(excalidrawAPI, doc);
    } catch (error) {
      console.error('Failed to insert image:', error);
    }
  };

  // Toggle AI chat sidebar
  const handleOpenAIChat = () => {
    if (excalidrawAPI) {
      excalidrawAPI.toggleSidebar({ name: 'ai-chat', tab: 'chat' });
    }
  };

  // Create AI prompt frame on canvas
  const handleCreateAIFrame = () => {
    if (excalidrawAPI) {
      createAIPromptFrame(excalidrawAPI);
    }
  };

  // Convert screen coordinates to canvas coordinates
  const screenToCanvas = useCallback(
    (screenX, screenY) => {
      if (!excalidrawAPI) return { x: 0, y: 0 };
      const appState = excalidrawAPI.getAppState();
      const { scrollX, scrollY, zoom } = appState;
      return {
        x: (screenX - scrollX * zoom.value) / zoom.value,
        y: (screenY - scrollY * zoom.value) / zoom.value,
      };
    },
    [excalidrawAPI]
  );

  // Handle double-click on document links
  useEffect(() => {
    if (!excalidrawAPI || !containerRef.current) return;

    const handleDoubleClick = (e) => {
      const container = containerRef.current;
      if (!container) return;

      const rect = container.getBoundingClientRect();
      const relX = e.clientX - rect.left;
      const relY = e.clientY - rect.top;

      const canvasPos = screenToCanvas(relX, relY);
      const element = getElementAtPosition(excalidrawAPI, canvasPos);

      if (element?.customData?.projectDocumentId) {
        e.preventDefault();
        e.stopPropagation();
        navigate(`/documents/${element.customData.projectDocumentId}`);
      }
    };

    const container = containerRef.current;
    container.addEventListener('dblclick', handleDoubleClick);

    return () => {
      container.removeEventListener('dblclick', handleDoubleClick);
    };
  }, [excalidrawAPI, navigate, screenToCanvas]);

  // Handle right-click context menu
  useEffect(() => {
    if (!excalidrawAPI || !containerRef.current) return;

    const handleContextMenu = (e) => {
      const container = containerRef.current;
      if (!container) return;

      const rect = container.getBoundingClientRect();
      const relX = e.clientX - rect.left;
      const relY = e.clientY - rect.top;

      const canvasPos = screenToCanvas(relX, relY);
      const element = getElementAtPosition(excalidrawAPI, canvasPos);

      // Only show custom context menu for elements with customData
      if (
        element?.customData?.projectDocumentId ||
        element?.customData?.isAIPromptFrame
      ) {
        e.preventDefault();
        e.stopPropagation();

        // Show context menu via the component's exposed method
        if (contextMenuRef.current?.showMenu) {
          contextMenuRef.current.showMenu(e.clientX, e.clientY, element);
        }
      }
    };

    const container = containerRef.current;
    container.addEventListener('contextmenu', handleContextMenu);

    return () => {
      container.removeEventListener('contextmenu', handleContextMenu);
    };
  }, [excalidrawAPI, screenToCanvas]);

  // Handle removing document link from element
  const handleRemoveLink = useCallback(
    (elementId) => {
      if (!excalidrawAPI) return;

      const elements = excalidrawAPI.getSceneElements();
      const updatedElements = elements.map((el) => {
        if (el.id === elementId) {
          // Remove document link properties from customData
          const customData = el.customData || {};
          const {
            projectDocumentId: _pid,
            projectDocumentName: _pname,
            documentType: _dtype,
            isDocumentLink: _link,
            ...restCustomData
          } = customData;
          // Silence lint for intentionally unused vars
          void _pid, _pname, _dtype, _link;
          return {
            ...el,
            customData: Object.keys(restCustomData).length > 0 ? restCustomData : undefined,
          };
        }
        return el;
      });

      excalidrawAPI.updateScene({ elements: updatedElements });
    },
    [excalidrawAPI]
  );

  // Render top-right UI buttons
  const renderTopRightUI = () => {
    if (readOnly) return null;

    return (
      <div className="flex items-center gap-1">
        {showAIChat && (
          <button
            onClick={handleOpenAIChat}
            title="AI Assistant"
            className="p-2 rounded hover:bg-black/10 dark:hover:bg-white/10"
          >
            <Sparkles className="h-4 w-4" />
          </button>
        )}
        {showCustomMenu && (
          <button
            onClick={() => setShowDocumentPicker(true)}
            title="Insert from Documents"
            className="p-2 rounded hover:bg-black/10 dark:hover:bg-white/10"
          >
            <FolderOpen className="h-4 w-4" />
          </button>
        )}
      </div>
    );
  };

  return (
    <div ref={containerRef} style={{ width: '100%', height: '100%', position: 'relative' }}>
      <Excalidraw
        excalidrawAPI={(api) => setExcalidrawAPI(api)}
        initialData={parsedInitialData}
        onChange={handleChange}
        theme={theme}
        viewModeEnabled={readOnly}
        UIOptions={{
          canvasActions: {
            loadScene: !readOnly,
            saveToActiveFile: !readOnly,
            export: readOnly ? false : { saveFileToDisk: true },
            clearCanvas: !readOnly,
          },
          tools: showCustomMenu ? { image: false } : {},
        }}
        renderTopRightUI={renderTopRightUI}
      >
        {/* Custom Main Menu */}
        {showCustomMenu && (
          <ExcalidrawMainMenu
            onInsertDocument={() => setShowDocumentPicker(true)}
            onInsertImage={() => setShowImagePicker(true)}
            onOpenAIChat={handleOpenAIChat}
            onCreateAIFrame={handleCreateAIFrame}
          />
        )}

        {/* AI Chat Sidebar */}
        {showAIChat && (
          <AIChatSidebar
            excalidrawAPI={excalidrawAPI}
            onElementsGenerated={() => {
              // Optionally trigger save/change callback
              if (excalidrawAPI && onDataChange) {
                const elements = excalidrawAPI.getSceneElements();
                const appState = excalidrawAPI.getAppState();
                const files = excalidrawAPI.getFiles();
                handleChange(elements, appState, files);
              }
            }}
          />
        )}
      </Excalidraw>

      {/* Document Picker Modal */}
      <DocumentPickerModal
        isOpen={showDocumentPicker}
        onClose={() => setShowDocumentPicker(false)}
        onSelect={handleDocumentSelect}
        title="Insert Document"
      />

      {/* Image Picker Modal */}
      <DocumentPickerModal
        isOpen={showImagePicker}
        onClose={() => setShowImagePicker(false)}
        onSelect={handleImageSelect}
        allowedTypes={['Image']}
        title="Insert Image"
      />

      {/* AI Prompt Frame Overlay */}
      {showAIChat && (
        <AIPromptFrameOverlay
          excalidrawAPI={excalidrawAPI}
          onElementsGenerated={() => {
            if (excalidrawAPI && onDataChange) {
              const elements = excalidrawAPI.getSceneElements();
              const appState = excalidrawAPI.getAppState();
              const files = excalidrawAPI.getFiles();
              handleChange(elements, appState, files);
            }
          }}
        />
      )}

      {/* Element Context Menu (right-click) */}
      <ElementContextMenu
        ref={contextMenuRef}
        excalidrawAPI={excalidrawAPI}
        onRemoveLink={handleRemoveLink}
      />

      {/* Element Tooltip (hover) */}
      <ElementTooltip excalidrawAPI={excalidrawAPI} />
    </div>
  );
}

/**
 * Get the current scene data from an Excalidraw API instance
 *
 * @param {Object} excalidrawAPI - The Excalidraw API instance
 * @returns {Object} The scene data object
 */
export function getSceneData(excalidrawAPI) {
  if (!excalidrawAPI) return null;

  const elements = excalidrawAPI.getSceneElements();
  const appState = excalidrawAPI.getAppState();
  const files = excalidrawAPI.getFiles();

  return {
    type: 'excalidraw',
    version: 2,
    source: 'zoea-studio',
    elements,
    appState: {
      viewBackgroundColor: appState.viewBackgroundColor,
      gridSize: appState.gridSize,
    },
    files,
  };
}

/**
 * Export the current scene as a PNG blob
 *
 * @param {Object} excalidrawAPI - The Excalidraw API instance
 * @param {Object} options - Export options
 * @param {string} options.backgroundColor - Background color (default: transparent)
 * @param {number} options.scale - Export scale (default: 2)
 * @returns {Promise<Blob>} The PNG blob
 */
export async function exportToPng(excalidrawAPI, options = {}) {
  if (!excalidrawAPI) return null;

  const elements = excalidrawAPI.getSceneElements();
  const appState = excalidrawAPI.getAppState();
  const files = excalidrawAPI.getFiles();

  const blob = await exportToBlob({
    elements,
    appState: {
      ...appState,
      exportBackground: options.backgroundColor !== 'transparent',
      viewBackgroundColor: options.backgroundColor || appState.viewBackgroundColor,
    },
    files,
    mimeType: 'image/png',
    quality: 1,
    exportPadding: 10,
  });

  return blob;
}
