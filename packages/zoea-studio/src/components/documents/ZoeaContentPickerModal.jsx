/**
 * ZoeaContentPickerModal Component
 *
 * Modal for selecting Zoea content (documents, messages, diagrams) to insert
 * into the Notebook editor as embedded NotebookItem blocks.
 */

import { useCallback, useEffect, useState } from 'react';
import { FileText, MessageSquare, LayoutGrid, X, Search } from 'lucide-react';
import api from '../../services/api';

const TABS = [
  { id: 'documents', label: 'Documents', icon: FileText },
  { id: 'messages', label: 'Messages', icon: MessageSquare },
  { id: 'diagrams', label: 'Diagrams', icon: LayoutGrid },
];

function TabButton({ tab, active, onClick }) {
  const Icon = tab.icon;
  return (
    <button
      type="button"
      className={`flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-t-lg transition-colors ${
        active
          ? 'bg-surface border-b-2 border-primary text-primary'
          : 'text-text-secondary hover:text-text-primary hover:bg-background'
      }`}
      onClick={() => onClick(tab.id)}
    >
      <Icon className="h-4 w-4" />
      {tab.label}
    </button>
  );
}

function ContentItem({ item, type, onSelect }) {
  const getIcon = () => {
    switch (type) {
      case 'documents':
        return <FileText className="h-5 w-5 text-text-secondary" />;
      case 'messages':
        return <MessageSquare className="h-5 w-5 text-text-secondary" />;
      case 'diagrams':
        return <LayoutGrid className="h-5 w-5 text-text-secondary" />;
      default:
        return <FileText className="h-5 w-5 text-text-secondary" />;
    }
  };

  const getTitle = () => {
    switch (type) {
      case 'documents':
        return item.name || 'Untitled Document';
      case 'messages':
        return item.preview || item.text?.slice(0, 80) || 'Message';
      case 'diagrams':
        return item.name || 'Untitled Diagram';
      default:
        return 'Content Item';
    }
  };

  const getSubtitle = () => {
    switch (type) {
      case 'documents':
        return item.document_type || 'Document';
      case 'messages':
        return item.role || 'message';
      case 'diagrams':
        return 'D2 Diagram';
      default:
        return '';
    }
  };

  return (
    <button
      type="button"
      className="w-full flex items-center gap-3 p-3 text-left rounded-lg border border-border hover:bg-background transition-colors"
      onClick={() => onSelect(item, type)}
    >
      <div className="flex-shrink-0">{getIcon()}</div>
      <div className="flex-1 min-w-0">
        <div className="text-sm font-medium truncate">{getTitle()}</div>
        <div className="text-xs text-text-secondary">{getSubtitle()}</div>
      </div>
    </button>
  );
}

export default function ZoeaContentPickerModal({
  isOpen,
  onClose,
  onSelect,
  projectId,
  workspaceId,
}) {
  const [activeTab, setActiveTab] = useState('documents');
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [searchQuery, setSearchQuery] = useState('');

  // Load items when tab changes or modal opens
  useEffect(() => {
    if (!isOpen || !workspaceId) {
      setItems([]);
      return;
    }

    const loadItems = async () => {
      setLoading(true);
      setError(null);
      setItems([]);

      try {
        switch (activeTab) {
          case 'documents': {
            const response = await api.fetchDocuments({
              workspace_id: workspaceId,
              limit: 50,
            });
            setItems(response.documents || []);
            break;
          }
          case 'messages': {
            // Fetch recent conversations and their messages
            const convResponse = await api.fetchConversations({ workspace_id: workspaceId, limit: 5 });
            const conversations = convResponse.conversations || [];
            const allMessages = [];
            for (const conv of conversations) {
              const msgResponse = await api.fetchConversationDetail(conv.id);
              const messages = (msgResponse.messages || [])
                .filter((m) => m.role === 'assistant')
                .slice(-5);
              allMessages.push(...messages.map((m) => ({ ...m, conversation_id: conv.id })));
            }
            setItems(allMessages.slice(-20));
            break;
          }
          case 'diagrams': {
            // Fetch D2 diagrams from documents
            const response = await api.fetchDocuments({
              workspace_id: workspaceId,
              document_type: 'D2Diagram',
              limit: 50,
            });
            setItems(response.documents || []);
            break;
          }
          default:
            setItems([]);
        }
      } catch (err) {
        console.error('Failed to load content:', err);
        setError(err.message || 'Failed to load content');
      } finally {
        setLoading(false);
      }
    };

    loadItems();
  }, [isOpen, activeTab, workspaceId]);

  // Filter items by search query
  const filteredItems = items.filter((item) => {
    if (!searchQuery) return true;
    const query = searchQuery.toLowerCase();
    const name = (item.name || item.preview || item.text || '').toLowerCase();
    return name.includes(query);
  });

  const handleSelect = useCallback(
    (item, type) => {
      if (!onSelect) return;

      // Build the selection payload based on type
      switch (type) {
        case 'documents': {
          // Build metadata based on document type
          const docMetadata = {
            document_type: item.document_type,
            document_name: item.name,
          };

          // Add type-specific content for preview
          if (item.document_type === 'Image' && item.image_file) {
            docMetadata.image_url = item.image_file;
          } else if (item.document_type === 'Markdown' && item.content) {
            docMetadata.full_text = item.content;
          } else if (item.content) {
            // For other text documents (YooptaDocument, etc.)
            docMetadata.full_text = item.content;
          }

          onSelect({
            contentType: 'documents.document',
            objectId: item.id,
            metadata: docMetadata,
          });
          break;
        }
        case 'messages':
          onSelect({
            contentType: 'message',
            text: item.content || item.text,
            metadata: {
              role: item.role,
              conversation_id: item.conversation_id,
              preview: (item.content || item.text || '').slice(0, 180),
            },
          });
          break;
        case 'diagrams':
          onSelect({
            contentType: 'documents.document',
            objectId: item.id,
            metadata: {
              document_type: 'D2Diagram',
              document_name: item.name,
              diagram_code: item.content,
            },
          });
          break;
        default:
          break;
      }
      onClose();
    },
    [onSelect, onClose]
  );

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="bg-surface border border-border rounded-lg shadow-lg w-full max-w-2xl max-h-[80vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-border">
          <h2 className="text-lg font-semibold">Insert Zoea Content</h2>
          <button
            type="button"
            className="p-1 rounded hover:bg-background transition-colors"
            onClick={onClose}
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Tabs */}
        <div className="flex gap-1 px-4 pt-2 border-b border-border">
          {TABS.map((tab) => (
            <TabButton
              key={tab.id}
              tab={tab}
              active={activeTab === tab.id}
              onClick={setActiveTab}
            />
          ))}
        </div>

        {/* Search */}
        <div className="px-4 py-3">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-text-secondary" />
            <input
              type="text"
              placeholder="Search..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-10 pr-4 py-2 text-sm border border-border rounded-lg bg-background focus:outline-none focus:ring-2 focus:ring-primary/50"
            />
          </div>
        </div>

        {/* Content */}
        <div className="flex-1 min-h-0 overflow-auto px-4 pb-4">
          {loading && (
            <div className="flex items-center justify-center py-8 text-text-secondary">
              Loading...
            </div>
          )}

          {error && (
            <div className="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded">
              {error}
            </div>
          )}

          {!loading && !error && filteredItems.length === 0 && (
            <div className="flex items-center justify-center py-8 text-text-secondary">
              No content found
            </div>
          )}

          {!loading && !error && filteredItems.length > 0 && (
            <div className="grid gap-2">
              {filteredItems.map((item) => (
                <ContentItem
                  key={item.id || `${activeTab}-${Math.random()}`}
                  item={item}
                  type={activeTab}
                  onSelect={handleSelect}
                />
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
