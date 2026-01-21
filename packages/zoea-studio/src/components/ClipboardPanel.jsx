import { useEffect, useState } from 'react';
import { ClipboardList, RefreshCw, Plus, Trash2, List, LayoutGrid } from 'lucide-react';
import { useClipboardStore, useWorkspaceStore } from '../stores';
import { useShallow } from 'zustand/react/shallow';
import PreviewThumbnail from './PreviewThumbnail';

export function ClipboardSection({
  title,
  clipboard,
  items,
  loading,
  onRefresh,
  onCreate,
  onRemove,
}) {
  const [viewMode, setViewMode] = useState('list'); // 'list' or 'cards'
  const getItemPreview = (item) => {
    if (item.preview?.metadata?.text_snippet) {
      return item.preview.metadata.text_snippet;
    }

    if (item.content_type === 'documents.document' && item.source_metadata?.document_name) {
      return item.source_metadata.document_name;
    }

    if (item.source_metadata?.diagram_name) {
      return item.source_metadata.diagram_name;
    }

    if (item.source_metadata?.title) {
      return item.source_metadata.title;
    }

    return (
      item.source_metadata?.preview ||
      item.source_metadata?.full_text ||
      item.source_metadata?.document_name ||
      'Notebook item'
    );
  };

  return (
    <section className="clipboard-section">
      <div className="clipboard-section-header">
        <div>
          <h4>{title}</h4>
          {clipboard ? (
            <p className="clipboard-subtitle">{clipboard.name}</p>
          ) : (
            <p className="clipboard-subtitle">No active notebook</p>
          )}
        </div>
        <div className="flex items-center gap-2">
          {clipboard && items.length > 0 && (
            <div className="flex rounded-md border border-border" role="group">
              <button
                type="button"
                className={`px-2 py-1 text-sm transition-colors ${
                  viewMode === 'list'
                    ? 'bg-primary text-white'
                    : 'bg-transparent text-text-secondary hover:bg-surface-hover'
                }`}
                onClick={() => setViewMode('list')}
                title="List view"
              >
                <List size={16} />
              </button>
              <button
                type="button"
                className={`px-2 py-1 text-sm border-l border-border transition-colors ${
                  viewMode === 'cards'
                    ? 'bg-primary text-white'
                    : 'bg-transparent text-text-secondary hover:bg-surface-hover'
                }`}
                onClick={() => setViewMode('cards')}
                title="Cards view"
              >
                <LayoutGrid size={16} />
              </button>
            </div>
          )}
          {!clipboard && (
            <button
              type="button"
              className="px-2 py-1 text-sm bg-primary text-white rounded hover:opacity-90 transition-opacity flex items-center"
              onClick={onCreate}
            >
              <Plus size={14} className="mr-1" /> Create
            </button>
          )}
        </div>
      </div>

      {clipboard && items.length === 0 && (
        <div className="clipboard-empty">No items yet</div>
      )}

      {clipboard && items.length > 0 && viewMode === 'list' && (
        <ul className="clipboard-item-list">
          {items.map((item) => (
            <li key={item.id} className="clipboard-item">
              <div className="clipboard-item-meta">
                <span className="px-2 py-0.5 text-xs rounded bg-gray-100 text-gray-700">
                  {item.source_channel}
                </span>
                <span className="clipboard-item-date">
                  {new Date(item.created_at).toLocaleTimeString([], {
                    hour: 'numeric',
                    minute: '2-digit',
                  })}
                </span>
              </div>
              <div className="clipboard-item-preview">
                <PreviewThumbnail preview={item.preview} size="xs" />
                <div className="clipboard-item-preview-text">
                  {getItemPreview(item)}
                </div>
              </div>
              <div className="clipboard-item-actions">
                <button
                  type="button"
                  className="px-2 py-1 text-sm border border-red-500 text-red-500 rounded hover:bg-red-500 hover:text-white transition-colors"
                  onClick={() => onRemove(clipboard.id, item.id)}
                  title="Remove item"
                >
                  <Trash2 size={14} />
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}

      {clipboard && items.length > 0 && viewMode === 'cards' && (
        <div className="clipboard-cards-grid">
          {items.map((item) => (
            <div key={item.id} className="clipboard-card">
              <div className="clipboard-card-header">
                <span className="px-2 py-0.5 text-xs rounded bg-gray-100 text-gray-700">
                  {item.source_channel}
                </span>
                <button
                  type="button"
                  className="px-2 py-1 text-sm border border-red-500 text-red-500 rounded hover:bg-red-500 hover:text-white transition-colors"
                  onClick={() => onRemove(clipboard.id, item.id)}
                  title="Remove item"
                >
                  <Trash2 size={14} />
                </button>
              </div>
              <div className="clipboard-card-preview">
                <PreviewThumbnail preview={item.preview} size="md" />
              </div>
              <div className="clipboard-card-content">
                <p className="clipboard-card-text">{getItemPreview(item)}</p>
                <span className="clipboard-card-date">
                  {new Date(item.created_at).toLocaleString([], {
                    month: 'short',
                    day: 'numeric',
                    hour: 'numeric',
                    minute: '2-digit',
                  })}
                </span>
              </div>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}

function ClipboardPanel({ workspaceId }) {
  const fallbackWorkspaceId = useWorkspaceStore((state) => state.currentWorkspaceId);
  const resolvedWorkspaceId = workspaceId || fallbackWorkspaceId;

  const {
    clipboard,
    items,
    loading,
    error,
    loadClipboardsForWorkspace,
    refreshClipboardItems,
    createClipboard,
    removeClipboardItem,
  } = useClipboardStore(
    useShallow((state) => ({
      clipboard: state.clipboard,
      items: state.items,
      loading: state.loading,
      error: state.error,
      loadClipboardsForWorkspace: state.loadClipboardsForWorkspace,
      refreshClipboardItems: state.refreshClipboardItems,
      createClipboard: state.createClipboard,
      removeClipboardItem: state.removeClipboardItem,
    }))
  );

  useEffect(() => {
    if (resolvedWorkspaceId) {
      loadClipboardsForWorkspace(resolvedWorkspaceId);
    }
  }, [resolvedWorkspaceId, loadClipboardsForWorkspace]);

  if (!resolvedWorkspaceId) {
    return (
      <aside className="clipboard-panel clipboard-panel-empty">
        <div className="clipboard-panel-header">
          <ClipboardList size={18} />
          <span>Notebook</span>
        </div>
        <p className="clipboard-empty">Select a workspace to open your notebook.</p>
      </aside>
    );
  }

  const getItemTitle = (item) => {
    if (item.source_metadata?.document_name) {
      return item.source_metadata.document_name;
    }
    if (item.source_metadata?.diagram_name) {
      return item.source_metadata.diagram_name;
    }
    if (item.source_metadata?.title) {
      return item.source_metadata.title;
    }
    if (item.preview?.metadata?.text_snippet) {
      // Truncate to first 30 characters
      const snippet = item.preview.metadata.text_snippet;
      return snippet.length > 30 ? snippet.substring(0, 30) + '...' : snippet;
    }
    return 'Notebook item';
  };

  return (
    <aside className="clipboard-panel">
      <div className="clipboard-panel-header">
        <ClipboardList size={18} />
        <span>Notebook</span>
      </div>

      {error && (
        <div className="bg-red-100 border border-red-400 text-red-700 px-3 py-2 rounded text-sm clipboard-alert" role="alert">
          {error}
        </div>
      )}

      {!clipboard && (
        <div className="clipboard-section">
          <button
            type="button"
            className="w-full px-2 py-1 text-sm bg-primary text-white rounded hover:opacity-90 transition-opacity flex items-center justify-center"
            onClick={() => createClipboard(resolvedWorkspaceId)}
          >
            <Plus size={14} className="mr-1" /> Create Notebook
          </button>
        </div>
      )}

      {clipboard && items.length === 0 && (
        <div className="clipboard-empty">No items yet</div>
      )}

      {clipboard && items.length > 0 && (
        <div className="sidebar-clipboard-items">
          {items.map((item) => (
            <div key={item.id} className="sidebar-clipboard-item">
              <PreviewThumbnail preview={item.preview} size="xs" />
              <div className="sidebar-clipboard-item-text">
                <div className="sidebar-clipboard-item-title">{getItemTitle(item)}</div>
                <div className="sidebar-clipboard-item-meta">
                  <span className="px-2 py-0.5 text-xs rounded bg-gray-100 text-gray-700">{item.source_channel}</span>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </aside>
  );
}

export default ClipboardPanel;
