import { useEffect, useState, useMemo } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { Trash2 } from 'lucide-react';
import api from '../services/api';

function buildTree(items) {
  const map = {};
  items.forEach((item) => {
    map[item.id] = { ...item, children: [] };
  });
  const roots = [];
  items.forEach((item) => {
    if (item.parent_id && map[item.parent_id]) {
      map[item.parent_id].children.push(map[item.id]);
    } else {
      roots.push(map[item.id]);
    }
  });
  return roots;
}

export default function FolderSidebar({ workspaceId, activeFolderId, onSelectFolder, refreshKey, newButton }) {
  const location = useLocation();
  const navigate = useNavigate();
  const [folders, setFolders] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const isTrashActive = location.pathname === '/documents/trash';

  useEffect(() => {
    if (!workspaceId) {
      setFolders([]);
      return;
    }

    const load = async () => {
      try {
        setLoading(true);
        setError(null);
        const data = await api.fetchFolders({ workspace_id: workspaceId });
        setFolders(data);
      } catch (err) {
        console.error('Failed to load folders', err);
        const errorMsg = err?.message || (err instanceof Error ? err.toString() : JSON.stringify(err));
        setError(errorMsg);
      } finally {
        setLoading(false);
      }
    };

    load();
  }, [workspaceId, refreshKey]);

  const tree = useMemo(() => buildTree(folders), [folders]);
  const folderMap = useMemo(() => {
    const map = {};
    folders.forEach((f) => {
      map[f.id] = f;
    });
    return map;
  }, [folders]);

  const handleSelect = (folder) => {
    if (!folder) {
      onSelectFolder(null);
      return;
    }
    onSelectFolder(folder);
  };

  const renderNodes = (nodes, depth = 0) => {
    return nodes.map((node) => (
      <div key={node.id} style={{ paddingLeft: depth * 12 }}>
        <button
          type="button"
          className={`w-full text-left px-2 py-1.5 text-sm rounded-md transition-colors ${activeFolderId === node.id ? 'bg-primary text-primary-foreground font-medium' : 'text-text-primary hover:bg-background'}`}
          onClick={() => handleSelect(folderMap[node.id])}
        >
          {node.name}
        </button>
        {node.children && node.children.length > 0 && renderNodes(node.children, depth + 1)}
      </div>
    ));
  };

  return (
    <div className="h-full flex flex-col">
      {/* New button slot */}
      {newButton && <div className="mb-3">{newButton}</div>}

      {/* Folder tree */}
      <div className="flex-1 overflow-y-auto">
        {error && <div className="text-xs text-red-500 mb-2">{error}</div>}
        {!workspaceId && <div className="text-xs text-text-secondary px-2">Select a workspace to manage folders.</div>}
        {workspaceId && (
          <div className="space-y-0.5">
            <button
              type="button"
              className={`w-full text-left px-2 py-1.5 text-sm rounded-md transition-colors ${!activeFolderId && !isTrashActive ? 'bg-primary text-primary-foreground font-medium' : 'text-text-primary hover:bg-background'}`}
              onClick={() => handleSelect(null)}
            >
              All Documents
            </button>
            {loading && <div className="text-xs text-text-secondary px-2 py-1">Loading folders...</div>}
            {!loading && renderNodes(tree)}
          </div>
        )}
      </div>

      {/* Trash link */}
      <div className="border-t border-border pt-2 mt-2">
        <button
          type="button"
          className={`w-full flex items-center gap-2 px-2 py-1.5 text-sm rounded-md transition-colors ${
            isTrashActive
              ? 'bg-primary text-primary-foreground font-medium'
              : 'text-text-primary hover:bg-background'
          }`}
          onClick={() => navigate('/documents/trash')}
        >
          <Trash2 className="h-4 w-4" />
          Trash
        </button>
      </div>
    </div>
  );
}
