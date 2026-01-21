/**
 * Recent Canvas Documents Sidebar
 *
 * Displays a list of recent Excalidraw documents in the workspace
 * for quick access from the Canvas page.
 */

import { useState, useEffect, useCallback } from 'react';
import { FileImage, Loader2, RefreshCw, ChevronRight } from 'lucide-react';
import { useWorkspaceStore } from '../../stores';
import api from '../../services/api';

function RecentCanvasDocuments({ onDocumentSelect }) {
  const [documents, setDocuments] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);

  const currentProjectId = useWorkspaceStore((state) => state.currentProjectId);
  const currentWorkspaceId = useWorkspaceStore((state) => state.currentWorkspaceId);

  const loadDocuments = useCallback(async () => {
    if (!currentWorkspaceId) {
      setDocuments([]);
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      const response = await api.fetchDocuments({
        workspace_id: currentWorkspaceId,
        project_id: currentProjectId,
        document_type: 'ExcalidrawDiagram',
        page_size: 10,
        include_previews: false,
      });

      // Response includes documents array from paginated response
      setDocuments(response.documents || []);
    } catch (err) {
      console.error('Failed to fetch canvas documents:', err);
      setError('Failed to load documents');
      setDocuments([]);
    } finally {
      setIsLoading(false);
    }
  }, [currentProjectId, currentWorkspaceId]);

  // Load documents when workspace changes
  useEffect(() => {
    loadDocuments();
  }, [loadDocuments]);

  const handleDocumentClick = async (doc) => {
    if (!onDocumentSelect) return;

    try {
      // Fetch full document with content
      const fullDoc = await api.fetchDocument(doc.id);
      onDocumentSelect(fullDoc);
    } catch (err) {
      console.error('Failed to load document:', err);
      setError('Failed to load document');
    }
  };

  const formatDate = (dateStr) => {
    if (!dateStr) return '';
    const date = new Date(dateStr);
    const now = new Date();
    const diffMs = now - date;
    const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));

    if (diffDays === 0) {
      return 'Today';
    } else if (diffDays === 1) {
      return 'Yesterday';
    } else if (diffDays < 7) {
      return `${diffDays} days ago`;
    } else {
      return date.toLocaleDateString();
    }
  };

  if (!currentWorkspaceId) {
    return (
      <div className="text-xs text-text-secondary p-2">
        Select a workspace to see recent canvases.
      </div>
    );
  }

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between px-1">
        <span className="text-xs font-medium text-text-secondary">Recent Canvases</span>
        <button
          onClick={loadDocuments}
          disabled={isLoading}
          className="p-1 text-text-secondary hover:text-text-primary transition-colors"
          title="Refresh"
        >
          <RefreshCw className={`h-3 w-3 ${isLoading ? 'animate-spin' : ''}`} />
        </button>
      </div>

      {isLoading && documents.length === 0 ? (
        <div className="flex items-center justify-center py-4">
          <Loader2 className="h-4 w-4 animate-spin text-text-secondary" />
        </div>
      ) : error ? (
        <div className="text-xs text-red-500 px-2 py-1">{error}</div>
      ) : documents.length === 0 ? (
        <div className="text-xs text-text-secondary px-2 py-3 text-center">
          No canvas documents yet.
          <br />
          <span className="opacity-70">Save your first canvas to see it here.</span>
        </div>
      ) : (
        <ul className="space-y-1">
          {documents.map((doc) => (
            <li key={doc.id}>
              <button
                onClick={() => handleDocumentClick(doc)}
                className="w-full flex items-center gap-2 px-2 py-1.5 text-left text-sm rounded hover:bg-background transition-colors group"
              >
                <FileImage className="h-4 w-4 text-text-secondary flex-shrink-0" />
                <div className="flex-1 min-w-0">
                  <div className="truncate text-text-primary">{doc.name}</div>
                  <div className="text-xs text-text-secondary truncate">
                    {formatDate(doc.updated_at)}
                  </div>
                </div>
                <ChevronRight className="h-3 w-3 text-text-secondary opacity-0 group-hover:opacity-100 transition-opacity flex-shrink-0" />
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export default RecentCanvasDocuments;
