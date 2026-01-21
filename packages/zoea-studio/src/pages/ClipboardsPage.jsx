import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { FileText, ImageIcon, MessageSquare, Save } from 'lucide-react';
import { useClipboardStore, useWorkspaceStore } from '../stores';
import { useShallow } from 'zustand/react/shallow';
import LayoutFrame from '../components/layout/LayoutFrame';
import ViewPrimaryActions from '../components/layout/view/ViewPrimaryActions';
import { DocumentRAGModal } from '../components/document-rag';
import YooptaEditor from '../components/documents/YooptaEditor';
import ZoeaContentPickerModal from '../components/documents/ZoeaContentPickerModal';
import SaveAsDocumentModal from '../components/documents/SaveAsDocumentModal';
import {
  createNotebookItemPlugin,
  extractNotebookItemIdsFromYooptaContent,
} from '../config/yooptaClipboardItemPlugin';
import api from '../services/api';

function ClipboardsPage() {
  const navigate = useNavigate();
  const currentProjectId = useWorkspaceStore((state) => state.currentProjectId);
  const currentWorkspaceId = useWorkspaceStore((state) => state.currentWorkspaceId);
  const {
    clipboard,
    items,
    error,
    loadClipboardsForWorkspace,
    ensureClipboard,
    removeClipboardItems,
    notepadDraft,
    notepadDraftLoadedForClipboardId,
    notepadDraftLoading,
    notepadDraftSaving,
    notepadDraftError,
    notepadDraftVersion,
    loadNotepadDraft,
    saveNotepadDraft,
    clearNotepadDraft,
    setNotepadDraftContent,
    addMessageToClipboard,
    addModelToClipboard,
  } = useClipboardStore(
    useShallow((state) => ({
      clipboard: state.clipboard,
      items: state.items,
      error: state.error,
      loadClipboardsForWorkspace: state.loadClipboardsForWorkspace,
      ensureClipboard: state.ensureClipboard,
      removeClipboardItems: state.removeClipboardItems,
      notepadDraft: state.notepadDraft,
      notepadDraftLoadedForClipboardId: state.notepadDraftLoadedForClipboardId,
      notepadDraftLoading: state.notepadDraftLoading,
      notepadDraftSaving: state.notepadDraftSaving,
      notepadDraftError: state.notepadDraftError,
      notepadDraftVersion: state.notepadDraftVersion,
      loadNotepadDraft: state.loadNotepadDraft,
      saveNotepadDraft: state.saveNotepadDraft,
      clearNotepadDraft: state.clearNotepadDraft,
      setNotepadDraftContent: state.setNotepadDraftContent,
      addMessageToClipboard: state.addMessageToClipboard,
      addModelToClipboard: state.addModelToClipboard,
    }))
  );

  const [ragModalOpen, setRagModalOpen] = useState(false);
  const [contentPickerOpen, setContentPickerOpen] = useState(false);
  const [saveAsDocModalOpen, setSaveAsDocModalOpen] = useState(false);
  const [draftClipboardId, setDraftClipboardId] = useState(null);
  const [draftContent, setDraftContent] = useState(undefined);
  const [draftDirty, setDraftDirty] = useState(false);
  const [draftStatus, setDraftStatus] = useState(null);
  const savedEmbeddedItemIdsRef = useRef(new Set());
  const lastSyncedVersionRef = useRef(0);
  const editorRef = useRef(null);
  const autoSaveTimerRef = useRef(null);
  const pendingSaveRef = useRef(null);

  useEffect(() => {
    if (currentWorkspaceId) {
      ensureClipboard(currentWorkspaceId);
    }
  }, [currentWorkspaceId, ensureClipboard]);

  useEffect(() => {
    if (!clipboard?.id) {
      setDraftClipboardId(null);
      setDraftContent(undefined);
      setDraftDirty(false);
      setDraftStatus(null);
      savedEmbeddedItemIdsRef.current = new Set();
      return;
    }

    if (draftClipboardId !== clipboard.id) {
      setDraftClipboardId(null);
      setDraftContent(undefined);
      setDraftDirty(false);
      setDraftStatus(null);
      savedEmbeddedItemIdsRef.current = new Set();
    }

    loadNotepadDraft(clipboard.id);
  }, [clipboard?.id, draftClipboardId, loadNotepadDraft]);

  // Initial sync: load draft from store into local state when first arriving at page
  useEffect(() => {
    if (!clipboard?.id) return;
    if (notepadDraftLoadedForClipboardId !== clipboard.id) return;
    if (draftClipboardId === clipboard.id) return;

    setDraftClipboardId(clipboard.id);
    setDraftContent(notepadDraft ?? undefined);
    setDraftDirty(false);
    setDraftStatus(null);
    savedEmbeddedItemIdsRef.current = extractNotebookItemIdsFromYooptaContent(notepadDraft);
    lastSyncedVersionRef.current = notepadDraftVersion;
  }, [
    clipboard?.id,
    draftClipboardId,
    notepadDraft,
    notepadDraftLoadedForClipboardId,
    notepadDraftVersion,
  ]);

  // External update sync: when notepadDraft changes externally (e.g., item added from another page),
  // update local draftContent. If user has unsaved changes, append new blocks to preserve their edits.
  useEffect(() => {
    // Only run after initial sync is complete
    if (draftClipboardId !== clipboard?.id) return;
    if (notepadDraftLoadedForClipboardId !== clipboard?.id) return;
    // Skip if this is the same version we already synced
    if (notepadDraftVersion === lastSyncedVersionRef.current) return;

    lastSyncedVersionRef.current = notepadDraftVersion;

    if (!draftDirty) {
      // No local changes - just replace with store content
      setDraftContent(notepadDraft ?? undefined);
      savedEmbeddedItemIdsRef.current = extractNotebookItemIdsFromYooptaContent(notepadDraft);
    } else {
      // User has local changes - merge by finding new NotebookItem blocks and appending them
      const currentIds = extractNotebookItemIdsFromYooptaContent(draftContent);
      const newIds = extractNotebookItemIdsFromYooptaContent(notepadDraft);
      const addedIds = [...newIds].filter((id) => !currentIds.has(id));

      if (addedIds.length > 0 && notepadDraft && typeof notepadDraft === 'object') {
        // Find the new NotebookItem blocks and append them to local content
        const newBlocks = {};
        for (const [blockId, block] of Object.entries(notepadDraft)) {
          if (block?.type === 'NotebookItem') {
            const itemId = block?.value?.[0]?.props?.notebook_item_id;
            if (addedIds.includes(itemId)) {
              newBlocks[blockId] = block;
            }
          }
        }
        if (Object.keys(newBlocks).length > 0) {
          setDraftContent((prev) => ({ ...prev, ...newBlocks }));
          setDraftStatus('New items added');
        }
      }
    }
  }, [clipboard?.id, draftClipboardId, draftContent, draftDirty, notepadDraft, notepadDraftLoadedForClipboardId, notepadDraftVersion]);

  const normalizeDraftContent = useMemo(() => {
    if (!draftContent || typeof draftContent !== 'object') {
      return null;
    }
    return Object.keys(draftContent).length > 0 ? draftContent : null;
  }, [draftContent]);

  // Auto-save: debounce saving draft after 2 seconds of inactivity
  useEffect(() => {
    if (!clipboard?.id || !draftDirty || notepadDraftSaving) {
      return;
    }

    // Clear any existing timer
    if (autoSaveTimerRef.current) {
      clearTimeout(autoSaveTimerRef.current);
    }

    // Store the content to save (captured at this moment)
    const contentToSave = normalizeDraftContent;
    const clipboardIdToSave = clipboard.id;

    autoSaveTimerRef.current = setTimeout(async () => {
      try {
        pendingSaveRef.current = saveNotepadDraft(clipboardIdToSave, contentToSave);
        await pendingSaveRef.current;
        setDraftDirty(false);
      } catch (err) {
        console.error('Auto-save failed:', err);
      } finally {
        pendingSaveRef.current = null;
      }
    }, 2000);

    return () => {
      if (autoSaveTimerRef.current) {
        clearTimeout(autoSaveTimerRef.current);
      }
    };
  }, [clipboard?.id, draftDirty, normalizeDraftContent, notepadDraftSaving, saveNotepadDraft]);

  // Save immediately when visibility changes (tab switch) to prevent data loss
  useEffect(() => {
    const handleVisibilityChange = async () => {
      if (document.visibilityState === 'hidden' && draftDirty && clipboard?.id && !notepadDraftSaving) {
        // Cancel pending auto-save timer and save immediately
        if (autoSaveTimerRef.current) {
          clearTimeout(autoSaveTimerRef.current);
          autoSaveTimerRef.current = null;
        }
        try {
          await saveNotepadDraft(clipboard.id, normalizeDraftContent);
          setDraftDirty(false);
        } catch (err) {
          console.error('Save on visibility change failed:', err);
        }
      }
    };

    document.addEventListener('visibilitychange', handleVisibilityChange);
    return () => document.removeEventListener('visibilitychange', handleVisibilityChange);
  }, [draftDirty, clipboard?.id, normalizeDraftContent, notepadDraftSaving, saveNotepadDraft]);

  // Track current save state in refs for cleanup
  const draftDirtyRef = useRef(draftDirty);
  const clipboardIdRef = useRef(clipboard?.id);
  const contentRef = useRef(normalizeDraftContent);

  useEffect(() => {
    draftDirtyRef.current = draftDirty;
    clipboardIdRef.current = clipboard?.id;
    contentRef.current = normalizeDraftContent;
  }, [draftDirty, clipboard?.id, normalizeDraftContent]);

  // Cleanup timers and save on unmount
  useEffect(() => {
    return () => {
      if (autoSaveTimerRef.current) {
        clearTimeout(autoSaveTimerRef.current);
      }
      // Fire-and-forget save on unmount if there are dirty changes
      if (draftDirtyRef.current && clipboardIdRef.current) {
        const savePromise = saveNotepadDraft(clipboardIdRef.current, contentRef.current);
        if (savePromise?.catch) {
          savePromise.catch((err) => {
            console.error('Save on unmount failed:', err);
          });
        }
      }
    };
  }, [saveNotepadDraft]);

  const handleDraftChange = (nextValue) => {
    setDraftContent(nextValue);
    setDraftDirty(true);
    // Sync to store so items added from other pages include our edits
    if (clipboard?.id) {
      setNotepadDraftContent(clipboard.id, nextValue);
    }
  };

  const saveDraftOrThrow = async () => {
    if (!clipboard?.id) {
      throw new Error('No active notebook for this workspace.');
    }

    await saveNotepadDraft(clipboard.id, normalizeDraftContent);

    const nextEmbeddedIds = extractNotebookItemIdsFromYooptaContent(normalizeDraftContent);
    const removedIds = Array.from(savedEmbeddedItemIdsRef.current).filter(
      (id) => !nextEmbeddedIds.has(id)
    );
    if (removedIds.length > 0) {
      await removeClipboardItems(clipboard.id, removedIds);
    }

    savedEmbeddedItemIdsRef.current = nextEmbeddedIds;
    setDraftDirty(false);
  };

  const handleSaveDraft = async () => {
    setDraftStatus(null);
    try {
      setDraftStatus('Saving…');
      await saveDraftOrThrow();
      setDraftStatus('Saved');
    } catch (err) {
      setDraftStatus(err?.message || 'Failed to save notebook draft.');
    }
  };

  const handleClearDraft = async () => {
    if (!clipboard?.id) return;
    const itemCount = items.length;
    const message = itemCount > 0
      ? `Clear this notebook draft and all ${itemCount} notebook item${itemCount === 1 ? '' : 's'}? This cannot be undone.`
      : 'Clear this notebook draft? This cannot be undone.';
    const ok = window.confirm(message);
    if (!ok) return;

    setDraftStatus(null);
    try {
      setDraftStatus('Clearing…');
      await clearNotepadDraft(clipboard.id);

      // Also clear all clipboard items
      if (itemCount > 0) {
        const itemIds = items.map((item) => item.id);
        await removeClipboardItems(clipboard.id, itemIds);
      }

      setDraftContent(undefined);
      setDraftDirty(false);
      savedEmbeddedItemIdsRef.current = new Set();
      setDraftStatus('Cleared');
    } catch (err) {
      setDraftStatus(err?.message || 'Failed to clear notebook.');
    }
  };

  const handleOpenSaveAsDoc = () => {
    if (!clipboard?.id) {
      setDraftStatus('No active notebook for this workspace.');
      return;
    }
    setSaveAsDocModalOpen(true);
  };

  const handleSaveAsDocument = async ({ name, folder_id }) => {
    if (!clipboard?.id) {
      throw new Error('No active notebook for this workspace.');
    }

    setDraftStatus(null);
    if (draftDirty) {
      setDraftStatus('Saving draft…');
      await saveDraftOrThrow();
    }

    setDraftStatus('Creating document…');
    const response = await api.saveClipboardAsDocument(clipboard.id, {
      name,
      folder_id,
    });
    navigate(`/documents/${response.document_id}`);
  };

  const resolveClipboardItem = useCallback(
    (clipboardItemId) => {
      const parsed = Number.parseInt(String(clipboardItemId), 10);
      if (!Number.isFinite(parsed)) return null;
      return items.find((item) => item.id === parsed) ?? null;
    },
    [items]
  );

  const handleOpenClipboardItem = useCallback(
    (item) => {
      if (!item || typeof item !== 'object') return;

      if (item.content_type === 'documents.document' && item.object_id) {
        navigate(`/documents/${item.object_id}`);
        return;
      }

      if (item.source_metadata?.diagram_code) {
        navigate('/canvas/d2');
      }
    },
    [navigate]
  );

  const notepadPlugins = useMemo(
    () => [
      createNotebookItemPlugin({
        resolveNotebookItem: resolveClipboardItem,
        onOpenNotebookItem: handleOpenClipboardItem,
      }),
    ],
    [handleOpenClipboardItem, resolveClipboardItem]
  );

  const handleChatWithClipboard = () => {
    if (!clipboard?.id) {
      alert('No notebook available to chat with.');
      return;
    }
    if (items.length === 0) {
      alert('Notebook is empty. Add some items first.');
      return;
    }
    setRagModalOpen(true);
  };

  const handleContentSelect = useCallback(
    async (selection) => {
      if (!currentWorkspaceId) return;

      setDraftStatus('Adding content...');
      try {
        if (selection.contentType === 'message') {
          await addMessageToClipboard({
            workspaceId: currentWorkspaceId,
            text: selection.text,
            preview: selection.metadata?.preview,
            metadata: selection.metadata,
          });
        } else {
          await addModelToClipboard({
            workspaceId: currentWorkspaceId,
            contentType: selection.contentType,
            objectId: selection.objectId,
            metadata: selection.metadata,
          });
        }
        setDraftStatus('Content added');
      } catch (err) {
        console.error('Failed to add content:', err);
        setDraftStatus('Failed to add content');
      }
    },
    [currentWorkspaceId, addMessageToClipboard, addModelToClipboard]
  );

  const actions = clipboard ? (
    <ViewPrimaryActions>
      <ViewPrimaryActions.Button
        variant="outline"
        onClick={() => editorRef.current?.openImagePicker()}
        disabled={!clipboard?.id || notepadDraftSaving || notepadDraftLoading}
        title="Insert image from library"
      >
        <span className="flex items-center gap-2">
          <ImageIcon className="h-4 w-4" />
          <span>Insert from Library</span>
        </span>
      </ViewPrimaryActions.Button>
      <ViewPrimaryActions.Button
        variant="outline"
        onClick={handleSaveDraft}
        disabled={!clipboard?.id || notepadDraftSaving || notepadDraftLoading}
        title="Save notebook draft"
      >
        <span className="flex items-center gap-2">
          <Save className="h-4 w-4" />
          <span>Save</span>
        </span>
      </ViewPrimaryActions.Button>
      <ViewPrimaryActions.Button
        variant="outline"
        onClick={handleOpenSaveAsDoc}
        disabled={!clipboard?.id || notepadDraftSaving || notepadDraftLoading}
        title="Save as shared document"
      >
        <span className="flex items-center gap-2">
          <FileText className="h-4 w-4" />
          <span>Save as Document</span>
        </span>
      </ViewPrimaryActions.Button>
      <ViewPrimaryActions.Button
        variant="ghost"
        onClick={handleClearDraft}
        disabled={!clipboard?.id || notepadDraftSaving || notepadDraftLoading}
        title="Clear notebook draft"
      >
        Clear
      </ViewPrimaryActions.Button>
      {items.length > 0 && (
        <ViewPrimaryActions.Button
          variant="outline"
          onClick={handleChatWithClipboard}
          title="Chat with notebook items"
        >
          <MessageSquare className="h-4 w-4" />
        </ViewPrimaryActions.Button>
      )}
    </ViewPrimaryActions>
  ) : null;

  const content = currentWorkspaceId ? (
    <>
      {(notepadDraftError || error) && (
        <div
          className="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded"
          role="alert"
        >
          {notepadDraftError || error}
        </div>
      )}
      {clipboard && draftClipboardId === clipboard.id ? (
        <YooptaEditor
          ref={editorRef}
          key={draftClipboardId}
          value={draftContent}
          onChange={handleDraftChange}
          placeholder="Start a private note…"
          className="h-full"
          projectId={currentProjectId}
          workspaceId={currentWorkspaceId}
          extraPlugins={notepadPlugins}
          hideImageLibraryButton
        />
      ) : clipboard ? (
        <div className="text-sm text-text-secondary flex items-center gap-2">
          <span className="animate-pulse">Loading notebook...</span>
        </div>
      ) : (
        <div className="text-sm text-text-secondary">
          Create a notebook to start writing.
        </div>
      )}
    </>
  ) : (
    <div className="bg-blue-100 border border-blue-400 text-blue-700 px-4 py-3 rounded mt-3" role="alert">
      Choose a project and workspace from the sidebar to view notebooks.
    </div>
  );

  return (
    <>
      <LayoutFrame title="Notebook" actions={actions} variant="content-centered">
        {content}
      </LayoutFrame>
      <DocumentRAGModal
        isOpen={ragModalOpen}
        onClose={() => setRagModalOpen(false)}
        contextType="notebook"
        contextId={clipboard?.id}
        contextName="Notebook Items"
      />
      <ZoeaContentPickerModal
        isOpen={contentPickerOpen}
        onClose={() => setContentPickerOpen(false)}
        onSelect={handleContentSelect}
        projectId={currentProjectId}
        workspaceId={currentWorkspaceId}
      />
      <SaveAsDocumentModal
        isOpen={saveAsDocModalOpen}
        onClose={() => setSaveAsDocModalOpen(false)}
        onSave={handleSaveAsDocument}
        workspaceId={currentWorkspaceId}
        defaultName={clipboard?.name ? `${clipboard.name} (Notepad)` : 'Notepad'}
      />
    </>
  );
}

export default ClipboardsPage;
