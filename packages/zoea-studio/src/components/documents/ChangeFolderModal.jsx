/**
 * Change Folder Modal
 *
 * Modal for moving a document to a different folder.
 * Includes inline folder creation.
 */

import { useEffect, useMemo, useRef, useState } from 'react'
import { X, Folder, FolderOpen, FolderPlus, Check } from 'lucide-react'
import toast from 'react-hot-toast'
import api from '../../services/api'

function buildTree(items) {
  const map = {}
  items.forEach((item) => {
    map[item.id] = { ...item, children: [] }
  })
  const roots = []
  items.forEach((item) => {
    if (item.parent_id && map[item.parent_id]) {
      map[item.parent_id].children.push(map[item.id])
    } else {
      roots.push(map[item.id])
    }
  })
  return roots
}

function ChangeFolderModal({ isOpen, onClose, document, documentIds, workspaceId, onSuccess, onFolderCreated }) {
  const isBulkMode = Array.isArray(documentIds) && documentIds.length > 0
  const documentCount = isBulkMode ? documentIds.length : 1
  const [folders, setFolders] = useState([])
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState(null)
  const [selectedFolderId, setSelectedFolderId] = useState(null)

  // New folder creation state
  const [isCreatingFolder, setIsCreatingFolder] = useState(false)
  const [newFolderName, setNewFolderName] = useState('')
  const [creatingFolder, setCreatingFolder] = useState(false)
  const newFolderInputRef = useRef(null)

  // Reset form when modal opens
  useEffect(() => {
    if (isOpen) {
      // For single document, pre-select current folder; for bulk, start with null
      if (document && !isBulkMode) {
        setSelectedFolderId(document.folder_id || null)
      } else {
        setSelectedFolderId(null)
      }
      setError(null)
      setSaving(false)
      setIsCreatingFolder(false)
      setNewFolderName('')
    }
  }, [isOpen, document, isBulkMode])

  // Load folders when modal opens
  const loadFolders = async () => {
    if (!workspaceId) return
    setLoading(true)
    try {
      const result = await api.fetchFolders({ workspace_id: workspaceId })
      setFolders(result || [])
    } catch (err) {
      console.error('Failed to load folders:', err)
      setFolders([])
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    if (!isOpen || !workspaceId) return
    loadFolders()
  }, [isOpen, workspaceId])

  const tree = useMemo(() => buildTree(folders), [folders])

  // Focus input when creating folder
  useEffect(() => {
    if (isCreatingFolder && newFolderInputRef.current) {
      newFolderInputRef.current.focus()
    }
  }, [isCreatingFolder])

  // Close on escape key
  useEffect(() => {
    const handleEscape = (event) => {
      if (event.key === 'Escape' && isOpen && !saving && !creatingFolder) {
        if (isCreatingFolder) {
          setIsCreatingFolder(false)
          setNewFolderName('')
        } else {
          onClose()
        }
      }
    }

    window.addEventListener('keydown', handleEscape)
    return () => window.removeEventListener('keydown', handleEscape)
  }, [isOpen, onClose, saving, creatingFolder, isCreatingFolder])

  // Close when clicking outside
  const handleBackdropClick = (event) => {
    if (event.target === event.currentTarget && !saving && !creatingFolder) {
      onClose()
    }
  }

  const handleCreateFolder = async () => {
    if (!newFolderName.trim() || !workspaceId) return

    setCreatingFolder(true)
    try {
      const newFolder = await api.createFolder({
        name: newFolderName.trim(),
        workspace_id: workspaceId,
        parent_id: selectedFolderId,
      })
      toast.success('Folder created')
      // Reload folders and select the new one
      await loadFolders()
      setSelectedFolderId(newFolder.id)
      setIsCreatingFolder(false)
      setNewFolderName('')
      // Notify parent to refresh sidebar
      onFolderCreated?.()
    } catch (err) {
      console.error('Failed to create folder:', err)
      toast.error(err.message || 'Failed to create folder')
    } finally {
      setCreatingFolder(false)
    }
  }

  const handleNewFolderKeyDown = (event) => {
    if (event.key === 'Enter') {
      event.preventDefault()
      handleCreateFolder()
    } else if (event.key === 'Escape') {
      setIsCreatingFolder(false)
      setNewFolderName('')
    }
  }

  const handleSave = async () => {
    // For single document mode, don't save if folder hasn't changed
    if (!isBulkMode && selectedFolderId === (document?.folder_id || null)) {
      onClose()
      return
    }

    setSaving(true)
    setError(null)

    try {
      if (isBulkMode) {
        // Move all selected documents
        await Promise.all(
          documentIds.map((id) => api.moveDocument(id, { folder_id: selectedFolderId }))
        )
        toast.success(`Moved ${documentCount} document${documentCount > 1 ? 's' : ''}`)
      } else {
        await api.moveDocument(document.id, { folder_id: selectedFolderId })
        toast.success('Document moved')
      }
      onSuccess?.()
      onClose()
    } catch (err) {
      console.error('Failed to move document:', err)
      setError(err.message || 'Failed to move document')
      setSaving(false)
    }
  }

  const renderNodes = (nodes, depth = 0) => {
    return nodes.map((node) => {
      const isSelected = selectedFolderId === node.id
      const isCurrent = !isBulkMode && document?.folder_id === node.id

      return (
        <div key={node.id} style={{ paddingLeft: depth * 16 }}>
          <button
            type="button"
            className={`w-full text-left px-3 py-2 text-sm rounded-lg transition-colors flex items-center gap-2 ${
              isSelected
                ? 'bg-primary/10 text-primary font-medium'
                : 'text-text-primary hover:bg-muted'
            }`}
            onClick={() => setSelectedFolderId(node.id)}
            disabled={saving || creatingFolder}
          >
            {isSelected ? (
              <FolderOpen className="h-4 w-4 flex-shrink-0" />
            ) : (
              <Folder className="h-4 w-4 flex-shrink-0" />
            )}
            <span className="truncate">{node.name}</span>
            {isCurrent && (
              <span className="text-xs text-muted-foreground ml-auto">(current)</span>
            )}
          </button>
          {node.children && node.children.length > 0 && renderNodes(node.children, depth + 1)}
        </div>
      )
    })
  }

  if (!isOpen) return null

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50"
      onClick={handleBackdropClick}
    >
      <div
        className="bg-card text-card-foreground rounded-xl shadow-lg border border-border w-full max-w-md mx-4 overflow-hidden"
        role="dialog"
        aria-modal="true"
        aria-labelledby="change-folder-title"
      >
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-border">
          <h2 id="change-folder-title" className="text-lg font-semibold">
            {isBulkMode
              ? `Move ${documentCount} document${documentCount > 1 ? 's' : ''}`
              : 'Move to folder'}
          </h2>
          <button
            type="button"
            onClick={onClose}
            disabled={saving || creatingFolder}
            className="p-1 rounded-md hover:bg-muted text-muted-foreground hover:text-foreground transition-colors disabled:opacity-50"
            aria-label="Close"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Content */}
        <div className="p-4">
          {/* Error display */}
          {error && (
            <div className="p-3 rounded-lg bg-red-500/10 text-red-500 text-sm mb-4">
              {error}
            </div>
          )}

          {/* Folder Tree */}
          <div className="max-h-80 overflow-y-auto border border-border rounded-lg">
            {loading ? (
              <div className="p-4 text-sm text-muted-foreground text-center">
                Loading folders...
              </div>
            ) : (
              <div className="p-2 space-y-0.5">
                {/* Root option */}
                <button
                  type="button"
                  className={`w-full text-left px-3 py-2 text-sm rounded-lg transition-colors flex items-center gap-2 ${
                    selectedFolderId === null
                      ? 'bg-primary/10 text-primary font-medium'
                      : 'text-text-primary hover:bg-muted'
                  }`}
                  onClick={() => setSelectedFolderId(null)}
                  disabled={saving || creatingFolder}
                >
                  {selectedFolderId === null ? (
                    <FolderOpen className="h-4 w-4 flex-shrink-0" />
                  ) : (
                    <Folder className="h-4 w-4 flex-shrink-0" />
                  )}
                  <span>Root (no folder)</span>
                  {!isBulkMode && !document?.folder_id && (
                    <span className="text-xs text-muted-foreground ml-auto">(current)</span>
                  )}
                </button>
                {renderNodes(tree)}
                {!loading && folders.length === 0 && (
                  <div className="px-3 py-2 text-sm text-muted-foreground">
                    No folders available
                  </div>
                )}
              </div>
            )}
          </div>

          {/* New Folder Section */}
          <div className="mt-3">
            {isCreatingFolder ? (
              <div className="flex items-center gap-2">
                <FolderPlus className="h-4 w-4 text-muted-foreground flex-shrink-0" />
                <input
                  ref={newFolderInputRef}
                  type="text"
                  value={newFolderName}
                  onChange={(e) => setNewFolderName(e.target.value)}
                  onKeyDown={handleNewFolderKeyDown}
                  placeholder="Folder name"
                  disabled={creatingFolder}
                  className="flex-1 px-2 py-1.5 text-sm border border-border rounded-md bg-background focus:outline-none focus:ring-2 focus:ring-primary/50 disabled:opacity-50"
                />
                <button
                  type="button"
                  onClick={handleCreateFolder}
                  disabled={!newFolderName.trim() || creatingFolder}
                  className="p-1.5 rounded-md bg-primary text-white hover:bg-primary/90 transition-colors disabled:opacity-50"
                  aria-label="Create folder"
                >
                  <Check className="h-4 w-4" />
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setIsCreatingFolder(false)
                    setNewFolderName('')
                  }}
                  disabled={creatingFolder}
                  className="p-1.5 rounded-md hover:bg-muted text-muted-foreground hover:text-foreground transition-colors disabled:opacity-50"
                  aria-label="Cancel"
                >
                  <X className="h-4 w-4" />
                </button>
              </div>
            ) : (
              <button
                type="button"
                onClick={() => setIsCreatingFolder(true)}
                disabled={saving || loading}
                className="flex items-center gap-2 text-sm text-muted-foreground hover:text-primary transition-colors disabled:opacity-50"
              >
                <FolderPlus className="h-4 w-4" />
                <span>New folder{selectedFolderId !== null ? ' (in selected)' : ''}</span>
              </button>
            )}
          </div>
        </div>

        {/* Footer */}
        <div className="flex justify-end gap-3 px-6 py-4 border-t border-border bg-muted/50">
          <button
            type="button"
            onClick={onClose}
            disabled={saving || creatingFolder}
            className="px-4 py-2 text-sm font-medium rounded-lg border border-border hover:bg-background transition-colors disabled:opacity-50"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={handleSave}
            disabled={saving || creatingFolder}
            className="px-4 py-2 text-sm font-medium rounded-lg bg-primary text-white hover:bg-primary/90 transition-colors disabled:opacity-50"
          >
            {saving ? 'Moving...' : 'Move'}
          </button>
        </div>
      </div>
    </div>
  )
}

export default ChangeFolderModal
