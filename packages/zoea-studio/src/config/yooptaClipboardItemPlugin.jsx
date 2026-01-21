/**
 * Yoopta Notebook Item Plugin (JSX)
 *
 * Provides a Notebook-only embedded block that references a NotebookItem by ID.
 * The block is intended for user-private drafts; exporting to a shared document
 * must sanitize/inline these references on the backend.
 */

import { useMemo, useState } from 'react';
import { generateId, YooptaPlugin, useYooptaPluginOptions } from '@yoopta/editor';
import { ChevronDown, ChevronRight, ExternalLink, FileText, Image, LayoutGrid, MessageSquare } from 'lucide-react';
import MarkdownViewer from '../components/MarkdownViewer';

const PLUGIN_TYPE = 'NotebookItem';
const ELEMENT_TYPE = 'notebookitem';

const coerceNotebookItemId = (value) => {
  if (value === null || value === undefined) return null;
  const parsed = Number.parseInt(String(value), 10);
  return Number.isFinite(parsed) ? parsed : null;
};

export const extractNotebookItemIdsFromYooptaContent = (content) => {
  const ids = new Set();
  if (!content || typeof content !== 'object') return ids;

  const visit = (node) => {
    if (!node || typeof node !== 'object') return;
    if (node.type === ELEMENT_TYPE) {
      const id = coerceNotebookItemId(node?.props?.notebook_item_id);
      if (id !== null) ids.add(id);
    }
    const children = node.children;
    if (Array.isArray(children)) {
      children.forEach(visit);
    }
  };

  Object.values(content).forEach((block) => {
    if (!block || typeof block !== 'object') return;
    const value = block.value;
    if (!Array.isArray(value)) return;
    value.forEach(visit);
  });

  return ids;
};

const guessDisplayFromItem = (item) => {
  if (!item || typeof item !== 'object') {
    return { icon: FileText, title: 'Notebook item', subtitle: '', content: null, contentType: null };
  }

  const sourceMetadata = item.source_metadata || {};
  const documentType = sourceMetadata.document_type || '';

  // Handle D2 diagrams first (before generic document check)
  if (sourceMetadata.diagram_code || documentType === 'D2Diagram') {
    const code = String(sourceMetadata.diagram_code || '').trim();
    const firstLine = code.split('\n')[0] || '';
    const snippet = firstLine.length > 90 ? `${firstLine.slice(0, 87)}...` : firstLine;
    return {
      icon: LayoutGrid,
      title: sourceMetadata.diagram_name || sourceMetadata.document_name || 'Diagram',
      subtitle: snippet || 'D2 Diagram',
      content: code,
      contentType: 'diagram',
    };
  }

  // Handle Image documents
  if (documentType === 'Image' || item.content_type === 'documents.image') {
    const imageUrl = sourceMetadata.image_url || sourceMetadata.file_url || sourceMetadata.url || null;
    return {
      icon: Image,
      title: sourceMetadata.document_name || sourceMetadata.title || 'Image',
      subtitle: 'Image',
      content: imageUrl,
      contentType: 'image',
    };
  }

  // Handle Markdown documents
  if (documentType === 'Markdown' || documentType === 'MarkdownDocument') {
    const markdownContent = sourceMetadata.full_text || sourceMetadata.content || sourceMetadata.preview || null;
    return {
      icon: FileText,
      title: sourceMetadata.document_name || sourceMetadata.title || 'Markdown',
      subtitle: 'Markdown',
      content: markdownContent,
      contentType: 'markdown',
    };
  }

  // Handle generic documents
  if (item.content_type === 'documents.document') {
    const docContent = sourceMetadata.full_text || sourceMetadata.preview || null;
    return {
      icon: FileText,
      title: sourceMetadata.document_name || sourceMetadata.title || 'Document',
      subtitle: documentType || (item.object_id ? `Document #${item.object_id}` : 'Document'),
      content: docContent,
      contentType: 'document',
    };
  }

  // Handle messages (text snippets)
  const snippet =
    item.preview?.metadata?.text_snippet ||
    sourceMetadata.preview ||
    sourceMetadata.full_text ||
    '';

  if (snippet) {
    const trimmed = String(snippet).trim();
    return {
      icon: MessageSquare,
      title: trimmed.length > 80 ? `${trimmed.slice(0, 77)}...` : trimmed,
      subtitle: 'Message',
      content: trimmed,
      contentType: 'message',
    };
  }

  return { icon: FileText, title: 'Notebook item', subtitle: '', content: null, contentType: null };
};

function NotebookItemEmbed({ element, attributes, children }) {
  const options = useYooptaPluginOptions(PLUGIN_TYPE) || {};
  const [isExpanded, setIsExpanded] = useState(true); // Expanded by default

  const notebookItemId = useMemo(
    () => coerceNotebookItemId(element?.props?.notebook_item_id),
    [element?.props?.notebook_item_id]
  );

  const resolvedItem = useMemo(() => {
    if (!notebookItemId) return null;
    const resolver = options.resolveNotebookItem;
    return typeof resolver === 'function' ? resolver(notebookItemId) : null;
  }, [notebookItemId, options.resolveNotebookItem]);

  const { icon: Icon, title, subtitle, content, contentType } = useMemo(
    () => guessDisplayFromItem(resolvedItem),
    [resolvedItem]
  );

  const openCallback = options.onOpenNotebookItem;
  const canOpen = Boolean(resolvedItem && typeof openCallback === 'function');

  const handleToggle = () => {
    setIsExpanded((prev) => !prev);
  };

  const handleOpenClick = (e) => {
    e.stopPropagation();
    if (openCallback && resolvedItem) {
      openCallback(resolvedItem);
    }
  };

  // Render content based on type
  const renderContent = () => {
    if (!content) {
      return (
        <p className="text-sm text-muted-foreground italic">
          No preview available
        </p>
      );
    }

    if (contentType === 'image') {
      return (
        <div className="flex justify-center">
          <img
            src={content}
            alt={title || 'Image'}
            className="max-w-full max-h-48 object-contain rounded"
            onError={(e) => {
              e.target.style.display = 'none';
              e.target.nextSibling.style.display = 'block';
            }}
          />
          <p className="text-sm text-muted-foreground italic hidden">
            Image could not be loaded
          </p>
        </div>
      );
    }

    if (contentType === 'markdown') {
      return (
        <div className="prose prose-sm dark:prose-invert max-w-none">
          <MarkdownViewer content={content} />
        </div>
      );
    }

    if (contentType === 'diagram') {
      return (
        <pre className="text-sm font-mono whitespace-pre-wrap m-0 text-foreground overflow-x-auto">
          <code>{content}</code>
        </pre>
      );
    }

    if (contentType === 'message') {
      return (
        <p className="text-sm text-foreground whitespace-pre-wrap m-0">
          {content}
        </p>
      );
    }

    // document or default
    return (
      <p className="text-sm text-foreground whitespace-pre-wrap m-0 line-clamp-6">
        {content}
      </p>
    );
  };

  return (
    <div
      {...attributes}
      contentEditable={false}
      className="zoea-notebook-item-embed border border-border rounded-lg mb-2 overflow-hidden"
    >
      {/* Collapsible Header */}
      <div
        className="flex items-center justify-between px-3 py-2 bg-muted/50 cursor-pointer hover:bg-muted/70 transition-colors"
        onClick={handleToggle}
      >
        <div className="flex items-center gap-2 min-w-0">
          <button
            type="button"
            className="p-0 bg-transparent border-none flex-shrink-0"
            aria-label={isExpanded ? 'Collapse' : 'Expand'}
          >
            {isExpanded ? (
              <ChevronDown size={16} className="text-muted-foreground" />
            ) : (
              <ChevronRight size={16} className="text-muted-foreground" />
            )}
          </button>
          <Icon size={16} className="text-muted-foreground flex-shrink-0" />
          <div className="min-w-0 flex-1">
            <span className="text-sm font-medium text-foreground truncate block">
              {title || `Notebook item${notebookItemId ? ` #${notebookItemId}` : ''}`}
            </span>
            {subtitle && !isExpanded && (
              <span className="text-xs text-muted-foreground truncate block">
                {subtitle}
              </span>
            )}
          </div>
        </div>
        {canOpen && (
          <button
            type="button"
            className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground border border-border rounded px-2 py-1 bg-background hover:bg-muted transition-colors flex-shrink-0"
            onClick={handleOpenClick}
            title="Open item"
          >
            <ExternalLink size={12} />
            <span>Open</span>
          </button>
        )}
      </div>

      {/* Expanded Content */}
      {isExpanded && (
        <div className="p-3 bg-muted">
          {renderContent()}
        </div>
      )}

      {children}
    </div>
  );
}

export const NotebookItemCommands = {
  buildNotebookItemElements: (editor, { notebookItemId } = {}) => ({
    id: generateId(),
    type: ELEMENT_TYPE,
    children: [{ text: '' }],
    props: {
      nodeType: 'void',
      notebook_item_id: notebookItemId,
    },
  }),

  insertNotebookItem: (editor, { notebookItemId, at, focus = true } = {}) => {
    if (!editor || !notebookItemId) return null;
    const element = NotebookItemCommands.buildNotebookItemElements(editor, { notebookItemId });
    return editor.insertBlock(PLUGIN_TYPE, {
      at,
      focus,
      blockData: {
        value: [element],
        meta: { align: 'left', depth: 0 },
      },
    });
  },
};

/**
 * Base NotebookItem plugin instance.
 * Created once at module load time to ensure the plugin is properly initialized.
 */
const BaseNotebookItemPlugin = new YooptaPlugin({
  type: PLUGIN_TYPE,
  elements: {
    [ELEMENT_TYPE]: {
      render: NotebookItemEmbed,
      props: {
        nodeType: 'void',
        notebook_item_id: null,
      },
    },
  },
  options: {
    display: {
      title: 'Notebook Item',
      description: 'An embedded notebook item reference.',
    },
  },
});

/**
 * Factory to create a NotebookItem plugin with custom options.
 * Uses .extend() on the base plugin to add custom options.
 */
export const createNotebookItemPlugin = (options = {}) => {
  if (!options || Object.keys(options).length === 0) {
    return BaseNotebookItemPlugin;
  }
  return BaseNotebookItemPlugin.extend({
    options: {
      ...options,
    },
  });
};

// Default instance
export const NotebookItemPlugin = BaseNotebookItemPlugin;

export default NotebookItemPlugin;
