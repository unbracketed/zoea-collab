import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Plus, ClipboardList, Calendar, Clock } from 'lucide-react';
import LayoutFrame from '../components/layout/LayoutFrame';
import ViewPrimaryActions from '../components/layout/view/ViewPrimaryActions';
import { useWorkspaceStore } from '../stores';
import api from '../services/api';

function NotepadsListPage() {
  const navigate = useNavigate();
  const currentWorkspaceId = useWorkspaceStore((state) => state.currentWorkspaceId);
  const [clipboards, setClipboards] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!currentWorkspaceId) {
      setClipboards([]);
      setLoading(false);
      return;
    }

    const loadClipboards = async () => {
      setLoading(true);
      setError(null);
      try {
        const response = await api.fetchClipboards({
          workspace_id: currentWorkspaceId,
          include_recent: true,
        });
        setClipboards(response.clipboards || []);
      } catch (err) {
        console.error('Failed to load notebooks:', err);
        setError(err.message || 'Failed to load notebooks');
      } finally {
        setLoading(false);
      }
    };

    loadClipboards();
  }, [currentWorkspaceId]);

  const handleCreateNotebook = async () => {
    if (!currentWorkspaceId) return;
    try {
      await api.createClipboard({
        workspace_id: currentWorkspaceId,
        name: `Notebook ${new Date().toLocaleDateString()}`,
        activate: true,
      });
      // Refresh list
      const response = await api.fetchClipboards({
        workspace_id: currentWorkspaceId,
        include_recent: true,
      });
      setClipboards(response.clipboards || []);
    } catch (err) {
      console.error('Failed to create notebook:', err);
      alert(err.message || 'Failed to create notebook');
    }
  };

  const handleOpenNotebook = (clipboardId) => {
    navigate(`/notepad?clipboard=${clipboardId}`);
  };

  const formatDate = (dateString) => {
    if (!dateString) return '';
    const date = new Date(dateString);
    return date.toLocaleDateString(undefined, {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
    });
  };

  const formatTime = (dateString) => {
    if (!dateString) return '';
    const date = new Date(dateString);
    return date.toLocaleTimeString(undefined, {
      hour: 'numeric',
      minute: '2-digit',
    });
  };

  const actions = (
    <ViewPrimaryActions>
      <ViewPrimaryActions.Button
        variant="primary"
        onClick={handleCreateNotebook}
        disabled={!currentWorkspaceId}
        title="Create new notebook"
      >
        <span className="flex items-center gap-2">
          <Plus className="h-4 w-4" />
          <span>New Notebook</span>
        </span>
      </ViewPrimaryActions.Button>
    </ViewPrimaryActions>
  );

  const content = !currentWorkspaceId ? (
    <div className="bg-blue-100 border border-blue-400 text-blue-700 px-4 py-3 rounded" role="alert">
      Choose a project and workspace from the sidebar to view notebooks.
    </div>
  ) : loading ? (
    <div className="flex items-center justify-center py-12">
      <div className="text-text-secondary">Loading notebooks...</div>
    </div>
  ) : error ? (
    <div className="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded" role="alert">
      {error}
    </div>
  ) : clipboards.length === 0 ? (
    <div className="text-center py-12">
      <ClipboardList className="h-12 w-12 mx-auto text-text-secondary mb-4" />
      <h3 className="text-lg font-medium mb-2">No notebooks yet</h3>
      <p className="text-text-secondary mb-4">
        Create a notebook to start collecting notes and content.
      </p>
      <button
        onClick={handleCreateNotebook}
        className="inline-flex items-center gap-2 px-4 py-2 bg-primary text-white rounded-lg hover:bg-primary/90 transition-colors"
      >
        <Plus className="h-4 w-4" />
        Create Notebook
      </button>
    </div>
  ) : (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {clipboards.map((clipboard) => (
        <button
          key={clipboard.id}
          onClick={() => handleOpenNotebook(clipboard.id)}
          className="bg-surface border border-border rounded-lg p-4 text-left hover:border-primary/50 hover:shadow-soft transition-all group"
        >
          <div className="flex items-start gap-3">
            <div className="p-2 bg-primary/10 rounded-lg text-primary">
              <ClipboardList className="h-5 w-5" />
            </div>
            <div className="flex-1 min-w-0">
              <h3 className="font-medium truncate group-hover:text-primary transition-colors">
                {clipboard.name || 'Untitled Notebook'}
              </h3>
              {clipboard.description && (
                <p className="text-sm text-text-secondary truncate mt-0.5">
                  {clipboard.description}
                </p>
              )}
              <div className="flex items-center gap-4 mt-2 text-xs text-text-secondary">
                <span className="flex items-center gap-1">
                  <Calendar className="h-3 w-3" />
                  {formatDate(clipboard.created_at)}
                </span>
                {clipboard.updated_at !== clipboard.created_at && (
                  <span className="flex items-center gap-1">
                    <Clock className="h-3 w-3" />
                    {formatTime(clipboard.updated_at)}
                  </span>
                )}
              </div>
            </div>
          </div>
          {clipboard.is_active && (
            <div className="mt-3 pt-3 border-t border-border">
              <span className="text-xs font-medium text-primary bg-primary/10 px-2 py-0.5 rounded">
                Active
              </span>
            </div>
          )}
        </button>
      ))}
    </div>
  );

  return (
    <LayoutFrame title="All Notebooks" actions={actions} variant="content-centered">
      {content}
    </LayoutFrame>
  );
}

export default NotepadsListPage;
