/**
 * Excalidraw Canvas Page
 *
 * Full-screen Excalidraw canvas for freehand drawing and diagramming.
 * Features localStorage persistence, save to documents, and image export.
 */

import { useState, useEffect, useRef, useCallback } from 'react';
import { Save, Download, Trash2 } from 'lucide-react';
import ExcalidrawEditor, { getSceneData, exportToPng } from '../components/ExcalidrawEditor';
import LayoutFrame from '../components/layout/LayoutFrame';
import RecentCanvasDocuments from '../components/excalidraw/RecentCanvasDocuments';
import { useWorkspaceStore } from '../stores';
import api from '../services/api';

const LOCALSTORAGE_KEY_PREFIX = 'zoea-canvas-excalidraw';

// Generate project-scoped localStorage key
const getStorageKey = (projectId) =>
  projectId ? `${LOCALSTORAGE_KEY_PREFIX}-${projectId}` : LOCALSTORAGE_KEY_PREFIX;

function ExcalidrawCanvasPage() {
  const [canvasName, setCanvasName] = useState('Untitled Canvas');
  const [saveStatus, setSaveStatus] = useState(null);
  const [isSaving, setIsSaving] = useState(false);
  const [isExporting, setIsExporting] = useState(false);
  const [initialData, setInitialData] = useState(null);
  const [hasUnsavedChanges, setHasUnsavedChanges] = useState(false);
  const [loadedDocumentId, setLoadedDocumentId] = useState(null);

  const excalidrawAPIRef = useRef(null);
  const currentProjectId = useWorkspaceStore((state) => state.currentProjectId);
  const currentWorkspaceId = useWorkspaceStore((state) => state.currentWorkspaceId);
  const currentWorkspace = useWorkspaceStore((state) => state.getCurrentWorkspace());

  // Load from localStorage when project changes
  useEffect(() => {
    if (!currentProjectId) return;

    const storageKey = getStorageKey(currentProjectId);
    const saved = localStorage.getItem(storageKey);

    if (saved) {
      try {
        const parsed = JSON.parse(saved);
        setInitialData(parsed.sceneData || null);
        setCanvasName(parsed.name || 'Untitled Canvas');
      } catch (e) {
        console.error('Failed to parse saved canvas data:', e);
        setInitialData(null);
        setCanvasName('Untitled Canvas');
      }
    } else {
      setInitialData(null);
      setCanvasName('Untitled Canvas');
    }
    setHasUnsavedChanges(false);
  }, [currentProjectId]);

  // Update canvas name when workspace changes
  useEffect(() => {
    if (currentWorkspace?.name && canvasName === 'Untitled Canvas') {
      setCanvasName(`${currentWorkspace.name} Canvas`);
    }
  }, [currentWorkspace, canvasName]);

  // Clear status message after delay
  useEffect(() => {
    if (!saveStatus) return;
    const timeout = setTimeout(() => setSaveStatus(null), 3000);
    return () => clearTimeout(timeout);
  }, [saveStatus]);

  // Handle data changes from Excalidraw
  const handleDataChange = useCallback(
    (sceneData) => {
      if (!currentProjectId) return;

      // Save to localStorage
      const storageKey = getStorageKey(currentProjectId);
      const dataToSave = {
        name: canvasName,
        sceneData,
        updatedAt: new Date().toISOString(),
      };
      localStorage.setItem(storageKey, JSON.stringify(dataToSave));
      setHasUnsavedChanges(true);
    },
    [currentProjectId, canvasName]
  );

  // Store the Excalidraw API reference
  const handleExcalidrawRef = useCallback((api) => {
    excalidrawAPIRef.current = api;
  }, []);

  // Save as document
  const handleSaveAsDocument = async () => {
    if (!currentWorkspaceId || !currentProjectId) {
      setSaveStatus('Select a project and workspace to save.');
      return;
    }

    if (!excalidrawAPIRef.current) {
      setSaveStatus('Canvas not ready. Please try again.');
      return;
    }

    const sceneData = getSceneData(excalidrawAPIRef.current);
    if (!sceneData || !sceneData.elements || sceneData.elements.length === 0) {
      setSaveStatus('Add some content to the canvas before saving.');
      return;
    }

    setIsSaving(true);
    setSaveStatus('Saving as document...');

    try {
      await api.createExcalidrawDocument({
        name: canvasName || 'Excalidraw Canvas',
        description: `Saved from Canvas - ${currentWorkspace?.name || ''}`,
        content: JSON.stringify(sceneData),
        project_id: currentProjectId,
        workspace_id: currentWorkspaceId,
      });
      setSaveStatus('Saved to Documents!');
      setHasUnsavedChanges(false);
    } catch (error) {
      setSaveStatus(error.message || 'Failed to save document.');
    } finally {
      setIsSaving(false);
    }
  };

  // Export as image
  const handleExportAsImage = async () => {
    if (!currentWorkspaceId || !currentProjectId) {
      setSaveStatus('Select a project and workspace to export.');
      return;
    }

    if (!excalidrawAPIRef.current) {
      setSaveStatus('Canvas not ready. Please try again.');
      return;
    }

    const elements = excalidrawAPIRef.current.getSceneElements();
    if (!elements || elements.length === 0) {
      setSaveStatus('Add some content before exporting.');
      return;
    }

    setIsExporting(true);
    setSaveStatus('Exporting as image...');

    try {
      const blob = await exportToPng(excalidrawAPIRef.current, {
        backgroundColor: '#ffffff',
      });

      if (!blob) {
        throw new Error('Failed to generate image');
      }

      // Create a File object from the blob
      const file = new File([blob], `${canvasName || 'canvas'}.png`, {
        type: 'image/png',
      });

      // Upload as image document
      await api.createImageDocument({
        name: `${canvasName || 'Canvas'} Export`,
        description: `Exported from Excalidraw Canvas`,
        project_id: currentProjectId,
        workspace_id: currentWorkspaceId,
        file,
      });

      setSaveStatus('Image exported to Documents!');
    } catch (error) {
      setSaveStatus(error.message || 'Failed to export image.');
    } finally {
      setIsExporting(false);
    }
  };

  // Clear canvas
  const handleClearCanvas = () => {
    if (!currentProjectId) return;

    if (!confirm('Clear the canvas? This cannot be undone.')) return;

    const storageKey = getStorageKey(currentProjectId);
    localStorage.removeItem(storageKey);

    // Reset state
    setInitialData({ elements: [], appState: {}, files: {} });
    setCanvasName('Untitled Canvas');
    setHasUnsavedChanges(false);
    setLoadedDocumentId(null);
    setSaveStatus('Canvas cleared.');
  };

  // Load a document from the sidebar
  const handleDocumentSelect = useCallback((doc) => {
    if (!doc) return;

    // Warn about unsaved changes
    if (hasUnsavedChanges) {
      if (!confirm('You have unsaved changes. Load this document anyway?')) {
        return;
      }
    }

    try {
      // Parse the content JSON
      const sceneData = doc.content ? JSON.parse(doc.content) : null;

      if (sceneData) {
        setInitialData(sceneData);
        setCanvasName(doc.name || 'Loaded Canvas');
        setLoadedDocumentId(doc.id);
        setHasUnsavedChanges(false);
        setSaveStatus(`Loaded "${doc.name}"`);
      } else {
        setSaveStatus('Document has no content.');
      }
    } catch (err) {
      console.error('Failed to parse document content:', err);
      setSaveStatus('Failed to load document.');
    }
  }, [hasUnsavedChanges]);

  const actions = (
    <div className="flex items-center gap-2">
      {saveStatus && (
        <span className="text-xs text-text-secondary">{saveStatus}</span>
      )}
      <input
        type="text"
        className="w-[180px] px-2 py-1 text-sm border border-border rounded bg-background focus:outline-none focus:ring-2 focus:ring-primary"
        placeholder="Canvas name"
        value={canvasName}
        onChange={(e) => setCanvasName(e.target.value)}
      />
      <button
        className="px-2 py-1.5 text-sm border border-border text-text-secondary rounded hover:bg-background transition-colors"
        onClick={handleClearCanvas}
        title="Clear canvas"
      >
        <Trash2 className="h-4 w-4" />
      </button>
      <button
        className="px-2 py-1.5 text-sm border border-primary text-primary rounded hover:bg-primary hover:text-white transition-colors disabled:opacity-50"
        onClick={handleExportAsImage}
        disabled={isExporting}
        title="Export as image"
      >
        <Download className="h-4 w-4" />
      </button>
      <button
        className="px-2 py-1.5 text-sm bg-primary text-white rounded hover:opacity-90 transition-opacity disabled:opacity-50 flex items-center"
        onClick={handleSaveAsDocument}
        disabled={isSaving}
        title="Save as document"
      >
        <Save className="h-4 w-4" />
        <span className="ml-1">Save</span>
      </button>
    </div>
  );

  const sidebar = (
    <RecentCanvasDocuments onDocumentSelect={handleDocumentSelect} />
  );

  return (
    <LayoutFrame
      title={canvasName || 'Canvas'}
      actions={actions}
      sidebar={sidebar}
      viewSidebarTitle="Canvas"
      variant="full"
      noPadding={true}
    >
      <div className="flex flex-col flex-1 w-full h-full min-h-0">
        <ExcalidrawEditor
          initialData={initialData}
          onDataChange={handleDataChange}
          excalidrawRef={handleExcalidrawRef}
          readOnly={false}
        />
      </div>
    </LayoutFrame>
  );
}

export default ExcalidrawCanvasPage;
