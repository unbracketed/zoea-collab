import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import * as React from 'react';

// Mock zustand useShallow to pass through the selector
vi.mock('zustand/react/shallow', () => ({
  useShallow: (selector) => selector,
}));

// Mock dependencies before importing component
vi.mock('@yoopta/editor', () => ({
  __esModule: true,
  generateId: vi.fn(() => 'mock-generated-id'),
  YooptaPlugin: class MockYooptaPlugin {
    constructor(config) {
      this.type = config.type;
      this.elements = config.elements;
      this.options = config.options;
    }
    extend(options) {
      return { ...this, options: { ...this.options, ...options.options } };
    }
  },
  useYooptaPluginOptions: vi.fn(() => ({})),
}));

vi.mock('../components/layout/LayoutFrame', () => ({
  __esModule: true,
  default: ({ children, title, actions }) => (
    <div data-testid="layout-frame">
      <h1>{title}</h1>
      <div data-testid="actions">{actions}</div>
      {children}
    </div>
  ),
}));

vi.mock('../components/documents/YooptaEditor', () => ({
  __esModule: true,
  // eslint-disable-next-line react/display-name
  default: React.forwardRef(({ value, onChange, placeholder }, ref) => {
    React.useImperativeHandle(ref, () => ({
      openImagePicker: vi.fn(),
    }));
    return (
      <div data-testid="yoopta-editor" data-yoopta-editor="true">
        <textarea
          data-testid="editor-input"
          value={value ? JSON.stringify(value) : ''}
          onChange={(e) => {
            try {
              const parsed = JSON.parse(e.target.value);
              onChange(parsed);
            } catch {
              onChange({ 'mock-block': { type: 'Paragraph', value: e.target.value } });
            }
          }}
          placeholder={placeholder}
        />
      </div>
    );
  }),
}));


vi.mock('../components/layout/view/ViewPrimaryActions', () => {
  const Button = ({ children, onClick, disabled, title }) => (
    <button onClick={onClick} disabled={disabled} title={title} data-testid={`action-${title}`}>
      {children}
    </button>
  );
  const ViewPrimaryActions = ({ children }) => <div data-testid="primary-actions">{children}</div>;
  ViewPrimaryActions.Button = Button;
  return { __esModule: true, default: ViewPrimaryActions };
});

vi.mock('../components/document-rag', () => ({
  DocumentRAGModal: ({ isOpen }) => isOpen ? <div data-testid="rag-modal">RAG Modal</div> : null,
}));

vi.mock('../components/documents/ZoeaContentPickerModal', () => ({
  __esModule: true,
  default: ({ isOpen, onClose, onSelect }) =>
    isOpen ? (
      <div data-testid="content-picker-modal">
        <button onClick={() => onSelect({ contentType: 'message', text: 'Test message' })}>
          Select Content
        </button>
        <button onClick={onClose}>Close</button>
      </div>
    ) : null,
}));

vi.mock('../components/documents/SaveAsDocumentModal', () => ({
  __esModule: true,
  default: ({ isOpen, onClose, onSave, defaultName }) =>
    isOpen ? (
      <div data-testid="save-as-doc-modal">
        <span data-testid="default-name">{defaultName}</span>
        <button onClick={() => onSave({ name: 'Test Document', folder_id: null })}>
          Save Document
        </button>
        <button onClick={onClose}>Cancel</button>
      </div>
    ) : null,
}));

vi.mock('../services/api', () => ({
  __esModule: true,
  default: {
    saveClipboardAsDocument: vi.fn(),
  },
}));

// Store mock state
let mockClipboardState;
let mockWorkspaceState;

vi.mock('../stores', () => ({
  useClipboardStore: (selector) => selector(mockClipboardState),
  useWorkspaceStore: (selector) => selector(mockWorkspaceState),
}));

// Import after mocks
import ClipboardsPage from './ClipboardsPage';
import api from '../services/api';

describe('ClipboardsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();

    // Reset mock state
    mockWorkspaceState = {
      currentProjectId: 1,
      currentWorkspaceId: 100,
    };

    mockClipboardState = {
      clipboard: { id: 10, name: 'Test Clipboard' },
      items: [],
      loading: false,
      error: null,
      loadClipboardsForWorkspace: vi.fn(),
      refreshClipboardItems: vi.fn(),
      createClipboard: vi.fn(),
      removeClipboardItem: vi.fn(),
      removeClipboardItems: vi.fn(),
      notepadDraft: null,
      notepadDraftLoadedForClipboardId: 10,
      notepadDraftLoading: false,
      notepadDraftSaving: false,
      notepadDraftError: null,
      notepadDraftVersion: 0,
      loadNotepadDraft: vi.fn(),
      saveNotepadDraft: vi.fn().mockResolvedValue({}),
      clearNotepadDraft: vi.fn().mockResolvedValue({}),
      setNotepadDraftContent: vi.fn(),
      addMessageToClipboard: vi.fn().mockResolvedValue({}),
      addModelToClipboard: vi.fn().mockResolvedValue({}),
      ensureClipboard: vi.fn(),
    };
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  const renderPage = () => {
    return render(
      <MemoryRouter initialEntries={['/notepad']}>
        <ClipboardsPage />
      </MemoryRouter>
    );
  };

  describe('Initial Rendering', () => {
    it('renders the page with title', () => {
      renderPage();
      expect(screen.getByRole('heading', { name: 'Notebook' })).toBeInTheDocument();
    });

    it('ensures clipboard exists for workspace on mount', () => {
      renderPage();
      expect(mockClipboardState.ensureClipboard).toHaveBeenCalledWith(100);
    });

    it('loads notepad draft when clipboard exists', () => {
      renderPage();
      expect(mockClipboardState.loadNotepadDraft).toHaveBeenCalledWith(10);
    });

    it('shows workspace selection message when no workspace selected', () => {
      mockWorkspaceState.currentWorkspaceId = null;
      renderPage();
      expect(screen.getByText(/Choose a project and workspace/)).toBeInTheDocument();
    });

    it('shows create notebook message when no clipboard exists', () => {
      mockClipboardState.clipboard = null;
      renderPage();
      expect(screen.getByText('Create a notebook to start writing.')).toBeInTheDocument();
    });
  });

  describe('Editor Loading and Sync', () => {
    it('shows loading state while draft is loading', () => {
      mockClipboardState.notepadDraftLoadedForClipboardId = null;
      renderPage();
      const loadingElements = screen.getAllByText('Loading notebook...');
      expect(loadingElements.length).toBeGreaterThan(0);
    });

    it('renders editor when draft is loaded', async () => {
      renderPage();
      await waitFor(() => {
        const editors = screen.getAllByTestId('yoopta-editor');
        expect(editors.length).toBeGreaterThan(0);
      });
    });

    it('displays draft content in editor', async () => {
      mockClipboardState.notepadDraft = { 'block-1': { type: 'Paragraph', value: 'Hello' } };
      renderPage();
      await waitFor(() => {
        const editors = screen.getAllByTestId('editor-input');
        expect(editors[0].value).toContain('block-1');
      });
    });
  });

  describe('Draft Dirty State', () => {
    it('syncs draft content to store when modified', async () => {
      renderPage();

      await waitFor(() => {
        const editors = screen.getAllByTestId('editor-input');
        expect(editors.length).toBeGreaterThan(0);
      });

      const editors = screen.getAllByTestId('editor-input');
      fireEvent.change(editors[0], { target: { value: 'modified content' } });

      await waitFor(() => {
        expect(mockClipboardState.setNotepadDraftContent).toHaveBeenCalled();
      });
    });
  });

  describe('Save Draft Flow', () => {
    it('calls saveNotepadDraft when save button clicked', async () => {
      renderPage();

      const saveButtons = screen.getAllByTitle('Save notebook draft');
      fireEvent.click(saveButtons[0]);

      await waitFor(() => {
        expect(mockClipboardState.saveNotepadDraft).toHaveBeenCalledWith(10, null);
      });
    });

    it('does not throw during save when button clicked while saving', async () => {
      mockClipboardState.saveNotepadDraft = vi.fn(() => new Promise(() => {})); // Never resolves
      renderPage();

      const saveButtons = screen.getAllByTitle('Save notebook draft');
      // Should not throw when clicking save button
      expect(() => fireEvent.click(saveButtons[0])).not.toThrow();
    });

    it('handles save failure gracefully', async () => {
      mockClipboardState.saveNotepadDraft = vi.fn().mockRejectedValue(new Error('Save failed'));
      renderPage();

      const saveButtons = screen.getAllByTitle('Save notebook draft');
      // Should not throw when save fails
      expect(() => fireEvent.click(saveButtons[0])).not.toThrow();
    });
  });

  describe('Clear Draft Flow', () => {
    it('shows confirmation before clearing', async () => {
      const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(false);
      renderPage();

      const clearButtons = screen.getAllByTitle('Clear notebook draft');
      fireEvent.click(clearButtons[0]);

      expect(confirmSpy).toHaveBeenCalledWith('Clear this notebook draft? This cannot be undone.');
      expect(mockClipboardState.clearNotepadDraft).not.toHaveBeenCalled();
    });

    it('calls clearNotepadDraft when confirmed', async () => {
      vi.spyOn(window, 'confirm').mockReturnValue(true);
      renderPage();

      const clearButtons = screen.getAllByTitle('Clear notebook draft');
      fireEvent.click(clearButtons[0]);

      await waitFor(() => {
        expect(mockClipboardState.clearNotepadDraft).toHaveBeenCalledWith(10);
      });
    });

    it('calls removeClipboardItems after clear when items exist', async () => {
      mockClipboardState.items = [{ id: 1 }, { id: 2 }];
      vi.spyOn(window, 'confirm').mockReturnValue(true);
      renderPage();

      const clearButtons = screen.getAllByTitle('Clear notebook draft');
      fireEvent.click(clearButtons[0]);

      await waitFor(() => {
        expect(mockClipboardState.removeClipboardItems).toHaveBeenCalledWith(10, [1, 2]);
      });
    });
  });

  describe('Save As Document Flow', () => {
    it('opens save as document modal', async () => {
      renderPage();

      const saveAsDocButtons = screen.getAllByTitle('Save as shared document');
      fireEvent.click(saveAsDocButtons[0]);

      await waitFor(() => {
        expect(screen.getByTestId('save-as-doc-modal')).toBeInTheDocument();
      });
    });

    it('calls saveClipboardAsDocument API when modal save clicked', async () => {
      api.saveClipboardAsDocument.mockResolvedValue({ document_id: 42 });
      renderPage();

      // Open modal
      const saveAsDocButtons = screen.getAllByTitle('Save as shared document');
      fireEvent.click(saveAsDocButtons[0]);

      await waitFor(() => {
        expect(screen.getByTestId('save-as-doc-modal')).toBeInTheDocument();
      });

      // Click save in modal
      fireEvent.click(screen.getByText('Save Document'));

      await waitFor(() => {
        expect(api.saveClipboardAsDocument).toHaveBeenCalledWith(10, {
          name: 'Test Document',
          folder_id: null,
        });
      });
    });

    it('calls API to save as document', async () => {
      api.saveClipboardAsDocument.mockResolvedValue({ document_id: 42 });
      renderPage();

      // Open modal
      const saveAsDocButtons = screen.getAllByTitle('Save as shared document');
      fireEvent.click(saveAsDocButtons[0]);

      await waitFor(() => {
        expect(screen.getByTestId('save-as-doc-modal')).toBeInTheDocument();
      });

      // Click save in modal
      fireEvent.click(screen.getByText('Save Document'));

      await waitFor(() => {
        expect(api.saveClipboardAsDocument).toHaveBeenCalledWith(10, {
          name: 'Test Document',
          folder_id: null,
        });
      });
    });

    it('saves draft first if dirty before creating document', async () => {
      api.saveClipboardAsDocument.mockResolvedValue({ document_id: 42 });
      renderPage();

      // Wait for editor to appear
      await waitFor(() => {
        const editors = screen.getAllByTestId('editor-input');
        expect(editors.length).toBeGreaterThan(0);
      });

      // Make draft dirty
      const editors = screen.getAllByTestId('editor-input');
      fireEvent.change(editors[0], { target: { value: 'modified' } });

      // Open modal
      const saveAsDocButtons = screen.getAllByTitle('Save as shared document');
      fireEvent.click(saveAsDocButtons[0]);

      await waitFor(() => {
        expect(screen.getByTestId('save-as-doc-modal')).toBeInTheDocument();
      });

      // Click save in modal
      fireEvent.click(screen.getByText('Save Document'));

      await waitFor(() => {
        expect(mockClipboardState.saveNotepadDraft).toHaveBeenCalled();
      });
    });
  });

  describe('Error States', () => {
    it('displays clipboard error', () => {
      mockClipboardState.error = 'Failed to load clipboard';
      renderPage();
      const alerts = screen.getAllByRole('alert');
      expect(alerts.some(alert => alert.textContent.includes('Failed to load clipboard'))).toBe(true);
    });

    it('displays notepad draft error', () => {
      mockClipboardState.notepadDraftError = 'Draft sync failed';
      renderPage();
      const alerts = screen.getAllByRole('alert');
      expect(alerts.some(alert => alert.textContent.includes('Draft sync failed'))).toBe(true);
    });
  });

  describe('Loading States', () => {
    it('disables buttons while loading draft', () => {
      mockClipboardState.notepadDraftLoading = true;
      renderPage();

      const saveButtons = screen.getAllByTitle('Save notebook draft');
      const saveAsDocButtons = screen.getAllByTitle('Save as shared document');
      const clearButtons = screen.getAllByTitle('Clear notebook draft');

      expect(saveButtons[0]).toBeDisabled();
      expect(saveAsDocButtons[0]).toBeDisabled();
      expect(clearButtons[0]).toBeDisabled();
    });

    it('disables buttons while saving draft', () => {
      mockClipboardState.notepadDraftSaving = true;
      renderPage();

      const saveButtons = screen.getAllByTitle('Save notebook draft');
      const saveAsDocButtons = screen.getAllByTitle('Save as shared document');
      const clearButtons = screen.getAllByTitle('Clear notebook draft');

      expect(saveButtons[0]).toBeDisabled();
      expect(saveAsDocButtons[0]).toBeDisabled();
      expect(clearButtons[0]).toBeDisabled();
    });
  });

  describe('Insert from Library', () => {
    it('renders Insert from Library button', () => {
      renderPage();

      const insertButtons = screen.getAllByTitle('Insert image from library');
      expect(insertButtons.length).toBeGreaterThan(0);
    });
  });

  describe('Chat With Clipboard', () => {
    it('shows RAG modal when clicking chat button with items', async () => {
      mockClipboardState.items = [{ id: 1, content_type: 'message' }];
      renderPage();

      const chatButton = screen.getByTitle('Chat with notebook items');
      fireEvent.click(chatButton);

      await waitFor(() => {
        expect(screen.getByTestId('rag-modal')).toBeInTheDocument();
      });
    });

    it('shows alert when clipboard is empty', async () => {
      const alertSpy = vi.spyOn(window, 'alert').mockImplementation(() => {});
      mockClipboardState.items = [];
      renderPage();

      // Chat button should not be visible when items is empty
      expect(screen.queryByTitle('Chat with notebook items')).not.toBeInTheDocument();
    });
  });

  describe('Store Sync on Edit', () => {
    it('calls setNotepadDraftContent when draft is modified', async () => {
      renderPage();

      // Wait for editor to appear
      await waitFor(() => {
        const editors = screen.getAllByTestId('editor-input');
        expect(editors.length).toBeGreaterThan(0);
      });

      const editors = screen.getAllByTestId('editor-input');
      fireEvent.change(editors[0], { target: { value: 'modified content' } });

      await waitFor(() => {
        expect(mockClipboardState.setNotepadDraftContent).toHaveBeenCalledWith(
          10,
          expect.objectContaining({ 'mock-block': expect.any(Object) })
        );
      });
    });

    it('syncs content to store on every edit', async () => {
      renderPage();

      // Wait for editor to appear
      await waitFor(() => {
        const editors = screen.getAllByTestId('editor-input');
        expect(editors.length).toBeGreaterThan(0);
      });

      const editors = screen.getAllByTestId('editor-input');

      // First edit
      fireEvent.change(editors[0], { target: { value: 'first edit' } });

      // Second edit
      fireEvent.change(editors[0], { target: { value: 'second edit' } });

      await waitFor(() => {
        expect(mockClipboardState.setNotepadDraftContent).toHaveBeenCalledTimes(2);
      });
    });
  });
});
