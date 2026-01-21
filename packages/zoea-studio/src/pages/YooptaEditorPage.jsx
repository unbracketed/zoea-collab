import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { ArrowLeft, Save } from 'lucide-react';
import LayoutFrame from '../components/layout/LayoutFrame';
import ViewPrimaryActions from '../components/layout/view/ViewPrimaryActions';
import YooptaEditor from '../components/documents/YooptaEditor';
import { useWorkspaceStore, useDocumentStore } from '../stores';
import api from '../services/api';

function YooptaEditorPage() {
  const navigate = useNavigate();
  const currentProjectId = useWorkspaceStore((state) => state.currentProjectId);
  const currentWorkspaceId = useWorkspaceStore((state) => state.currentWorkspaceId);
  const currentWorkspace = useWorkspaceStore((state) => state.getCurrentWorkspace());
  const setCurrentDocumentId = useDocumentStore((state) => state.setCurrentDocumentId);

  const [title, setTitle] = useState('Untitled Document');
  const [description, setDescription] = useState('');
  const [content, setContent] = useState(undefined);
  const [status, setStatus] = useState(null);
  const [isSaving, setIsSaving] = useState(false);
  const [folderOptions, setFolderOptions] = useState([]);
  const [selectedFolderId, setSelectedFolderId] = useState('');

  useEffect(() => {
    const loadFolders = async () => {
      if (!currentWorkspaceId) {
        setFolderOptions([]);
        return;
      }
      try {
        const data = await api.fetchFolders({ workspace_id: currentWorkspaceId });
        setFolderOptions(data);
      } catch (err) {
        console.error('Failed to load folders', err);
      }
    };
    loadFolders();
  }, [currentWorkspaceId]);

  const handleContentChange = (newContent) => {
    setContent(newContent);
  };

  const handleSave = async () => {
    if (!currentWorkspaceId || !currentProjectId) {
      setStatus('Select a project and workspace before saving.');
      return;
    }

    setIsSaving(true);
    setStatus('Saving document...');
    try {
      // Yoopta content can be undefined for empty docs - serialize appropriately
      const contentJson = content ? JSON.stringify(content) : '{}';
      const response = await api.createYooptaDocument({
        name: title.trim() || 'Untitled Document',
        description,
        content: contentJson,
        project_id: currentProjectId,
        workspace_id: currentWorkspaceId,
        folder_id: selectedFolderId ? Number(selectedFolderId) : null,
      });
      setCurrentDocumentId(response.id);
      setStatus('Document saved. Redirecting...');
      navigate(`/documents/${response.id}`);
    } catch (error) {
      setStatus(error.message || 'Failed to save document.');
    } finally {
      setIsSaving(false);
    }
  };

  const workspaceLabel = currentWorkspace?.name || 'No workspace selected';

  const actions = (
    <ViewPrimaryActions>
      <ViewPrimaryActions.Button
        variant="outline"
        onClick={() => navigate('/documents')}
        title="Back to documents"
      >
        <ArrowLeft className="h-4 w-4" />
      </ViewPrimaryActions.Button>
      <ViewPrimaryActions.Button
        onClick={handleSave}
        disabled={isSaving}
        title="Save document"
      >
        {isSaving ? (
          'Saving…'
        ) : (
          <span className="flex items-center gap-2">
            <Save className="h-4 w-4" />
            <span>Save</span>
          </span>
        )}
      </ViewPrimaryActions.Button>
    </ViewPrimaryActions>
  );

  return (
    <LayoutFrame
      title="New Rich Text Document"
      actions={actions}
      variant="content-centered"
      noPadding
    >
      <div className="flex flex-col flex-1 min-h-0 gap-4 p-6">
        <div className="flex flex-col sm:flex-row justify-between gap-2">
          <p className="text-sm text-text-secondary">
            Workspace: <strong>{workspaceLabel}</strong>
          </p>
          {status && <div className="text-xs text-primary">{status}</div>}
        </div>

        <div className="bg-surface border border-border rounded-lg shadow-soft p-4 space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="space-y-2 md:col-span-2">
              <label className="block text-sm font-medium mb-1">Title</label>
              <input
                type="text"
                className="w-full px-3 py-2 border border-border rounded-md bg-background focus:outline-none focus:ring-2 focus:ring-primary"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="Document title"
              />
            </div>
            <div className="space-y-2">
              <label className="block text-sm font-medium mb-1">Folder</label>
              <select
                className="w-full px-3 py-2 border border-border rounded-md bg-background focus:outline-none focus:ring-2 focus:ring-primary"
                value={selectedFolderId}
                onChange={(e) => setSelectedFolderId(e.target.value)}
                disabled={!currentWorkspaceId}
              >
                <option value="">(No folder)</option>
                {folderOptions.map((folder) => (
                  <option key={folder.id} value={folder.id}>
                    {folder.path}
                  </option>
                ))}
              </select>
            </div>
          </div>
          <div className="space-y-2">
            <label className="block text-sm font-medium mb-1">Description</label>
            <input
              type="text"
              className="w-full px-3 py-2 border border-border rounded-md bg-background focus:outline-none focus:ring-2 focus:ring-primary"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Optional description"
            />
          </div>
        </div>

        <div className="bg-surface border border-border rounded-lg shadow-soft flex-1 min-h-0 overflow-hidden">
          <YooptaEditor
            value={content}
            onChange={handleContentChange}
            placeholder="Start writing your document..."
            autoFocus
            className="h-full"
            projectId={currentProjectId}
            workspaceId={currentWorkspaceId}
          />
        </div>
      </div>
    </LayoutFrame>
  );
}

export default YooptaEditorPage;
