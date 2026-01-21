/**
 * Canvas Page - D2 Diagram Playground
 *
 * Split-pane view for live D2 diagram editing and rendering.
 * Left: Simple textarea for D2 code
 * Right: Live diagram preview with error handling
 */

import { useState, useEffect, useRef, useMemo, useCallback } from 'react';
import { AlertCircle, Rows, LayoutPanelLeft } from 'lucide-react';
import { compileD2 } from '../utils/d2Compiler';
import { convertD2ToReactFlow, convertDiagramToReactFlow } from '../utils/d2ToReactFlow';
import DiagramPreview from '../components/DiagramPreview';
import LayoutFrame from '../components/layout/LayoutFrame';
import { useClipboardStore, useWorkspaceStore } from '../stores';
import { useShallow } from 'zustand/react/shallow';
import api from '../services/api';

const LOCALSTORAGE_KEY_PREFIX = 'zoea-canvas-d2-code';
const DEBOUNCE_DELAY = 500; // ms
const ERROR_DISPLAY_DELAY = 3000; // ms

// Generate project-scoped localStorage key
const getStorageKey = (projectId) => projectId ? `${LOCALSTORAGE_KEY_PREFIX}-${projectId}` : LOCALSTORAGE_KEY_PREFIX;

function CanvasPage() {
  // State
  const [d2Code, setD2Code] = useState('');
  const [lastValidDiagram, setLastValidDiagram] = useState({ nodes: [], edges: [] });
  const [hasError, setHasError] = useState(false);
  const [errorMessage, setErrorMessage] = useState(null);
  const [isTyping, setIsTyping] = useState(false);
  const [isCompiling, setIsCompiling] = useState(false);
  const [diagramName, setDiagramName] = useState('Canvas Diagram');
  const [clipboardStatus, setClipboardStatus] = useState(null);
  const [documentStatus, setDocumentStatus] = useState(null);
  const [isSavingClipboard, setIsSavingClipboard] = useState(false);
  const [isSavingDocument, setIsSavingDocument] = useState(false);
  const [editorOpen, setEditorOpen] = useState(true);

  // Refs for timeouts
  const typingTimeoutRef = useRef(null);
  const compileTimeoutRef = useRef(null);

  const currentWorkspaceId = useWorkspaceStore((state) => state.currentWorkspaceId);
  const currentProjectId = useWorkspaceStore((state) => state.currentProjectId);
  const currentWorkspace = useWorkspaceStore((state) => state.getCurrentWorkspace());

  const { loadClipboardsForWorkspace, addDiagramToClipboard } = useClipboardStore(
    useShallow((state) => ({
      loadClipboardsForWorkspace: state.loadClipboardsForWorkspace,
      addDiagramToClipboard: state.addDiagramToClipboard,
    }))
  );

  const trimmedCode = d2Code.trim();
  const hasDiagramContent = lastValidDiagram.nodes.length > 0 || lastValidDiagram.edges.length > 0;

  // Load from localStorage when project changes
  useEffect(() => {
    // Don't load/save until we have a valid project ID
    if (!currentProjectId) {
      return;
    }

    const storageKey = getStorageKey(currentProjectId);
    const saved = localStorage.getItem(storageKey);
    if (saved) {
      setD2Code(saved);
      // Trigger initial compilation
      compileAndRender(saved);
    } else {
      // Clear canvas when switching to a project with no saved canvas
      setD2Code('');
      setLastValidDiagram({ nodes: [], edges: [] });
      setHasError(false);
      setErrorMessage(null);
    }
  }, [currentProjectId]);

  // Save to localStorage whenever code changes (project-scoped)
  useEffect(() => {
    // Don't save until we have a valid project ID
    if (!currentProjectId) {
      return;
    }

    const storageKey = getStorageKey(currentProjectId);
    if (d2Code) {
      localStorage.setItem(storageKey, d2Code);
    }
  }, [d2Code, currentProjectId]);

  // Load clipboards when workspace changes
  useEffect(() => {
    if (currentWorkspaceId) {
      loadClipboardsForWorkspace(currentWorkspaceId);
    }
  }, [currentWorkspaceId, loadClipboardsForWorkspace]);

  // Update diagram name when workspace changes (only if using default)
  useEffect(() => {
    if (currentWorkspace && currentWorkspace.name) {
      setDiagramName((prev) =>
        !prev || prev === 'Canvas Diagram' ? `${currentWorkspace.name} Diagram` : prev
      );
    }
  }, [currentWorkspaceId, currentWorkspace]);

  // Clear status messages after delay
  useEffect(() => {
    if (!clipboardStatus) return;
    const timeout = setTimeout(() => setClipboardStatus(null), 3000);
    return () => clearTimeout(timeout);
  }, [clipboardStatus]);

  useEffect(() => {
    if (!documentStatus) return;
    const timeout = setTimeout(() => setDocumentStatus(null), 3000);
    return () => clearTimeout(timeout);
  }, [documentStatus]);

  const computeDiagramPreview = useCallback(() => {
    if (!d2Code) {
      return '';
    }
    return d2Code.split('\n').slice(0, 4).join('\n');
  }, [d2Code]);

  // Compilation function
  const compileAndRender = useCallback(async (code) => {
    if (!code.trim()) {
      setLastValidDiagram({ nodes: [], edges: [] });
      setHasError(false);
      setErrorMessage(null);
      setIsCompiling(false);
      return;
    }

    try {
      setIsCompiling(true);
      const result = await compileD2(code);

      // Debug logging - check what's in the compilation result
      console.log('D2 Compilation Result:', result);
      console.log('Has diagram:', !!result.diagram);
      console.log('Diagram connections:', result.diagram?.connections?.length);
      console.log('Graph edges:', result.graph.edges?.length);

      // Use diagram for better edge support (has connections with proper src/dst)
      const { nodes, edges } = result.diagram
        ? convertDiagramToReactFlow(result.diagram)
        : convertD2ToReactFlow(result.graph);

      console.log('Converted nodes:', nodes);
      console.log('Converted edges:', edges);

      setLastValidDiagram({ nodes, edges });
      setHasError(false);
      setErrorMessage(null);
    } catch (error) {
      setHasError(true);
      setErrorMessage(error.message || 'Failed to compile D2 code');
      // Keep lastValidDiagram unchanged - shows last good diagram
    } finally {
      setIsCompiling(false);
    }
  }, []);

  // Debounced compile function
  const debouncedCompile = useMemo(() => {
    return (code) => {
      // Clear existing compile timeout
      if (compileTimeoutRef.current) {
        clearTimeout(compileTimeoutRef.current);
      }

      // Set new timeout
      compileTimeoutRef.current = setTimeout(() => {
        compileAndRender(code);
      }, DEBOUNCE_DELAY);
    };
  }, [compileAndRender]);

  // Handle code change
  const handleCodeChange = (e) => {
    const newCode = e.target.value;
    setD2Code(newCode);
    setIsTyping(true);

    // Clear existing typing timeout
    if (typingTimeoutRef.current) {
      clearTimeout(typingTimeoutRef.current);
    }

    // Set new typing timeout (3 seconds)
    typingTimeoutRef.current = setTimeout(() => {
      setIsTyping(false);
    }, ERROR_DISPLAY_DELAY);

    // Trigger debounced compilation
    debouncedCompile(newCode);
  };

  // Cleanup timeouts on unmount
  useEffect(() => {
    return () => {
      if (typingTimeoutRef.current) {
        clearTimeout(typingTimeoutRef.current);
      }
      if (compileTimeoutRef.current) {
        clearTimeout(compileTimeoutRef.current);
      }
    };
  }, []);

  const handleSaveToClipboard = async () => {
    if (!currentWorkspaceId) {
      setClipboardStatus('Select a workspace to save this diagram to your notepad.');
      return;
    }

    if (!trimmedCode) {
      setClipboardStatus('Add diagram code before saving to your notepad.');
      return;
    }

    setIsSavingClipboard(true);
    setClipboardStatus('Saving to notepad...');
    try {
      await addDiagramToClipboard({
        workspaceId: currentWorkspaceId,
        diagramCode: d2Code,
        diagramName,
        diagramPreview: computeDiagramPreview(),
      });
      setClipboardStatus('Saved to notepad.');
    } catch (error) {
      setClipboardStatus(error.message || 'Failed to save to notepad.');
    } finally {
      setIsSavingClipboard(false);
    }
  };

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
      await api.createD2Document({
        name: diagramName || 'Canvas Diagram',
        description: `Saved from Canvas - ${currentWorkspace?.name || ''}`,
        content: d2Code,
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

  // Determine what to show in diagram pane
  const shouldShowError = hasError && !isTyping;
  const shouldShowWarning = hasError && isTyping;

  const actions = (
    <div className="flex gap-2">
      {trimmedCode && (
        <button className="px-3 py-1.5 text-sm border border-primary text-primary rounded hover:bg-primary hover:text-white transition-colors" onClick={handleSaveToClipboard} disabled={isSavingClipboard}>
          {isSavingClipboard ? 'Saving…' : 'Save to Notepad'}
        </button>
      )}
      <button className="px-3 py-1.5 text-sm bg-primary text-white rounded hover:opacity-90 transition-opacity disabled:opacity-50" onClick={handleSaveAsDocument} disabled={isSavingDocument || !trimmedCode}>
        {isSavingDocument ? 'Saving…' : 'Save as D2 Document'}
      </button>
    </div>
  );

  return (
    <LayoutFrame title={diagramName || 'Canvas'} actions={actions} variant="full" noPadding={true}>
        <div className="relative flex flex-col flex-1 w-full bg-background rounded-lg border border-border overflow-hidden">
          <div className="absolute top-4 left-4 w-[420px] max-w-[90vw] bg-surface border border-border shadow-strong rounded-lg overflow-hidden z-50 pointer-events-auto">
          <div className="flex items-center justify-between bg-background px-3 py-2">
            <div className="flex items-center gap-2">
              <LayoutPanelLeft className="h-4 w-4" />
              <span className="text-sm font-semibold">D2 Code Editor</span>
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
              {(clipboardStatus || documentStatus) && (
                <div className="text-xs text-text-secondary">
                  {clipboardStatus && <div>{clipboardStatus}</div>}
                  {documentStatus && <div className="text-primary">{documentStatus}</div>}
                </div>
              )}
              <textarea
                className="d2-editor"
                value={d2Code}
                onChange={handleCodeChange}
                placeholder="Type your D2 code here...&#10;&#10;Example:&#10;x -> y: hello&#10;y -> z: world"
                spellCheck={false}
              />
              <div className="flex justify-between items-center">
                <input
                  type="text"
                  className="flex-1 px-2 py-1 text-sm border border-border rounded bg-background focus:outline-none focus:ring-2 focus:ring-primary diagram-name-input"
                  placeholder="Diagram name"
                  value={diagramName}
                  onChange={(e) => setDiagramName(e.target.value)}
                />
                {d2Code && (
                  <button
                    className="ml-2 px-2 py-1 text-sm border border-border text-text-secondary rounded hover:bg-background transition-colors"
                    onClick={() => {
                      setD2Code('');
                      setLastValidDiagram({ nodes: [], edges: [] });
                      setHasError(false);
                      setErrorMessage(null);
                      localStorage.removeItem(getStorageKey(currentProjectId));
                    }}
                  >
                    Clear
                  </button>
                )}
              </div>
            </div>
          )}
        </div>

        <div className="flex flex-col flex-1 w-full">
          <div className="flex-1 overflow-auto min-h-0">
            {isCompiling && (
              <div className="absolute top-3 right-3 text-xs text-text-secondary bg-surface border border-border rounded-md px-2 py-1">
                Compiling…
              </div>
            )}
            {shouldShowWarning && (
              <div className="absolute top-3 right-3 text-xs text-orange-500 flex items-center gap-1 bg-surface border border-border rounded-md px-2 py-1">
                <AlertCircle size={14} /> {errorMessage}
              </div>
            )}
            {shouldShowError ? (
              <div className="canvas-error-display">
                <AlertCircle size={48} className="error-icon" />
                <h4>Compilation Error</h4>
                <pre className="error-message">{errorMessage}</pre>
                <p className="error-hint">Fix the errors above to see your diagram.</p>
              </div>
            ) : hasDiagramContent ? (
              <DiagramPreview nodes={lastValidDiagram.nodes} edges={lastValidDiagram.edges} />
            ) : (
              <div className="canvas-empty-state">
                <h4>Start Creating</h4>
                <p>Type D2 code in the editor to see your diagram here.</p>
                <div className="example-hint">
                  <strong>Try this example:</strong>
                  <pre>
{`x -> y: hello
y -> z: world
z -> x: back`}
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

export default CanvasPage;
