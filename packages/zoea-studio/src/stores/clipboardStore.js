/**
 * Clipboard Store (Notebook Backend)
 *
 * Manages notebooks for the active workspace.
 * Note: This store maintains "clipboard" naming in the interface for backward
 * compatibility while using the new notebook API endpoints.
 */

import { create } from 'zustand';
import api from '../services/api';
import { generateId } from '@yoopta/editor';

const normalizeDiagramSignature = (code = '') => code.trim();

const buildDiagramMetadata = ({ diagramCode, diagramName, diagramPreview }) => ({
  diagram_signature: normalizeDiagramSignature(diagramCode),
  diagram_name: diagramName,
  preview: diagramPreview,
  diagram_code: diagramCode,
  source: 'canvas',
});

const buildNotebookItemEmbedBlock = ({ notebookItemId, order }) => {
  const blockId = `block-${generateId()}`;
  const elemId = `elem-${generateId()}`;

  return {
    id: blockId,
    meta: { order },
    type: 'NotebookItem',
    value: [
      {
        id: elemId,
        type: 'notebookitem',
        props: {
          nodeType: 'void',
          notebook_item_id: notebookItemId,
        },
        children: [{ text: '' }],
      },
    ],
  };
};

const appendNotebookItemEmbedBlock = (content, notebookItemId) => {
  const normalizedContent = content && typeof content === 'object' ? content : {};

  let nextOrder = 0;
  for (const block of Object.values(normalizedContent)) {
    const order = Number.parseInt(String(block?.meta?.order ?? ''), 10);
    if (Number.isFinite(order) && order >= nextOrder) {
      nextOrder = order + 1;
    }
  }

  const block = buildNotebookItemEmbedBlock({ notebookItemId, order: nextOrder });
  return {
    ...normalizedContent,
    [block.id]: block,
  };
};

const initialState = {
  clipboard: null,
  items: [],
  loading: false,
  error: null,
  lastWorkspaceId: null,
  notepadDraft: null,
  notepadDraftLoadedForClipboardId: null,
  notepadDraftLoading: false,
  notepadDraftSaving: false,
  notepadDraftError: null,
  // Tracks the last-known content version to detect external updates
  notepadDraftVersion: 0,
};

export const useClipboardStore = create((set, get) => ({
  ...initialState,

  reset: () => set(initialState),

  loadClipboardsForWorkspace: async (workspaceId) => {
    if (!workspaceId) {
      set({ ...initialState });
      return;
    }

    // Reset clipboard/items but NOT notepad draft state - notepad draft is loaded
    // separately by loadNotepadDraft to avoid race conditions on page refresh
    set({
      loading: true,
      error: null,
      lastWorkspaceId: workspaceId,
      clipboard: null,
      items: [],
    });
    try {
      const response = await api.fetchNotebooks({ workspace_id: workspaceId });
      const notebooks = response.notebooks || [];
      const clipboard = notebooks[0] || null;

      const itemsResponse = clipboard
        ? await api.fetchNotebookItems(clipboard.id)
        : { items: [] };

      // Only update clipboard/items state - notepad draft is loaded separately
      // to avoid race conditions on page refresh
      set({
        clipboard,
        items: itemsResponse.items || [],
        loading: false,
        error: null,
      });
    } catch (error) {
      console.error('Failed to load notebooks', error);
      set({ error: error.message, loading: false });
    }
  },

  refreshClipboardItems: async (clipboardId) => {
    if (!clipboardId) return;
    try {
      const data = await api.fetchNotebookItems(clipboardId);
      set({ items: data.items || [] });
    } catch (error) {
      console.error('Failed to refresh notebook items', error);
      set({ error: error.message });
      throw error;
    }
  },

  loadNotepadDraft: async (clipboardId) => {
    if (!clipboardId) return;

    const state = get();
    if (state.notepadDraftLoading) return;
    if (state.notepadDraftLoadedForClipboardId === clipboardId) return;

    set({
      notepadDraftLoading: true,
      notepadDraftError: null,
      notepadDraftLoadedForClipboardId: null,
      notepadDraft: null,
    });

    try {
      const response = await api.fetchNotebookNotepadDraft(clipboardId);
      set((state) => ({
        notepadDraft: response.content ?? null,
        notepadDraftLoadedForClipboardId: clipboardId,
        notepadDraftLoading: false,
        notepadDraftError: null,
        notepadDraftVersion: state.notepadDraftVersion + 1,
      }));
    } catch (error) {
      console.error('Failed to load notepad draft', error);
      set({
        notepadDraftLoading: false,
        notepadDraftError: error.message,
        notepadDraftLoadedForClipboardId: null,
      });
    }
  },

  saveNotepadDraft: async (clipboardId, content) => {
    if (!clipboardId) {
      throw new Error('clipboardId is required to save notepad draft');
    }

    set({ notepadDraftSaving: true, notepadDraftError: null });
    try {
      const response = await api.putNotebookNotepadDraft(clipboardId, { content });
      set((state) => ({
        notepadDraft: response.content ?? null,
        notepadDraftLoadedForClipboardId: clipboardId,
        notepadDraftSaving: false,
        notepadDraftError: null,
        notepadDraftVersion: state.notepadDraftVersion + 1,
      }));
      return response.content ?? null;
    } catch (error) {
      console.error('Failed to save notepad draft', error);
      set({ notepadDraftSaving: false, notepadDraftError: error.message });
      throw error;
    }
  },

  clearNotepadDraft: async (clipboardId) => {
    if (!clipboardId) return;

    set({ notepadDraftSaving: true, notepadDraftError: null });
    try {
      await api.deleteNotebookNotepadDraft(clipboardId);
      set((state) => ({
        notepadDraft: null,
        notepadDraftLoadedForClipboardId: clipboardId,
        notepadDraftSaving: false,
        notepadDraftError: null,
        notepadDraftVersion: state.notepadDraftVersion + 1,
      }));
    } catch (error) {
      console.error('Failed to clear notepad draft', error);
      set({ notepadDraftSaving: false, notepadDraftError: error.message });
      throw error;
    }
  },

  // Update notepad draft in store without saving to backend.
  // Used by ClipboardsPage to keep store in sync with local edits so that
  // items added from other pages include the user's unsaved work.
  setNotepadDraftContent: (clipboardId, content) => {
    const state = get();
    if (state.notepadDraftLoadedForClipboardId !== clipboardId) return;
    set({ notepadDraft: content });
  },

  createClipboard: async (workspaceId) => {
    if (!workspaceId) {
      throw new Error('Workspace is required to create a notebook');
    }

    const payload = {
      workspace_id: workspaceId,
      name: 'Notebook',
      description: 'Private notebook for this workspace',
      activate: true,
    };

    try {
      await api.createNotebook(payload);
      await get().loadClipboardsForWorkspace(workspaceId);
    } catch (error) {
      console.error('Failed to create notebook', error);
      set({ error: error.message });
      throw error;
    }
  },

  ensureClipboard: async (workspaceId) => {
    if (!workspaceId) {
      throw new Error('Workspace is required to manage notebooks');
    }

    const state = get();
    if (state.lastWorkspaceId !== workspaceId) {
      await get().loadClipboardsForWorkspace(workspaceId);
    }

    const existing = get().clipboard;
    if (existing) {
      return existing;
    }

    await get().createClipboard(workspaceId);
    return get().clipboard;
  },

  appendClipboardItemToNotepadDraft: async (clipboardId, notebookItemId) => {
    if (!clipboardId || !notebookItemId) return null;

    const state = get();
    let currentContent = null;

    if (state.notepadDraftLoadedForClipboardId === clipboardId) {
      currentContent = state.notepadDraft;
    } else {
      const response = await api.fetchNotebookNotepadDraft(clipboardId);
      currentContent = response.content ?? null;
    }

    const nextContent = appendNotebookItemEmbedBlock(currentContent, notebookItemId);
    await get().saveNotepadDraft(clipboardId, nextContent);
    return nextContent;
  },

  addMessageToClipboard: async ({ workspaceId, text, preview, metadata = {} }) => {
    if (!text) {
      return;
    }

    const clipboard = await get().ensureClipboard(workspaceId);
    if (!clipboard) {
      throw new Error('Unable to find or create a notebook');
    }

    // Use provided preview or create text snippet fallback
    const textPreview = text.length > 180 ? `${text.slice(0, 177)}...` : text;
    const finalPreview = preview || textPreview;

    try {
      const response = await api.addNotebookItem(clipboard.id, {
        direction: 'right',
        source_channel: 'message',
        preview: finalPreview,
        source_metadata: {
          preview: textPreview,
          full_text: text,
          ...metadata,
        },
      });

      const createdItemId = response?.item?.id;
      if (createdItemId) {
        try {
          await get().appendClipboardItemToNotepadDraft(clipboard.id, createdItemId);
        } catch (error) {
          try {
            await api.deleteNotebookItem(clipboard.id, createdItemId);
          } catch (rollbackError) {
            console.warn('Failed to rollback notebook item after notepad draft update', rollbackError);
          }
          throw error;
        }
      }
      await get().refreshClipboardItems(clipboard.id);
    } catch (error) {
      console.error('Failed to add notebook item', error);
      set({ error: error.message });
      throw error;
    }
  },

  addModelToClipboard: async ({
    workspaceId,
    contentType,
    objectId,
    sourceChannel = 'document',
    metadata = {},
  }) => {
    if (!contentType || !objectId) {
      throw new Error('contentType and objectId are required');
    }

    const clipboard = await get().ensureClipboard(workspaceId);
    if (!clipboard) {
      throw new Error('Unable to find or create a notebook');
    }

    try {
      const response = await api.addNotebookItem(clipboard.id, {
        direction: 'right',
        content_type: contentType,
        object_id: objectId.toString(),
        source_channel: sourceChannel,
        source_metadata: metadata,
      });

      const createdItemId = response?.item?.id;
      if (createdItemId) {
        try {
          await get().appendClipboardItemToNotepadDraft(clipboard.id, createdItemId);
        } catch (error) {
          try {
            await api.deleteNotebookItem(clipboard.id, createdItemId);
          } catch (rollbackError) {
            console.warn('Failed to rollback notebook item after notepad draft update', rollbackError);
          }
          throw error;
        }
      }
      await get().refreshClipboardItems(clipboard.id);
    } catch (error) {
      console.error('Failed to add model to notebook', error);
      set({ error: error.message });
      throw error;
    }
  },

  addDiagramToClipboard: async ({
    workspaceId,
    diagramCode,
    diagramName,
    diagramPreview,
  }) => {
    const signature = normalizeDiagramSignature(diagramCode);
    if (!workspaceId || !signature) {
      throw new Error('Diagram content is required to save to notebook');
    }

    const clipboard = await get().ensureClipboard(workspaceId);
    if (!clipboard) {
      throw new Error('Unable to find or create a notebook');
    }

    try {
      const response = await api.addNotebookItem(clipboard.id, {
        direction: 'right',
        source_channel: 'canvas',
        source_metadata: buildDiagramMetadata({
          diagramCode,
          diagramName,
          diagramPreview,
        }),
      });

      const createdItemId = response?.item?.id;
      if (createdItemId) {
        try {
          await get().appendClipboardItemToNotepadDraft(clipboard.id, createdItemId);
        } catch (error) {
          try {
            await api.deleteNotebookItem(clipboard.id, createdItemId);
          } catch (rollbackError) {
            console.warn('Failed to rollback notebook item after notepad draft update', rollbackError);
          }
          throw error;
        }
      }
      await get().refreshClipboardItems(clipboard.id);
    } catch (error) {
      console.error('Failed to add diagram to notebook', error);
      set({ error: error.message });
      throw error;
    }
  },

  removeClipboardItem: async (clipboardId, itemId) => {
    if (!clipboardId || !itemId) return;
    try {
      await api.deleteNotebookItem(clipboardId, itemId);
      await get().refreshClipboardItems(clipboardId);
    } catch (error) {
      console.error('Failed to delete notebook item', error);
      set({ error: error.message });
      throw error;
    }
  },

  removeClipboardItems: async (clipboardId, itemIds = []) => {
    if (!clipboardId) return;

    const ids = Array.from(new Set(itemIds))
      .map((id) => Number.parseInt(String(id), 10))
      .filter((id) => Number.isFinite(id));

    if (ids.length === 0) return;

    try {
      await Promise.all(ids.map((id) => api.deleteNotebookItem(clipboardId, id)));
      await get().refreshClipboardItems(clipboardId);
    } catch (error) {
      console.error('Failed to delete notebook items', error);
      set({ error: error.message });
      throw error;
    }
  },
}));
