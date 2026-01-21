import { useCallback, useEffect, useRef, useState } from 'react';
import { useNavigate, useNavigationType, useParams } from 'react-router-dom';
import toast from 'react-hot-toast';
import LayoutFrame from '../components/layout/LayoutFrame';
import DocumentsList from '../components/documents/DocumentsList';
import DocumentFiltersBar from '../components/documents/DocumentFiltersBar';
import NewDocumentButton from '../components/documents/NewDocumentButton';
import RenameDocumentModal from '../components/documents/RenameDocumentModal';
import ChangeFolderModal from '../components/documents/ChangeFolderModal';
import ImportDocumentsModal from '../components/documents/ImportDocumentsModal';
import FolderSidebar from '../components/FolderSidebar';
import { DocumentRAGModal } from '../components/document-rag';
import { useDocumentStore, useWorkspaceStore, useClipboardStore, useDocumentSelectionStore } from '../stores';
import api from '../services/api';

function DocumentsPage() {
  const navigate = useNavigate();
  const navigationType = useNavigationType();
  const { folderId: urlFolderId } = useParams();
  const hasRedirected = useRef(false);
  const currentDocumentId = useDocumentStore((state) => state.currentDocumentId);
  const currentWorkspaceId = useWorkspaceStore((state) => state.currentWorkspaceId);
  const currentProjectId = useWorkspaceStore((state) => state.currentProjectId);
  const addDocumentToClipboard = useClipboardStore((state) => state.addModelToClipboard);
  const [activeFolder, setActiveFolder] = useState(null);
  const [folderRefreshKey, setFolderRefreshKey] = useState(0);
  const [ragModalOpen, setRagModalOpen] = useState(false);
  const [ragContext, setRagContext] = useState(null);
  const [viewMode, setViewMode] = useState('grid');
  const [documentsRefreshKey, setDocumentsRefreshKey] = useState(0);
  const [importModalOpen, setImportModalOpen] = useState(false);
  const [importMode, setImportMode] = useState('directory');

  // Modal state for document actions
  const [renameModalOpen, setRenameModalOpen] = useState(false);
  const [changeFolderModalOpen, setChangeFolderModalOpen] = useState(false);
  const [targetDocument, setTargetDocument] = useState(null);
  const [bulkDocumentIds, setBulkDocumentIds] = useState(null);

  // Selection store
  const getSelectedIds = useDocumentSelectionStore((state) => state.getSelectedIds);
  const clearSelection = useDocumentSelectionStore((state) => state.clearSelection);

  // Load folder from URL if urlFolderId is provided
  useEffect(() => {
    if (urlFolderId) {
      api.fetchFolder(urlFolderId)
        .then((folder) => setActiveFolder(folder))
        .catch((err) => {
          console.error('Failed to load folder:', err);
          navigate('/documents', { replace: true });
        });
    } else {
      setActiveFolder(null);
    }
  }, [urlFolderId, navigate]);

  // Reset active folder when workspace/project changes
  useEffect(() => {
    if (!urlFolderId) {
      setActiveFolder(null);
    }
  }, [currentWorkspaceId, currentProjectId, urlFolderId]);

  // If there's a current document, redirect to show it (only once)
  useEffect(() => {
    // Do not auto-redirect when arriving via browser back/forward (POP)
    if (navigationType === 'POP') return;
    if (currentDocumentId && !hasRedirected.current) {
      hasRedirected.current = true;
      navigate(`/documents/${currentDocumentId}`, { replace: true });
    }
  }, [currentDocumentId, navigate, navigationType]);

  const handleFolderCreated = () => {
    setFolderRefreshKey((k) => k + 1);
  };

  const handleChatWithDocuments = () => {
    // If a folder is active, chat with folder contents; otherwise use workspace root
    if (activeFolder) {
      setRagContext({
        type: 'folder',
        id: activeFolder.id,
        name: activeFolder.name,
      });
      setRagModalOpen(true);
    } else {
      // For "all documents", we'll use the workspace ID as a virtual folder context
      // This requires backend support - for now, show an alert
      alert('Please select a folder to chat with its documents.');
    }
  };

  const handleFolderSelect = (folder) => {
    setActiveFolder(folder);
    if (folder) {
      navigate(`/documents/folder/${folder.id}`, { replace: true });
    } else {
      navigate('/documents', { replace: true });
    }
  };

  const handleAddToClipboard = async (doc) => {
    try {
      // Build metadata with type-specific content for preview
      const metadata = {
        document_type: doc.document_type,
        document_name: doc.name,
      };
      if (doc.document_type === 'Image' && doc.image_file) {
        metadata.image_url = doc.image_file;
      } else if (doc.content) {
        metadata.full_text = doc.content;
      }

      await addDocumentToClipboard({
        workspaceId: currentWorkspaceId,
        contentType: 'documents.document',
        objectId: doc.id,
        metadata,
      });
      toast.success('Added to notepad');
    } catch (error) {
      console.error('Failed to add to notepad:', error);
      toast.error('Failed to add to notepad');
    }
  };

  // Document action handlers
  const handleRename = useCallback((doc) => {
    setTargetDocument(doc);
    setRenameModalOpen(true);
  }, []);

  const handleChangeFolder = useCallback((doc) => {
    setTargetDocument(doc);
    setChangeFolderModalOpen(true);
  }, []);

  const handleMoveToTrash = useCallback(async (doc) => {
    try {
      await api.trashDocument(doc.id);
      toast.success('Moved to trash');
      setDocumentsRefreshKey((k) => k + 1);
    } catch (error) {
      console.error('Failed to move to trash:', error);
      toast.error(error.message || 'Failed to move to trash');
    }
  }, []);

  const handleRenameSuccess = useCallback(() => {
    setDocumentsRefreshKey((k) => k + 1);
  }, []);

  const handleChangeFolderSuccess = useCallback(() => {
    setDocumentsRefreshKey((k) => k + 1);
  }, []);

  const handleImportDirectory = useCallback(() => {
    setImportMode('directory');
    setImportModalOpen(true);
  }, []);

  const handleImportArchive = useCallback(() => {
    setImportMode('archive');
    setImportModalOpen(true);
  }, []);

  const handleImportSuccess = useCallback(() => {
    setDocumentsRefreshKey((k) => k + 1);
    setFolderRefreshKey((k) => k + 1);
  }, []);

  // Bulk action handlers
  const handleBulkMove = useCallback(() => {
    const ids = getSelectedIds();
    if (ids.length === 0) return;
    setBulkDocumentIds(ids);
    setTargetDocument(null);
    setChangeFolderModalOpen(true);
  }, [getSelectedIds]);

  const handleBulkAddToNotebook = useCallback(async () => {
    const ids = getSelectedIds();
    if (ids.length === 0) return;

    try {
      // Fetch and add each selected document to clipboard
      for (const docId of ids) {
        // Fetch document details to get proper metadata for preview
        const doc = await api.fetchDocument(docId, { include_preview: true });

        // Build metadata with type-specific content for preview
        const metadata = {
          document_type: doc.document_type,
          document_name: doc.name,
        };
        if (doc.document_type === 'Image' && doc.image_file) {
          metadata.image_url = doc.image_file;
        } else if (doc.content) {
          metadata.full_text = doc.content;
        }

        await addDocumentToClipboard({
          workspaceId: currentWorkspaceId,
          contentType: 'documents.document',
          objectId: docId,
          metadata,
        });
      }
      toast.success(`Added ${ids.length} document${ids.length > 1 ? 's' : ''} to notepad`);
      clearSelection();
    } catch (error) {
      console.error('Failed to add to notepad:', error);
      toast.error('Failed to add to notepad');
    }
  }, [getSelectedIds, addDocumentToClipboard, currentWorkspaceId, clearSelection]);

  const handleBulkMoveToTrash = useCallback(async () => {
    const ids = getSelectedIds();
    if (ids.length === 0) return;

    // Confirm for multiple documents
    if (ids.length > 1) {
      const confirmed = window.confirm(
        `Move ${ids.length} documents to trash?`
      );
      if (!confirmed) return;
    }

    try {
      // Trash each selected document
      await Promise.all(ids.map((id) => api.trashDocument(id)));
      toast.success(`Moved ${ids.length} document${ids.length > 1 ? 's' : ''} to trash`);
      clearSelection();
      setDocumentsRefreshKey((k) => k + 1);
    } catch (error) {
      console.error('Failed to move to trash:', error);
      toast.error(error.message || 'Failed to move to trash');
    }
  }, [getSelectedIds, clearSelection]);

  const newButton = (
    <NewDocumentButton
      workspaceId={currentWorkspaceId}
      parentFolderId={activeFolder?.id || null}
      onFolderCreated={handleFolderCreated}
      onChatWithDocuments={handleChatWithDocuments}
      onImportDirectory={handleImportDirectory}
      onImportArchive={handleImportArchive}
    />
  );

  const sidebarContent = (
    <FolderSidebar
      workspaceId={currentWorkspaceId}
      activeFolderId={activeFolder?.id || null}
      onSelectFolder={handleFolderSelect}
      refreshKey={folderRefreshKey}
      newButton={newButton}
    />
  );

  return (
    <>
      <LayoutFrame
        title="Documents"
        variant="full"
        noPadding={true}
        hideHeader={true}
        sidebar={sidebarContent}
        viewSidebarTitle="Folders"
      >
        <div className="h-full flex flex-col">
          <DocumentFiltersBar
            folder={activeFolder}
            workspaceId={currentWorkspaceId}
            projectId={currentProjectId}
            viewMode={viewMode}
            onViewModeChange={setViewMode}
            onBulkMove={handleBulkMove}
            onBulkAddToNotebook={handleBulkAddToNotebook}
            onBulkMoveToTrash={handleBulkMoveToTrash}
          />
          <div className="flex-1 overflow-auto p-3">
            <DocumentsList
              key={documentsRefreshKey}
              folderId={activeFolder?.id || null}
              projectId={currentProjectId}
              workspaceId={currentWorkspaceId}
              viewMode={viewMode}
              onAddToClipboard={handleAddToClipboard}
              onRename={handleRename}
              onChangeFolder={handleChangeFolder}
              onMoveToTrash={handleMoveToTrash}
            />
          </div>
        </div>
      </LayoutFrame>
      <DocumentRAGModal
        isOpen={ragModalOpen}
        onClose={() => setRagModalOpen(false)}
        contextType={ragContext?.type}
        contextId={ragContext?.id}
        contextName={ragContext?.name}
      />
      <RenameDocumentModal
        isOpen={renameModalOpen}
        onClose={() => setRenameModalOpen(false)}
        document={targetDocument}
        onSuccess={handleRenameSuccess}
      />
      <ChangeFolderModal
        isOpen={changeFolderModalOpen}
        onClose={() => {
          setChangeFolderModalOpen(false);
          setBulkDocumentIds(null);
        }}
        document={targetDocument}
        documentIds={bulkDocumentIds}
        workspaceId={currentWorkspaceId}
        onFolderCreated={handleFolderCreated}
        onSuccess={() => {
          handleChangeFolderSuccess();
          if (bulkDocumentIds) {
            clearSelection();
            setBulkDocumentIds(null);
          }
        }}
      />
      <ImportDocumentsModal
        isOpen={importModalOpen}
        mode={importMode}
        onClose={() => setImportModalOpen(false)}
        projectId={currentProjectId}
        workspaceId={currentWorkspaceId}
        folderId={activeFolder?.id || null}
        folderPath={activeFolder?.path || null}
        onSuccess={handleImportSuccess}
      />
    </>
  );
}

export default DocumentsPage;
