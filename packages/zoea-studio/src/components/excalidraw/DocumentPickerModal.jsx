/**
 * Document Picker Modal for Excalidraw
 *
 * Modal component for browsing and selecting project documents
 * to insert onto the Excalidraw canvas.
 */

import { useEffect, useState } from 'react';
import { X, Search, FileText, Image as ImageIcon, GitBranch, PenTool } from 'lucide-react';
import { useDocumentStore, useWorkspaceStore } from '../../stores';

const TYPE_ICONS = {
  Image: ImageIcon,
  Markdown: FileText,
  D2Diagram: FileText,
  MermaidDiagram: GitBranch,
  ExcalidrawDiagram: PenTool,
};

const TYPE_COLORS = {
  Image: 'text-green-500',
  Markdown: 'text-text-secondary',
  D2Diagram: 'text-blue-500',
  MermaidDiagram: 'text-green-500',
  ExcalidrawDiagram: 'text-purple-500',
};

export default function DocumentPickerModal({
  isOpen,
  onClose,
  onSelect,
  allowedTypes = null, // null means all types
  title = 'Insert from Documents',
}) {
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedType, setSelectedType] = useState('all');

  const documents = useDocumentStore((state) => state.recentDocuments) || [];
  const loadRecentDocuments = useDocumentStore((state) => state.loadRecentDocuments);
  const loading = useDocumentStore((state) => state.recentDocumentsLoading);
  const currentProjectId = useWorkspaceStore((state) => state.currentProjectId);

  useEffect(() => {
    if (isOpen && currentProjectId) {
      loadRecentDocuments(currentProjectId);
    }
  }, [isOpen, currentProjectId, loadRecentDocuments]);

  if (!isOpen) return null;

  // Filter documents
  const filteredDocuments = documents.filter((doc) => {
    // Type filter
    if (allowedTypes && !allowedTypes.includes(doc.document_type)) {
      return false;
    }
    if (selectedType !== 'all' && doc.document_type !== selectedType) {
      return false;
    }
    // Search filter
    if (searchQuery) {
      const query = searchQuery.toLowerCase();
      return (
        doc.name?.toLowerCase().includes(query) ||
        doc.description?.toLowerCase().includes(query)
      );
    }
    return true;
  });

  // Get unique types for filter
  const availableTypes = [...new Set(documents.map((d) => d.document_type))].filter(
    (t) => !allowedTypes || allowedTypes.includes(t)
  );

  const handleSelect = (doc) => {
    onSelect(doc);
    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="bg-surface rounded-lg shadow-xl w-full max-w-2xl max-h-[80vh] flex flex-col border border-border">
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-border">
          <h2 className="text-lg font-semibold">{title}</h2>
          <button
            onClick={onClose}
            className="p-1 rounded hover:bg-background text-text-secondary"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Search and filters */}
        <div className="px-4 py-3 border-b border-border space-y-3">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-text-secondary" />
            <input
              type="text"
              placeholder="Search documents..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-10 pr-4 py-2 rounded-md border border-border bg-background focus:outline-none focus:ring-2 focus:ring-primary"
            />
          </div>

          {availableTypes.length > 1 && (
            <div className="flex gap-2 flex-wrap">
              <button
                onClick={() => setSelectedType('all')}
                className={`px-3 py-1 text-sm rounded-full border ${
                  selectedType === 'all'
                    ? 'bg-primary text-white border-primary'
                    : 'border-border hover:bg-background'
                }`}
              >
                All
              </button>
              {availableTypes.map((type) => (
                <button
                  key={type}
                  onClick={() => setSelectedType(type)}
                  className={`px-3 py-1 text-sm rounded-full border ${
                    selectedType === type
                      ? 'bg-primary text-white border-primary'
                      : 'border-border hover:bg-background'
                  }`}
                >
                  {type}
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Document list */}
        <div className="flex-1 overflow-y-auto p-4">
          {loading ? (
            <div className="flex items-center justify-center py-8">
              <svg className="animate-spin h-6 w-6 text-primary" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" role="status">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
              </svg>
            </div>
          ) : filteredDocuments.length === 0 ? (
            <div className="text-center py-8 text-text-secondary">
              {searchQuery ? 'No documents match your search.' : 'No documents available.'}
            </div>
          ) : (
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
              {filteredDocuments.map((doc) => {
                const IconComponent = TYPE_ICONS[doc.document_type] || FileText;
                const iconColor = TYPE_COLORS[doc.document_type] || 'text-text-secondary';
                const previewUrl = doc.preview?.url || doc.image_file;

                return (
                  <button
                    key={doc.id}
                    onClick={() => handleSelect(doc)}
                    className="text-left border border-border rounded-lg overflow-hidden hover:border-primary hover:shadow-md transition bg-background"
                  >
                    {/* Preview */}
                    <div className="h-24 bg-surface flex items-center justify-center border-b border-border">
                      {previewUrl ? (
                        <img
                          src={previewUrl}
                          alt={doc.name}
                          className="w-full h-full object-cover"
                        />
                      ) : (
                        <IconComponent className={`h-8 w-8 ${iconColor}`} />
                      )}
                    </div>
                    {/* Info */}
                    <div className="p-2">
                      <p className="text-sm font-medium truncate">{doc.name}</p>
                      <p className="text-xs text-text-secondary">{doc.document_type}</p>
                    </div>
                  </button>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
