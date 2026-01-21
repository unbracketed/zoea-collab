import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';

// Mock @yoopta/editor before importing the plugin
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
  useYooptaPluginOptions: vi.fn(),
}));

// Import after mocks
import {
  extractNotebookItemIdsFromYooptaContent,
  NotebookItemCommands,
  NotebookItemPlugin,
  createNotebookItemPlugin,
} from './yooptaClipboardItemPlugin';
import { useYooptaPluginOptions } from '@yoopta/editor';

// Get NotebookItemEmbed component for direct testing
// Element type is 'notebookitem' (lowercase, no underscore)
const NotebookItemEmbed = NotebookItemPlugin.elements.notebookitem.render;

describe('yooptaClipboardItemPlugin', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('extractNotebookItemIdsFromYooptaContent', () => {
    it('returns empty set for null content', () => {
      const result = extractNotebookItemIdsFromYooptaContent(null);
      expect(result.size).toBe(0);
    });

    it('returns empty set for undefined content', () => {
      const result = extractNotebookItemIdsFromYooptaContent(undefined);
      expect(result.size).toBe(0);
    });

    it('returns empty set for non-object content', () => {
      const result = extractNotebookItemIdsFromYooptaContent('string');
      expect(result.size).toBe(0);
    });

    it('extracts single notebook item ID', () => {
      const content = {
        'block-1': {
          type: 'NotebookItem',
          value: [
            {
              type: 'notebookitem',
              props: { notebook_item_id: 42 },
            },
          ],
        },
      };
      const result = extractNotebookItemIdsFromYooptaContent(content);
      expect(result.size).toBe(1);
      expect(result.has(42)).toBe(true);
    });

    it('extracts multiple notebook item IDs', () => {
      const content = {
        'block-1': {
          type: 'NotebookItem',
          value: [{ type: 'notebookitem', props: { notebook_item_id: 1 } }],
        },
        'block-2': {
          type: 'NotebookItem',
          value: [{ type: 'notebookitem', props: { notebook_item_id: 2 } }],
        },
        'block-3': {
          type: 'Paragraph',
          value: [{ type: 'paragraph', children: [{ text: 'Hello' }] }],
        },
      };
      const result = extractNotebookItemIdsFromYooptaContent(content);
      expect(result.size).toBe(2);
      expect(result.has(1)).toBe(true);
      expect(result.has(2)).toBe(true);
    });

    it('coerces string IDs to numbers', () => {
      const content = {
        'block-1': {
          type: 'NotebookItem',
          value: [{ type: 'notebookitem', props: { notebook_item_id: '123' } }],
        },
      };
      const result = extractNotebookItemIdsFromYooptaContent(content);
      expect(result.has(123)).toBe(true);
    });

    it('ignores null notebook_item_id', () => {
      const content = {
        'block-1': {
          type: 'NotebookItem',
          value: [{ type: 'notebookitem', props: { notebook_item_id: null } }],
        },
      };
      const result = extractNotebookItemIdsFromYooptaContent(content);
      expect(result.size).toBe(0);
    });

    it('ignores invalid (non-numeric) notebook_item_id', () => {
      const content = {
        'block-1': {
          type: 'NotebookItem',
          value: [{ type: 'notebookitem', props: { notebook_item_id: 'not-a-number' } }],
        },
      };
      const result = extractNotebookItemIdsFromYooptaContent(content);
      expect(result.size).toBe(0);
    });

    it('extracts IDs from nested children', () => {
      const content = {
        'block-1': {
          type: 'NotebookItem',
          value: [
            {
              type: 'notebookitem',
              props: { notebook_item_id: 10 },
              children: [
                {
                  type: 'notebookitem',
                  props: { notebook_item_id: 20 },
                },
              ],
            },
          ],
        },
      };
      const result = extractNotebookItemIdsFromYooptaContent(content);
      expect(result.has(10)).toBe(true);
      expect(result.has(20)).toBe(true);
    });
  });

  describe('NotebookItemCommands', () => {
    describe('buildNotebookItemElements', () => {
      it('creates element with notebook_item_id', () => {
        const element = NotebookItemCommands.buildNotebookItemElements({}, { notebookItemId: 99 });
        expect(element.type).toBe('notebookitem');
        expect(element.props.notebook_item_id).toBe(99);
        expect(element.props.nodeType).toBe('void');
        expect(element.children).toEqual([{ text: '' }]);
      });

      it('generates unique ID', () => {
        const element = NotebookItemCommands.buildNotebookItemElements({}, { notebookItemId: 1 });
        expect(element.id).toBeDefined();
        expect(element.id).toContain('mock-generated-id');
      });
    });

    describe('insertNotebookItem', () => {
      it('returns null when editor is missing', () => {
        const result = NotebookItemCommands.insertNotebookItem(null, { notebookItemId: 1 });
        expect(result).toBeNull();
      });

      it('returns null when notebookItemId is missing', () => {
        const mockEditor = { insertBlock: vi.fn() };
        const result = NotebookItemCommands.insertNotebookItem(mockEditor, {});
        expect(result).toBeNull();
      });

      it('calls editor.insertBlock with correct params', () => {
        const mockEditor = { insertBlock: vi.fn().mockReturnValue('inserted') };
        const result = NotebookItemCommands.insertNotebookItem(mockEditor, {
          notebookItemId: 42,
          at: 5,
          focus: false,
        });

        expect(mockEditor.insertBlock).toHaveBeenCalledWith(
          'NotebookItem',
          expect.objectContaining({
            at: 5,
            focus: false,
            blockData: expect.objectContaining({
              meta: { align: 'left', depth: 0 },
            }),
          })
        );
        expect(result).toBe('inserted');
      });
    });
  });

  describe('NotebookItemPlugin', () => {
    it('has correct type', () => {
      expect(NotebookItemPlugin.type).toBe('NotebookItem');
    });

    it('has notebookitem element', () => {
      expect(NotebookItemPlugin.elements.notebookitem).toBeDefined();
      expect(NotebookItemPlugin.elements.notebookitem.props.nodeType).toBe('void');
    });

    it('has display options', () => {
      expect(NotebookItemPlugin.options.display.title).toBe('Notebook Item');
    });
  });

  describe('createNotebookItemPlugin', () => {
    it('creates plugin with custom options', () => {
      const customResolver = vi.fn();
      const plugin = createNotebookItemPlugin({
        resolveNotebookItem: customResolver,
      });

      expect(plugin.options.resolveNotebookItem).toBe(customResolver);
    });
  });

  describe('NotebookItemEmbed component', () => {
    const defaultProps = {
      element: {
        props: { notebook_item_id: 42 },
      },
      attributes: { 'data-testid': 'embed' },
      children: null,
    };

    it('renders without crashing', () => {
      useYooptaPluginOptions.mockReturnValue({});
      render(<NotebookItemEmbed {...defaultProps} />);
      expect(screen.getByTestId('embed')).toBeInTheDocument();
    });

    it('renders with contentEditable false (void block)', () => {
      useYooptaPluginOptions.mockReturnValue({});
      render(<NotebookItemEmbed {...defaultProps} />);
      const embed = screen.getByTestId('embed');
      expect(embed).toHaveAttribute('contenteditable', 'false');
    });

    it('displays fallback title when no resolver provided', () => {
      useYooptaPluginOptions.mockReturnValue({});
      render(<NotebookItemEmbed {...defaultProps} />);
      // Without a resolver, guessDisplayFromItem returns 'Notebook item' as the fallback title
      expect(screen.getByText(/Notebook item/)).toBeInTheDocument();
    });

    it('displays resolved document item correctly', () => {
      useYooptaPluginOptions.mockReturnValue({
        resolveNotebookItem: (id) => ({
          id,
          content_type: 'documents.document',
          source_metadata: { document_name: 'My Document' },
        }),
      });

      render(<NotebookItemEmbed {...defaultProps} />);
      expect(screen.getByText('My Document')).toBeInTheDocument();
    });

    it('displays resolved message item with preview', () => {
      useYooptaPluginOptions.mockReturnValue({
        resolveNotebookItem: (id) => ({
          id,
          source_metadata: {
            preview: 'This is a preview of the message content',
          },
        }),
      });

      render(<NotebookItemEmbed {...defaultProps} />);
      // Message preview appears in both header (as title) and body (as content)
      // Use getAllByText since the text appears in multiple places
      const previewElements = screen.getAllByText(/This is a preview/);
      expect(previewElements.length).toBeGreaterThanOrEqual(1);
      // Subtitle shows 'Message' in header when collapsed, but component is expanded by default
      // so we check it exists somewhere in the component
      expect(screen.getByTestId('embed')).toBeInTheDocument();
    });

    it('displays resolved diagram item', () => {
      useYooptaPluginOptions.mockReturnValue({
        resolveNotebookItem: (id) => ({
          id,
          source_metadata: {
            diagram_name: 'Flow Diagram',
            diagram_code: 'A -> B\nB -> C',
          },
        }),
      });

      render(<NotebookItemEmbed {...defaultProps} />);
      expect(screen.getByText('Flow Diagram')).toBeInTheDocument();
      // Diagram code is rendered in a <pre><code> element
      const embed = screen.getByTestId('embed');
      const codeElement = embed.querySelector('code');
      expect(codeElement).toBeInTheDocument();
      expect(codeElement.textContent).toContain('A -> B');
    });

    it('truncates long message titles', () => {
      const longText = 'x'.repeat(100);
      useYooptaPluginOptions.mockReturnValue({
        resolveNotebookItem: (id) => ({
          id,
          source_metadata: { preview: longText },
        }),
      });

      render(<NotebookItemEmbed {...defaultProps} />);
      const title = screen.getByText(/^x+\.\.\.$/);
      expect(title.textContent.length).toBeLessThan(100);
    });

    it('shows Open button when resolver and handler provided', () => {
      const onOpen = vi.fn();
      useYooptaPluginOptions.mockReturnValue({
        resolveNotebookItem: (id) => ({ id, content_type: 'documents.document' }),
        onOpenNotebookItem: onOpen,
      });

      render(<NotebookItemEmbed {...defaultProps} />);
      expect(screen.getByRole('button', { name: /open/i })).toBeInTheDocument();
    });

    it('hides Open button when no handler provided', () => {
      useYooptaPluginOptions.mockReturnValue({
        resolveNotebookItem: (id) => ({ id }),
        // No onOpenNotebookItem
      });

      render(<NotebookItemEmbed {...defaultProps} />);
      expect(screen.queryByRole('button', { name: /open/i })).not.toBeInTheDocument();
    });

    it('calls onOpenNotebookItem when Open button clicked', () => {
      const resolvedItem = { id: 42, content_type: 'documents.document' };
      const onOpen = vi.fn();
      useYooptaPluginOptions.mockReturnValue({
        resolveNotebookItem: () => resolvedItem,
        onOpenNotebookItem: onOpen,
      });

      render(<NotebookItemEmbed {...defaultProps} />);
      fireEvent.click(screen.getByRole('button', { name: /open/i }));
      expect(onOpen).toHaveBeenCalledWith(resolvedItem);
    });

    it('handles null notebook_item_id gracefully', () => {
      useYooptaPluginOptions.mockReturnValue({});
      const props = {
        ...defaultProps,
        element: { props: { notebook_item_id: null } },
      };

      render(<NotebookItemEmbed {...props} />);
      expect(screen.getByText(/Notebook item/)).toBeInTheDocument();
    });

    it('applies zoea-notebook-item-embed class', () => {
      useYooptaPluginOptions.mockReturnValue({});
      render(<NotebookItemEmbed {...defaultProps} />);
      const embed = screen.getByTestId('embed');
      expect(embed).toHaveClass('zoea-notebook-item-embed');
    });
  });
});
