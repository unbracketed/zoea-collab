import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { act } from '@testing-library/react';
import { useClipboardStore } from './clipboardStore';
import api from '../services/api';

vi.mock('../services/api', () => ({
  __esModule: true,
  default: {
    // New notebook API methods
    fetchNotebooks: vi.fn(),
    fetchNotebookItems: vi.fn(),
    fetchNotebookNotepadDraft: vi.fn(),
    putNotebookNotepadDraft: vi.fn(),
    deleteNotebookNotepadDraft: vi.fn(),
    createNotebook: vi.fn(),
    addNotebookItem: vi.fn(),
    deleteNotebookItem: vi.fn(),
  },
}));

// Mock @yoopta/editor generateId
vi.mock('@yoopta/editor', () => ({
  generateId: vi.fn(() => 'mock-id-' + Math.random().toString(36).slice(2, 9)),
}));

describe('clipboardStore', () => {
  beforeEach(() => {
    useClipboardStore.getState().reset();
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  describe('initial state', () => {
    it('has correct initial values', () => {
      const state = useClipboardStore.getState();
      expect(state.clipboard).toBeNull();
      expect(state.items).toEqual([]);
      expect(state.loading).toBe(false);
      expect(state.error).toBeNull();
      expect(state.notepadDraft).toBeNull();
      expect(state.notepadDraftLoadedForClipboardId).toBeNull();
      expect(state.notepadDraftLoading).toBe(false);
      expect(state.notepadDraftSaving).toBe(false);
      expect(state.notepadDraftError).toBeNull();
    });
  });

  describe('reset', () => {
    it('resets all state to initial values', async () => {
      useClipboardStore.setState({
        clipboard: { id: 1, name: 'Test' },
        items: [{ id: 1 }],
        loading: true,
        error: 'some error',
        notepadDraft: { block: {} },
        notepadDraftLoadedForClipboardId: 1,
      });

      await act(async () => {
        useClipboardStore.getState().reset();
      });

      const state = useClipboardStore.getState();
      expect(state.clipboard).toBeNull();
      expect(state.items).toEqual([]);
      expect(state.loading).toBe(false);
      expect(state.error).toBeNull();
      expect(state.notepadDraft).toBeNull();
    });
  });

  describe('loadClipboardsForWorkspace', () => {
    it('resets to initial state when workspaceId is null', async () => {
      useClipboardStore.setState({
        clipboard: { id: 1 },
        items: [{ id: 1 }],
      });

      await act(async () => {
        await useClipboardStore.getState().loadClipboardsForWorkspace(null);
      });

      const state = useClipboardStore.getState();
      expect(state.clipboard).toBeNull();
      expect(state.items).toEqual([]);
    });

    it('loads clipboard and items for workspace', async () => {
      const mockClipboard = { id: 1, name: 'Test Clipboard' };
      const mockItems = [{ id: 10, preview: 'Item 1' }, { id: 11, preview: 'Item 2' }];

      api.fetchNotebooks.mockResolvedValueOnce({ notebooks: [mockClipboard] });
      api.fetchNotebookItems.mockResolvedValueOnce({ items: mockItems });

      await act(async () => {
        await useClipboardStore.getState().loadClipboardsForWorkspace(123);
      });

      const state = useClipboardStore.getState();
      expect(state.clipboard).toEqual(mockClipboard);
      expect(state.items).toEqual(mockItems);
      expect(state.loading).toBe(false);
      expect(state.error).toBeNull();
      expect(state.lastWorkspaceId).toBe(123);
    });

    it('handles workspace with no clipboards', async () => {
      api.fetchNotebooks.mockResolvedValueOnce({ notebooks: [] });

      await act(async () => {
        await useClipboardStore.getState().loadClipboardsForWorkspace(123);
      });

      const state = useClipboardStore.getState();
      expect(state.clipboard).toBeNull();
      expect(state.items).toEqual([]);
      expect(state.loading).toBe(false);
    });

    it('sets error on API failure', async () => {
      api.fetchNotebooks.mockRejectedValueOnce(new Error('Network error'));

      await act(async () => {
        await useClipboardStore.getState().loadClipboardsForWorkspace(123);
      });

      const state = useClipboardStore.getState();
      expect(state.error).toBe('Network error');
      expect(state.loading).toBe(false);
    });

    it('does not reset notepad draft state', async () => {
      useClipboardStore.setState({
        notepadDraft: { 'block-1': { type: 'Paragraph' } },
        notepadDraftLoadedForClipboardId: 1,
      });

      api.fetchNotebooks.mockResolvedValueOnce({ notebooks: [{ id: 1 }] });
      api.fetchNotebookItems.mockResolvedValueOnce({ items: [] });

      await act(async () => {
        await useClipboardStore.getState().loadClipboardsForWorkspace(123);
      });

      const state = useClipboardStore.getState();
      expect(state.notepadDraft).toEqual({ 'block-1': { type: 'Paragraph' } });
      expect(state.notepadDraftLoadedForClipboardId).toBe(1);
    });
  });

  describe('refreshClipboardItems', () => {
    it('refreshes items for clipboard', async () => {
      const mockItems = [{ id: 20 }, { id: 21 }];
      api.fetchNotebookItems.mockResolvedValueOnce({ items: mockItems });

      await act(async () => {
        await useClipboardStore.getState().refreshClipboardItems(1);
      });

      const state = useClipboardStore.getState();
      expect(state.items).toEqual(mockItems);
    });

    it('does nothing when clipboardId is null', async () => {
      await act(async () => {
        await useClipboardStore.getState().refreshClipboardItems(null);
      });

      expect(api.fetchNotebookItems).not.toHaveBeenCalled();
    });

    it('sets error and throws on failure', async () => {
      api.fetchNotebookItems.mockRejectedValueOnce(new Error('Fetch failed'));

      await expect(
        act(async () => {
          await useClipboardStore.getState().refreshClipboardItems(1);
        })
      ).rejects.toThrow('Fetch failed');

      const state = useClipboardStore.getState();
      expect(state.error).toBe('Fetch failed');
    });
  });

  describe('loadNotepadDraft', () => {
    it('loads notepad draft content', async () => {
      const mockContent = { 'block-1': { type: 'Paragraph', value: [{ text: 'Hello' }] } };
      api.fetchNotebookNotepadDraft.mockResolvedValueOnce({ content: mockContent });

      await act(async () => {
        await useClipboardStore.getState().loadNotepadDraft(1);
      });

      const state = useClipboardStore.getState();
      expect(state.notepadDraft).toEqual(mockContent);
      expect(state.notepadDraftLoadedForClipboardId).toBe(1);
      expect(state.notepadDraftLoading).toBe(false);
      expect(state.notepadDraftError).toBeNull();
    });

    it('does nothing when clipboardId is null', async () => {
      await act(async () => {
        await useClipboardStore.getState().loadNotepadDraft(null);
      });

      expect(api.fetchNotebookNotepadDraft).not.toHaveBeenCalled();
    });

    it('does not reload if already loaded for same clipboard', async () => {
      useClipboardStore.setState({ notepadDraftLoadedForClipboardId: 1 });

      await act(async () => {
        await useClipboardStore.getState().loadNotepadDraft(1);
      });

      expect(api.fetchNotebookNotepadDraft).not.toHaveBeenCalled();
    });

    it('does not start loading if already loading', async () => {
      useClipboardStore.setState({ notepadDraftLoading: true });

      await act(async () => {
        await useClipboardStore.getState().loadNotepadDraft(1);
      });

      expect(api.fetchNotebookNotepadDraft).not.toHaveBeenCalled();
    });

    it('sets error on failure', async () => {
      api.fetchNotebookNotepadDraft.mockRejectedValueOnce(new Error('Draft load failed'));

      await act(async () => {
        await useClipboardStore.getState().loadNotepadDraft(1);
      });

      const state = useClipboardStore.getState();
      expect(state.notepadDraftError).toBe('Draft load failed');
      expect(state.notepadDraftLoading).toBe(false);
      expect(state.notepadDraftLoadedForClipboardId).toBeNull();
    });

    it('handles null content from API', async () => {
      api.fetchNotebookNotepadDraft.mockResolvedValueOnce({ content: null });

      await act(async () => {
        await useClipboardStore.getState().loadNotepadDraft(1);
      });

      const state = useClipboardStore.getState();
      expect(state.notepadDraft).toBeNull();
      expect(state.notepadDraftLoadedForClipboardId).toBe(1);
    });
  });

  describe('saveNotepadDraft', () => {
    it('saves notepad draft content', async () => {
      const mockContent = { 'block-1': { type: 'Paragraph' } };
      api.putNotebookNotepadDraft.mockResolvedValueOnce({ content: mockContent });

      let result;
      await act(async () => {
        result = await useClipboardStore.getState().saveNotepadDraft(1, mockContent);
      });

      expect(result).toEqual(mockContent);
      const state = useClipboardStore.getState();
      expect(state.notepadDraft).toEqual(mockContent);
      expect(state.notepadDraftSaving).toBe(false);
      expect(state.notepadDraftError).toBeNull();
    });

    it('throws when clipboardId is missing', async () => {
      await expect(
        act(async () => {
          await useClipboardStore.getState().saveNotepadDraft(null, {});
        })
      ).rejects.toThrow('clipboardId is required');
    });

    it('sets saving state during save', async () => {
      let savingDuringSave = false;
      api.putNotebookNotepadDraft.mockImplementationOnce(async () => {
        savingDuringSave = useClipboardStore.getState().notepadDraftSaving;
        return { content: {} };
      });

      await act(async () => {
        await useClipboardStore.getState().saveNotepadDraft(1, {});
      });

      expect(savingDuringSave).toBe(true);
    });

    it('sets error and throws on failure', async () => {
      api.putNotebookNotepadDraft.mockRejectedValueOnce(new Error('Save failed'));

      await expect(
        act(async () => {
          await useClipboardStore.getState().saveNotepadDraft(1, {});
        })
      ).rejects.toThrow('Save failed');

      const state = useClipboardStore.getState();
      expect(state.notepadDraftError).toBe('Save failed');
      expect(state.notepadDraftSaving).toBe(false);
    });
  });

  describe('clearNotepadDraft', () => {
    it('clears notepad draft', async () => {
      useClipboardStore.setState({
        notepadDraft: { 'block-1': {} },
        notepadDraftLoadedForClipboardId: 1,
      });

      api.deleteNotebookNotepadDraft.mockResolvedValueOnce({});

      await act(async () => {
        await useClipboardStore.getState().clearNotepadDraft(1);
      });

      const state = useClipboardStore.getState();
      expect(state.notepadDraft).toBeNull();
      expect(state.notepadDraftLoadedForClipboardId).toBe(1);
      expect(state.notepadDraftSaving).toBe(false);
    });

    it('does nothing when clipboardId is null', async () => {
      await act(async () => {
        await useClipboardStore.getState().clearNotepadDraft(null);
      });

      expect(api.deleteNotebookNotepadDraft).not.toHaveBeenCalled();
    });

    it('sets error and throws on failure', async () => {
      api.deleteNotebookNotepadDraft.mockRejectedValueOnce(new Error('Delete failed'));

      await expect(
        act(async () => {
          await useClipboardStore.getState().clearNotepadDraft(1);
        })
      ).rejects.toThrow('Delete failed');

      const state = useClipboardStore.getState();
      expect(state.notepadDraftError).toBe('Delete failed');
    });
  });

  describe('setNotepadDraftContent', () => {
    it('updates notepad draft in store without API call', () => {
      useClipboardStore.setState({
        notepadDraftLoadedForClipboardId: 1,
        notepadDraft: null,
      });

      const newContent = { 'block-1': { type: 'Paragraph', value: [{ text: 'Hello' }] } };

      act(() => {
        useClipboardStore.getState().setNotepadDraftContent(1, newContent);
      });

      const state = useClipboardStore.getState();
      expect(state.notepadDraft).toEqual(newContent);
      expect(api.putNotebookNotepadDraft).not.toHaveBeenCalled();
    });

    it('does nothing when clipboardId does not match loaded clipboard', () => {
      useClipboardStore.setState({
        notepadDraftLoadedForClipboardId: 1,
        notepadDraft: { existing: 'content' },
      });

      act(() => {
        useClipboardStore.getState().setNotepadDraftContent(999, { new: 'content' });
      });

      const state = useClipboardStore.getState();
      expect(state.notepadDraft).toEqual({ existing: 'content' });
    });

    it('allows setting null content', () => {
      useClipboardStore.setState({
        notepadDraftLoadedForClipboardId: 1,
        notepadDraft: { 'block-1': {} },
      });

      act(() => {
        useClipboardStore.getState().setNotepadDraftContent(1, null);
      });

      const state = useClipboardStore.getState();
      expect(state.notepadDraft).toBeNull();
    });
  });

  describe('notepadDraftVersion tracking', () => {
    it('increments version when loading notepad draft', async () => {
      api.fetchNotebookNotepadDraft.mockResolvedValueOnce({ content: {} });

      const initialVersion = useClipboardStore.getState().notepadDraftVersion;

      await act(async () => {
        await useClipboardStore.getState().loadNotepadDraft(1);
      });

      const state = useClipboardStore.getState();
      expect(state.notepadDraftVersion).toBe(initialVersion + 1);
    });

    it('increments version when saving notepad draft', async () => {
      api.putNotebookNotepadDraft.mockResolvedValueOnce({ content: {} });

      const initialVersion = useClipboardStore.getState().notepadDraftVersion;

      await act(async () => {
        await useClipboardStore.getState().saveNotepadDraft(1, {});
      });

      const state = useClipboardStore.getState();
      expect(state.notepadDraftVersion).toBe(initialVersion + 1);
    });

    it('increments version when clearing notepad draft', async () => {
      api.deleteNotebookNotepadDraft.mockResolvedValueOnce({});

      const initialVersion = useClipboardStore.getState().notepadDraftVersion;

      await act(async () => {
        await useClipboardStore.getState().clearNotepadDraft(1);
      });

      const state = useClipboardStore.getState();
      expect(state.notepadDraftVersion).toBe(initialVersion + 1);
    });

    it('does not increment version when setNotepadDraftContent is called', () => {
      useClipboardStore.setState({
        notepadDraftLoadedForClipboardId: 1,
        notepadDraftVersion: 5,
      });

      act(() => {
        useClipboardStore.getState().setNotepadDraftContent(1, { new: 'content' });
      });

      const state = useClipboardStore.getState();
      expect(state.notepadDraftVersion).toBe(5);
    });
  });

  describe('createClipboard', () => {
    it('creates clipboard and reloads', async () => {
      api.createNotebook.mockResolvedValueOnce({ id: 5 });
      api.fetchNotebooks.mockResolvedValueOnce({ notebooks: [{ id: 5 }] });
      api.fetchNotebookItems.mockResolvedValueOnce({ items: [] });

      await act(async () => {
        await useClipboardStore.getState().createClipboard(123);
      });

      expect(api.createNotebook).toHaveBeenCalledWith({
        workspace_id: 123,
        name: 'Notebook',
        description: 'Private notebook for this workspace',
        activate: true,
      });
    });

    it('throws when workspaceId is missing', async () => {
      await expect(
        act(async () => {
          await useClipboardStore.getState().createClipboard(null);
        })
      ).rejects.toThrow('Workspace is required');
    });

    it('sets error on failure', async () => {
      api.createNotebook.mockRejectedValueOnce(new Error('Create failed'));

      await expect(
        act(async () => {
          await useClipboardStore.getState().createClipboard(123);
        })
      ).rejects.toThrow('Create failed');

      const state = useClipboardStore.getState();
      expect(state.error).toBe('Create failed');
    });
  });

  describe('ensureClipboard', () => {
    it('returns existing clipboard if loaded for same workspace', async () => {
      const mockClipboard = { id: 1, name: 'Existing' };
      useClipboardStore.setState({
        clipboard: mockClipboard,
        lastWorkspaceId: 123,
      });

      let result;
      await act(async () => {
        result = await useClipboardStore.getState().ensureClipboard(123);
      });

      expect(result).toEqual(mockClipboard);
      expect(api.fetchNotebooks).not.toHaveBeenCalled();
    });

    it('loads and returns clipboard if different workspace', async () => {
      const mockClipboard = { id: 2, name: 'New' };
      api.fetchNotebooks.mockResolvedValueOnce({ notebooks: [mockClipboard] });
      api.fetchNotebookItems.mockResolvedValueOnce({ items: [] });

      useClipboardStore.setState({ lastWorkspaceId: 100 });

      let result;
      await act(async () => {
        result = await useClipboardStore.getState().ensureClipboard(123);
      });

      expect(result).toEqual(mockClipboard);
    });

    it('creates clipboard if none exists', async () => {
      api.fetchNotebooks.mockResolvedValueOnce({ notebooks: [] });
      api.createNotebook.mockResolvedValueOnce({ id: 3 });
      api.fetchNotebooks.mockResolvedValueOnce({ notebooks: [{ id: 3 }] });
      api.fetchNotebookItems.mockResolvedValueOnce({ items: [] });

      let result;
      await act(async () => {
        result = await useClipboardStore.getState().ensureClipboard(123);
      });

      expect(api.createNotebook).toHaveBeenCalled();
      expect(result).toEqual({ id: 3 });
    });

    it('throws when workspaceId is missing', async () => {
      await expect(
        act(async () => {
          await useClipboardStore.getState().ensureClipboard(null);
        })
      ).rejects.toThrow('Workspace is required');
    });
  });

  describe('appendClipboardItemToNotepadDraft', () => {
    it('appends block to existing draft', async () => {
      const existingContent = {
        'block-1': { id: 'block-1', meta: { order: 0 }, type: 'Paragraph' },
      };
      useClipboardStore.setState({
        notepadDraft: existingContent,
        notepadDraftLoadedForClipboardId: 1,
      });

      api.putNotebookNotepadDraft.mockResolvedValueOnce({ content: {} });

      await act(async () => {
        await useClipboardStore.getState().appendClipboardItemToNotepadDraft(1, 100);
      });

      expect(api.putNotebookNotepadDraft).toHaveBeenCalledWith(
        1,
        expect.objectContaining({
          content: expect.objectContaining({
            'block-1': existingContent['block-1'],
          }),
        })
      );

      // Check that a new NotebookItem block was added
      const callArg = api.putNotebookNotepadDraft.mock.calls[0][1].content;
      const newBlockKey = Object.keys(callArg).find((k) => k !== 'block-1');
      expect(callArg[newBlockKey]).toMatchObject({
        type: 'NotebookItem',
        meta: { order: 1 },
      });
    });

    it('fetches draft if not loaded for clipboard', async () => {
      api.fetchNotebookNotepadDraft.mockResolvedValueOnce({ content: null });
      api.putNotebookNotepadDraft.mockResolvedValueOnce({ content: {} });

      useClipboardStore.setState({ notepadDraftLoadedForClipboardId: 999 });

      await act(async () => {
        await useClipboardStore.getState().appendClipboardItemToNotepadDraft(1, 100);
      });

      expect(api.fetchNotebookNotepadDraft).toHaveBeenCalledWith(1);
    });

    it('returns null when clipboardId is missing', async () => {
      let result;
      await act(async () => {
        result = await useClipboardStore.getState().appendClipboardItemToNotepadDraft(null, 100);
      });

      expect(result).toBeNull();
    });

    it('returns null when clipboardItemId is missing', async () => {
      let result;
      await act(async () => {
        result = await useClipboardStore.getState().appendClipboardItemToNotepadDraft(1, null);
      });

      expect(result).toBeNull();
    });
  });

  describe('addMessageToClipboard', () => {
    beforeEach(() => {
      api.fetchNotebooks.mockResolvedValue({ notebooks: [{ id: 1 }] });
      api.fetchNotebookItems.mockResolvedValue({ items: [] });
      api.fetchNotebookNotepadDraft.mockResolvedValue({ content: null });
      api.putNotebookNotepadDraft.mockResolvedValue({ content: {} });
    });

    it('adds message to clipboard and appends to draft', async () => {
      api.addNotebookItem.mockResolvedValueOnce({ item: { id: 50 } });

      await act(async () => {
        await useClipboardStore.getState().addMessageToClipboard({
          workspaceId: 123,
          text: 'Hello world',
        });
      });

      expect(api.addNotebookItem).toHaveBeenCalledWith(
        1,
        expect.objectContaining({
          direction: 'right',
          source_channel: 'message',
          source_metadata: expect.objectContaining({
            full_text: 'Hello world',
          }),
        })
      );
      expect(api.putNotebookNotepadDraft).toHaveBeenCalled();
    });

    it('truncates long text for preview', async () => {
      const longText = 'x'.repeat(200);
      api.addNotebookItem.mockResolvedValueOnce({ item: { id: 51 } });

      await act(async () => {
        await useClipboardStore.getState().addMessageToClipboard({
          workspaceId: 123,
          text: longText,
        });
      });

      const callArg = api.addNotebookItem.mock.calls[0][1];
      expect(callArg.source_metadata.preview.length).toBeLessThanOrEqual(180);
      expect(callArg.source_metadata.preview).toContain('...');
    });

    it('does nothing when text is empty', async () => {
      await act(async () => {
        await useClipboardStore.getState().addMessageToClipboard({
          workspaceId: 123,
          text: '',
        });
      });

      expect(api.addNotebookItem).not.toHaveBeenCalled();
    });

    it('rolls back clipboard item on draft append failure', async () => {
      // Set up clipboard as already loaded to skip ensureClipboard flow
      useClipboardStore.setState({
        clipboard: { id: 1 },
        lastWorkspaceId: 123,
        notepadDraftLoadedForClipboardId: 1,
        notepadDraft: null,
      });

      // Clear and set up fresh mocks for this test
      vi.clearAllMocks();
      api.addNotebookItem.mockResolvedValueOnce({ item: { id: 52 } });
      api.putNotebookNotepadDraft.mockRejectedValueOnce(new Error('Draft save failed'));
      api.deleteNotebookItem.mockResolvedValueOnce({});
      api.fetchNotebookItems.mockResolvedValueOnce({ items: [] });

      // Call directly without act wrapper to properly catch the error flow
      let caughtError = null;
      try {
        await useClipboardStore.getState().addMessageToClipboard({
          workspaceId: 123,
          text: 'Test message',
        });
      } catch (error) {
        caughtError = error;
      }

      expect(caughtError?.message).toBe('Draft save failed');
      expect(api.deleteNotebookItem).toHaveBeenCalledWith(1, 52);
    });
  });

  describe('addModelToClipboard', () => {
    beforeEach(() => {
      api.fetchNotebooks.mockResolvedValue({ notebooks: [{ id: 1 }] });
      api.fetchNotebookItems.mockResolvedValue({ items: [] });
      api.fetchNotebookNotepadDraft.mockResolvedValue({ content: null });
      api.putNotebookNotepadDraft.mockResolvedValue({ content: {} });
    });

    it('adds model to clipboard', async () => {
      api.addNotebookItem.mockResolvedValueOnce({ item: { id: 60 } });

      await act(async () => {
        await useClipboardStore.getState().addModelToClipboard({
          workspaceId: 123,
          contentType: 'documents.document',
          objectId: 456,
          metadata: { document_name: 'Test Doc' },
        });
      });

      expect(api.addNotebookItem).toHaveBeenCalledWith(
        1,
        expect.objectContaining({
          content_type: 'documents.document',
          object_id: '456',
          source_channel: 'document',
        })
      );
    });

    it('throws when contentType is missing', async () => {
      await expect(
        act(async () => {
          await useClipboardStore.getState().addModelToClipboard({
            workspaceId: 123,
            objectId: 456,
          });
        })
      ).rejects.toThrow('contentType and objectId are required');
    });

    it('throws when objectId is missing', async () => {
      await expect(
        act(async () => {
          await useClipboardStore.getState().addModelToClipboard({
            workspaceId: 123,
            contentType: 'documents.document',
          });
        })
      ).rejects.toThrow('contentType and objectId are required');
    });

    it('rolls back on draft append failure', async () => {
      // Set up clipboard as already loaded to skip ensureClipboard flow
      useClipboardStore.setState({
        clipboard: { id: 1 },
        lastWorkspaceId: 123,
        notepadDraftLoadedForClipboardId: 1,
        notepadDraft: null,
      });

      // Clear and set up fresh mocks for this test
      vi.clearAllMocks();
      api.addNotebookItem.mockResolvedValueOnce({ item: { id: 61 } });
      api.putNotebookNotepadDraft.mockRejectedValueOnce(new Error('Draft failed'));
      api.deleteNotebookItem.mockResolvedValueOnce({});
      api.fetchNotebookItems.mockResolvedValueOnce({ items: [] });

      // Call directly without act wrapper to properly catch the error flow
      let caughtError = null;
      try {
        await useClipboardStore.getState().addModelToClipboard({
          workspaceId: 123,
          contentType: 'documents.document',
          objectId: 456,
        });
      } catch (error) {
        caughtError = error;
      }

      expect(caughtError?.message).toBe('Draft failed');
      expect(api.deleteNotebookItem).toHaveBeenCalledWith(1, 61);
    });
  });

  describe('addDiagramToClipboard', () => {
    beforeEach(() => {
      api.fetchNotebooks.mockResolvedValue({ notebooks: [{ id: 1 }] });
      api.fetchNotebookItems.mockResolvedValue({ items: [] });
      api.fetchNotebookNotepadDraft.mockResolvedValue({ content: null });
      api.putNotebookNotepadDraft.mockResolvedValue({ content: {} });
    });

    it('adds diagram to clipboard', async () => {
      api.addNotebookItem.mockResolvedValueOnce({ item: { id: 70 } });

      await act(async () => {
        await useClipboardStore.getState().addDiagramToClipboard({
          workspaceId: 123,
          diagramCode: 'A -> B',
          diagramName: 'Flow',
          diagramPreview: 'preview.png',
        });
      });

      expect(api.addNotebookItem).toHaveBeenCalledWith(
        1,
        expect.objectContaining({
          source_channel: 'canvas',
          source_metadata: expect.objectContaining({
            diagram_code: 'A -> B',
            diagram_name: 'Flow',
            source: 'canvas',
          }),
        })
      );
    });

    it('throws when diagram code is empty', async () => {
      await expect(
        act(async () => {
          await useClipboardStore.getState().addDiagramToClipboard({
            workspaceId: 123,
            diagramCode: '   ',
          });
        })
      ).rejects.toThrow('Diagram content is required');
    });

    it('throws when workspaceId is missing', async () => {
      await expect(
        act(async () => {
          await useClipboardStore.getState().addDiagramToClipboard({
            diagramCode: 'A -> B',
          });
        })
      ).rejects.toThrow('Diagram content is required');
    });
  });

  describe('removeClipboardItem', () => {
    it('removes item and refreshes', async () => {
      api.deleteNotebookItem.mockResolvedValueOnce({});
      api.fetchNotebookItems.mockResolvedValueOnce({ items: [] });

      await act(async () => {
        await useClipboardStore.getState().removeClipboardItem(1, 100);
      });

      expect(api.deleteNotebookItem).toHaveBeenCalledWith(1, 100);
      expect(api.fetchNotebookItems).toHaveBeenCalledWith(1);
    });

    it('does nothing when clipboardId is null', async () => {
      await act(async () => {
        await useClipboardStore.getState().removeClipboardItem(null, 100);
      });

      expect(api.deleteNotebookItem).not.toHaveBeenCalled();
    });

    it('does nothing when itemId is null', async () => {
      await act(async () => {
        await useClipboardStore.getState().removeClipboardItem(1, null);
      });

      expect(api.deleteNotebookItem).not.toHaveBeenCalled();
    });

    it('sets error and throws on failure', async () => {
      api.deleteNotebookItem.mockRejectedValueOnce(new Error('Delete failed'));

      await expect(
        act(async () => {
          await useClipboardStore.getState().removeClipboardItem(1, 100);
        })
      ).rejects.toThrow('Delete failed');

      const state = useClipboardStore.getState();
      expect(state.error).toBe('Delete failed');
    });
  });

  describe('removeClipboardItems', () => {
    it('removes multiple items', async () => {
      api.deleteNotebookItem.mockResolvedValue({});
      api.fetchNotebookItems.mockResolvedValueOnce({ items: [] });

      await act(async () => {
        await useClipboardStore.getState().removeClipboardItems(1, [100, 101, 102]);
      });

      expect(api.deleteNotebookItem).toHaveBeenCalledTimes(3);
      expect(api.deleteNotebookItem).toHaveBeenCalledWith(1, 100);
      expect(api.deleteNotebookItem).toHaveBeenCalledWith(1, 101);
      expect(api.deleteNotebookItem).toHaveBeenCalledWith(1, 102);
    });

    it('does nothing when clipboardId is null', async () => {
      await act(async () => {
        await useClipboardStore.getState().removeClipboardItems(null, [100]);
      });

      expect(api.deleteNotebookItem).not.toHaveBeenCalled();
    });

    it('does nothing when itemIds is empty', async () => {
      await act(async () => {
        await useClipboardStore.getState().removeClipboardItems(1, []);
      });

      expect(api.deleteNotebookItem).not.toHaveBeenCalled();
    });

    it('deduplicates item IDs', async () => {
      api.deleteNotebookItem.mockResolvedValue({});
      api.fetchNotebookItems.mockResolvedValueOnce({ items: [] });

      await act(async () => {
        await useClipboardStore.getState().removeClipboardItems(1, [100, 100, 100]);
      });

      expect(api.deleteNotebookItem).toHaveBeenCalledTimes(1);
    });

    it('filters out invalid IDs', async () => {
      api.deleteNotebookItem.mockResolvedValue({});
      api.fetchNotebookItems.mockResolvedValueOnce({ items: [] });

      await act(async () => {
        await useClipboardStore.getState().removeClipboardItems(1, [100, 'invalid', null, NaN]);
      });

      expect(api.deleteNotebookItem).toHaveBeenCalledTimes(1);
      expect(api.deleteNotebookItem).toHaveBeenCalledWith(1, 100);
    });
  });
});
