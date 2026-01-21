import { useState, useRef, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { ArrowLeft, Save, Upload } from 'lucide-react';
import LayoutFrame from '../components/layout/LayoutFrame';
import ViewPrimaryActions from '../components/layout/view/ViewPrimaryActions';
import MarkdownViewer from '../components/MarkdownViewer';
import { useWorkspaceStore, useDocumentStore } from '../stores';
import api from '../services/api';

function DocumentEditorPage() {
  const navigate = useNavigate();
  const currentProjectId = useWorkspaceStore((state) => state.currentProjectId);
  const currentWorkspaceId = useWorkspaceStore((state) => state.currentWorkspaceId);
  const currentWorkspace = useWorkspaceStore((state) => state.getCurrentWorkspace());
  const setCurrentDocumentId = useDocumentStore((state) => state.setCurrentDocumentId);

  const [title, setTitle] = useState('Untitled Document');
  const [description, setDescription] = useState('');
  const [content, setContent] = useState('# New Document');
  const [status, setStatus] = useState(null);
  const [isSaving, setIsSaving] = useState(false);
  const [folderOptions, setFolderOptions] = useState([]);
  const [selectedFolderId, setSelectedFolderId] = useState('');
  const fileInputRef = useRef(null);

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

  const handleSelectFile = () => {
    if (fileInputRef.current) {
      fileInputRef.current.click();
    }
  };

  const handleFileChange = (event) => {
    const file = event.target.files?.[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = (e) => {
      const text = e.target?.result?.toString() || '';
      setContent(text);
      if (title === 'Untitled Document') {
        setTitle(file.name.replace(/\.[^.]+$/, ''));
      }
      setStatus(`Loaded content from ${file.name}`);
    };
    reader.onerror = () => {
      setStatus('Failed to read the selected file.');
    };
    reader.readAsText(file);
  };

  const handleSave = async () => {
    if (!currentWorkspaceId || !currentProjectId) {
      setStatus('Select a project and workspace before saving.');
      return;
    }

    if (!content.trim()) {
      setStatus('Add some content before saving.');
      return;
    }

    setIsSaving(true);
    setStatus('Saving document...');
    try {
      const response = await api.createMarkdownDocument({
        name: title.trim() || 'Untitled Document',
        description,
        content,
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
        variant="outline"
        onClick={handleSelectFile}
        title="Import from file"
      >
        <Upload className="h-4 w-4" />
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
      title="New Markdown Document"
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

        <div className="flex flex-col lg:flex-row gap-4 flex-1 min-h-[520px]">
          <div className="bg-surface border border-border rounded-lg shadow-soft flex-1 min-h-[320px] min-w-0 overflow-hidden">
            <textarea
              className="w-full h-full p-4 bg-transparent text-text-primary font-mono text-sm resize-none focus:outline-none"
              value={content}
              onChange={(e) => setContent(e.target.value)}
              placeholder="Write your markdown here..."
            />
          </div>
          <div className="bg-surface border border-border rounded-lg shadow-soft w-full lg:w-[38%] min-h-[320px] overflow-auto">
            <div className="p-4 space-y-3">
              <h3 className="text-base font-semibold">Preview</h3>
              {content.trim() ? (
                <MarkdownViewer content={content} />
              ) : (
                <p className="text-sm text-text-secondary">Start typing to see a preview.</p>
              )}
            </div>
          </div>
        </div>
      </div>

      <input
        type="file"
        ref={fileInputRef}
        className="hidden"
        accept=".md,.markdown,.txt"
        onChange={handleFileChange}
      />
    </LayoutFrame>
  );
}

export default DocumentEditorPage;
