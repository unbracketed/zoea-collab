/**
 * Mermaid Canvas Page - Mermaid Diagram Editor
 *
 * Split-pane view for live Mermaid diagram editing and rendering.
 * Left: Code editor for Mermaid syntax
 * Right: Live diagram preview
 */

import { useState, useEffect, useRef, useCallback } from 'react';
import { AlertCircle, LayoutPanelLeft } from 'lucide-react';
import mermaid from 'mermaid';
import DOMPurify from 'dompurify';
import LayoutFrame from '../components/layout/LayoutFrame';
import { useWorkspaceStore } from '../stores';
import api from '../services/api';

const LOCALSTORAGE_KEY_PREFIX = 'zoea-mermaid-canvas';
const DEBOUNCE_DELAY = 500;
const ERROR_DISPLAY_DELAY = 3000;

const getStorageKey = (projectId) =>
  projectId ? `${LOCALSTORAGE_KEY_PREFIX}-${projectId}` : LOCALSTORAGE_KEY_PREFIX;

// Initialize mermaid with default config
mermaid.initialize({
  startOnLoad: false,
  theme: 'default',
  securityLevel: 'loose',
});

function MermaidCanvasPage() {
  const [mermaidCode, setMermaidCode] = useState('');
  const [renderedSvg, setRenderedSvg] = useState('');
  const [hasError, setHasError] = useState(false);
  const [errorMessage, setErrorMessage] = useState(null);
  const [isTyping, setIsTyping] = useState(false);
  const [isRendering, setIsRendering] = useState(false);
  const [diagramName, setDiagramName] = useState('Mermaid Diagram');
  const [documentStatus, setDocumentStatus] = useState(null);
  const [isSavingDocument, setIsSavingDocument] = useState(false);
  const [editorOpen, setEditorOpen] = useState(true);

  const typingTimeoutRef = useRef(null);
  const renderTimeoutRef = useRef(null);
  const renderIdRef = useRef(0);

  const currentWorkspaceId = useWorkspaceStore((state) => state.currentWorkspaceId);
  const currentProjectId = useWorkspaceStore((state) => state.currentProjectId);
  const currentWorkspace = useWorkspaceStore((state) => state.getCurrentWorkspace());

  const trimmedCode = mermaidCode.trim();

  // Load from localStorage when project changes
  useEffect(() => {
    if (!currentProjectId) return;

    const storageKey = getStorageKey(currentProjectId);
    const saved = localStorage.getItem(storageKey);
    if (saved) {
      setMermaidCode(saved);
      renderDiagram(saved);
    } else {
      setMermaidCode('');
      setRenderedSvg('');
      setHasError(false);
      setErrorMessage(null);
    }
  }, [currentProjectId]);

  // Save to localStorage whenever code changes
  useEffect(() => {
    if (!currentProjectId) return;

    const storageKey = getStorageKey(currentProjectId);
    if (mermaidCode) {
      localStorage.setItem(storageKey, mermaidCode);
    }
  }, [mermaidCode, currentProjectId]);

  // Update diagram name when workspace changes
  useEffect(() => {
    if (currentWorkspace?.name && diagramName === 'Mermaid Diagram') {
      setDiagramName(`${currentWorkspace.name} Mermaid`);
    }
  }, [currentWorkspace, diagramName]);

  // Clear status messages after delay
  useEffect(() => {
    if (!documentStatus) return;
    const timeout = setTimeout(() => setDocumentStatus(null), 3000);
    return () => clearTimeout(timeout);
  }, [documentStatus]);

  // Render function
  const renderDiagram = useCallback(async (code) => {
    if (!code.trim()) {
      setRenderedSvg('');
      setHasError(false);
      setErrorMessage(null);
      setIsRendering(false);
      return;
    }

    try {
      setIsRendering(true);
      renderIdRef.current += 1;
      const id = `mermaid-${renderIdRef.current}`;

      const { svg } = await mermaid.render(id, code);
      // Sanitize SVG output to prevent XSS
      const sanitizedSvg = DOMPurify.sanitize(svg, {
        USE_PROFILES: { svg: true, svgFilters: true },
      });
      setRenderedSvg(sanitizedSvg);
      setHasError(false);
      setErrorMessage(null);
    } catch (error) {
      setHasError(true);
      setErrorMessage(error.message || 'Failed to render Mermaid diagram');
    } finally {
      setIsRendering(false);
    }
  }, []);

  // Debounced render function
  const debouncedRender = useCallback(
    (code) => {
      if (renderTimeoutRef.current) {
        clearTimeout(renderTimeoutRef.current);
      }

      renderTimeoutRef.current = setTimeout(() => {
        renderDiagram(code);
      }, DEBOUNCE_DELAY);
    },
    [renderDiagram]
  );

  // Handle code change
  const handleCodeChange = (e) => {
    const newCode = e.target.value;
    setMermaidCode(newCode);
    setIsTyping(true);

    if (typingTimeoutRef.current) {
      clearTimeout(typingTimeoutRef.current);
    }

    typingTimeoutRef.current = setTimeout(() => {
      setIsTyping(false);
    }, ERROR_DISPLAY_DELAY);

    debouncedRender(newCode);
  };

  // Cleanup timeouts on unmount
  useEffect(() => {
    return () => {
      if (typingTimeoutRef.current) {
        clearTimeout(typingTimeoutRef.current);
      }
      if (renderTimeoutRef.current) {
        clearTimeout(renderTimeoutRef.current);
      }
    };
  }, []);

  const handleSaveAsDocument = async () => {
    if (!currentWorkspaceId || !currentProjectId) {
      setDocumentStatus('Select a project and workspace to save this diagram.');
      return;
    }

    if (!trimmedCode) {
      setDocumentStatus('Add diagram code before saving as a document.');
      return;
    }

    setIsSavingDocument(true);
    setDocumentStatus('Saving diagram as document...');
    try {
      await api.createMermaidDocument({
        name: diagramName || 'Mermaid Diagram',
        description: `Saved from Canvas - ${currentWorkspace?.name || ''}`,
        content: mermaidCode,
        project_id: currentProjectId,
        workspace_id: currentWorkspaceId,
      });
      setDocumentStatus('Diagram saved to Documents.');
    } catch (error) {
      setDocumentStatus(error.message || 'Failed to save diagram.');
    } finally {
      setIsSavingDocument(false);
    }
  };

  const handleClear = () => {
    if (!currentProjectId) return;

    setMermaidCode('');
    setRenderedSvg('');
    setHasError(false);
    setErrorMessage(null);
    localStorage.removeItem(getStorageKey(currentProjectId));
  };

  const shouldShowError = hasError && !isTyping;
  const shouldShowWarning = hasError && isTyping;

  const actions = (
    <div className="flex gap-2">
      <button
        className="px-3 py-1.5 text-sm bg-primary text-white rounded hover:opacity-90 transition-opacity disabled:opacity-50"
        onClick={handleSaveAsDocument}
        disabled={isSavingDocument || !trimmedCode}
      >
        {isSavingDocument ? 'Saving...' : 'Save as Document'}
      </button>
    </div>
  );

  return (
    <LayoutFrame title={diagramName || 'Mermaid Canvas'} actions={actions} variant="full" noPadding={true}>
      <div className="relative flex flex-col flex-1 w-full bg-background rounded-lg border border-border overflow-hidden">
        <div className="absolute top-4 left-4 w-[420px] max-w-[90vw] bg-surface border border-border shadow-strong rounded-lg overflow-hidden z-50 pointer-events-auto">
          <div className="flex items-center justify-between bg-background px-3 py-2">
            <div className="flex items-center gap-2">
              <LayoutPanelLeft className="h-4 w-4" />
              <span className="text-sm font-semibold">Mermaid Editor</span>
            </div>
            <button
              type="button"
              className="text-xs text-text-secondary hover:text-text-primary"
              onClick={() => setEditorOpen((v) => !v)}
            >
              {editorOpen ? 'Hide' : 'Show'}
            </button>
          </div>
          {editorOpen && (
            <div className="p-3 space-y-3 bg-surface">
              {documentStatus && (
                <div className="text-xs text-primary">{documentStatus}</div>
              )}
              <textarea
                className="w-full h-48 p-2 text-sm font-mono bg-background border border-border rounded resize-none focus:outline-none focus:ring-2 focus:ring-primary"
                value={mermaidCode}
                onChange={handleCodeChange}
                placeholder={`Type your Mermaid code here...

Example:
flowchart TD
    A[Start] --> B{Decision}
    B -->|Yes| C[Action 1]
    B -->|No| D[Action 2]`}
                spellCheck={false}
              />
              <div className="flex justify-between items-center">
                <input
                  type="text"
                  className="flex-1 px-2 py-1 text-sm border border-border rounded bg-background focus:outline-none focus:ring-2 focus:ring-primary"
                  placeholder="Diagram name"
                  value={diagramName}
                  onChange={(e) => setDiagramName(e.target.value)}
                />
                {mermaidCode && (
                  <button
                    className="ml-2 px-2 py-1 text-sm border border-border text-text-secondary rounded hover:bg-background transition-colors"
                    onClick={handleClear}
                  >
                    Clear
                  </button>
                )}
              </div>
            </div>
          )}
        </div>

        <div className="flex flex-col flex-1 w-full">
          <div className="flex-1 overflow-auto min-h-0 flex items-center justify-center p-8">
            {isRendering && (
              <div className="absolute top-3 right-3 text-xs text-text-secondary bg-surface border border-border rounded-md px-2 py-1">
                Rendering...
              </div>
            )}
            {shouldShowWarning && (
              <div className="absolute top-3 right-3 text-xs text-orange-500 flex items-center gap-1 bg-surface border border-border rounded-md px-2 py-1">
                <AlertCircle size={14} /> {errorMessage}
              </div>
            )}
            {shouldShowError ? (
              <div className="text-center p-8">
                <AlertCircle size={48} className="mx-auto mb-4 text-destructive" />
                <h4 className="text-lg font-medium mb-2">Render Error</h4>
                <pre className="text-sm text-destructive bg-destructive/10 p-4 rounded max-w-md overflow-auto">
                  {errorMessage}
                </pre>
                <p className="text-sm text-muted-foreground mt-4">
                  Fix the errors above to see your diagram.
                </p>
              </div>
            ) : renderedSvg ? (
              <div
                className="mermaid-preview max-w-full"
                dangerouslySetInnerHTML={{ __html: renderedSvg }}
              />
            ) : (
              <div className="text-center p-8">
                <h4 className="text-lg font-medium mb-2">Start Creating</h4>
                <p className="text-muted-foreground mb-4">
                  Type Mermaid code in the editor to see your diagram here.
                </p>
                <div className="text-left bg-muted p-4 rounded max-w-sm mx-auto">
                  <strong className="text-sm">Try this example:</strong>
                  <pre className="text-xs mt-2 text-muted-foreground">
{`flowchart TD
    A[Start] --> B{Decision}
    B -->|Yes| C[Action 1]
    B -->|No| D[Action 2]`}
                  </pre>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </LayoutFrame>
  );
}

export default MermaidCanvasPage;
