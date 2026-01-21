/**
 * Trash Page
 *
 * Displays trashed documents with restore and permanent delete options.
 */

import { useCallback, useEffect, useState } from 'react'
import { Trash2, RotateCcw, AlertTriangle, FileText, Image as ImageIcon, PenTool, GitBranch, Type, MoreVertical } from 'lucide-react'
import toast from 'react-hot-toast'
import LayoutFrame from '../components/layout/LayoutFrame'
import { useWorkspaceStore } from '../stores'
import api from '../services/api'

const TYPE_ICON = {
  Image: <ImageIcon className="h-5 w-5 text-text-secondary" />,
  Markdown: <FileText className="h-5 w-5 text-text-secondary" />,
  D2Diagram: <FileText className="h-5 w-5 text-blue-500" />,
  ExcalidrawDiagram: <PenTool className="h-5 w-5 text-purple-500" />,
  MermaidDiagram: <GitBranch className="h-5 w-5 text-green-500" />,
  YooptaDocument: <Type className="h-5 w-5 text-orange-500" />,
}

function TrashActionsMenu({ doc, onRestore, onDelete }) {
  const [open, setOpen] = useState(false)

  return (
    <div className="relative" data-actions-menu>
      <button
        type="button"
        className="p-1 rounded hover:bg-background transition-colors"
        onClick={(e) => {
          e.stopPropagation()
          setOpen((prev) => !prev)
        }}
        aria-label="Document actions"
      >
        <MoreVertical className="h-4 w-4 text-text-secondary" />
      </button>
      {open && (
        <>
          <div
            className="fixed inset-0 z-40"
            onClick={(e) => {
              e.stopPropagation()
              setOpen(false)
            }}
          />
          <div className="absolute right-0 top-full mt-1 w-44 bg-surface border border-border rounded-lg shadow-lg py-1 z-50">
            <button
              className="w-full flex items-center gap-2 px-3 py-2 text-sm text-left hover:bg-background transition-colors"
              onClick={(e) => {
                e.stopPropagation()
                setOpen(false)
                onRestore(doc)
              }}
            >
              <RotateCcw className="h-4 w-4 text-text-secondary" />
              Restore
            </button>
            <div className="border-t border-border my-1" />
            <button
              className="w-full flex items-center gap-2 px-3 py-2 text-sm text-left hover:bg-background transition-colors text-red-500"
              onClick={(e) => {
                e.stopPropagation()
                setOpen(false)
                onDelete(doc)
              }}
            >
              <Trash2 className="h-4 w-4" />
              Delete permanently
            </button>
          </div>
        </>
      )}
    </div>
  )
}

function TrashPage() {
  const currentWorkspaceId = useWorkspaceStore((state) => state.currentWorkspaceId)
  const [documents, setDocuments] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const loadDocuments = useCallback(async () => {
    if (!currentWorkspaceId) {
      setDocuments([])
      setLoading(false)
      return
    }

    try {
      setLoading(true)
      setError(null)
      const result = await api.fetchTrashedDocuments({ workspace_id: currentWorkspaceId })
      setDocuments(result || [])
    } catch (err) {
      console.error('Failed to load trashed documents:', err)
      setError(err.message || 'Failed to load trashed documents')
    } finally {
      setLoading(false)
    }
  }, [currentWorkspaceId])

  useEffect(() => {
    loadDocuments()
  }, [loadDocuments])

  const handleRestore = useCallback(async (doc) => {
    try {
      await api.restoreDocument(doc.id)
      toast.success('Document restored')
      loadDocuments()
    } catch (err) {
      console.error('Failed to restore document:', err)
      toast.error(err.message || 'Failed to restore document')
    }
  }, [loadDocuments])

  const handleDelete = useCallback(async (doc) => {
    if (!window.confirm(`Are you sure you want to permanently delete "${doc.name}"? This action cannot be undone.`)) {
      return
    }

    try {
      await api.permanentlyDeleteDocument(doc.id)
      toast.success('Document permanently deleted')
      loadDocuments()
    } catch (err) {
      console.error('Failed to delete document:', err)
      toast.error(err.message || 'Failed to delete document')
    }
  }, [loadDocuments])

  const formatTrashedDate = (dateStr) => {
    if (!dateStr) return ''
    const date = new Date(dateStr)
    const now = new Date()
    const diffDays = Math.floor((now - date) / (1000 * 60 * 60 * 24))

    if (diffDays === 0) return 'Today'
    if (diffDays === 1) return 'Yesterday'
    if (diffDays < 7) return `${diffDays} days ago`
    return date.toLocaleDateString()
  }

  return (
    <LayoutFrame title="Trash" variant="full" noPadding>
      <div className="h-full flex flex-col">
        {/* Header */}
        <div className="border-b border-border px-6 py-4">
          <div className="flex items-center gap-3">
            <Trash2 className="h-6 w-6 text-text-secondary" />
            <div>
              <h1 className="text-xl font-semibold">Trash</h1>
              <p className="text-sm text-text-secondary">Items in trash are deleted after 30 days</p>
            </div>
          </div>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-auto p-6">
          {loading && (
            <div className="text-text-secondary">Loading...</div>
          )}

          {error && (
            <div className="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded">
              {error}
            </div>
          )}

          {!loading && !error && documents.length === 0 && (
            <div className="flex flex-col items-center justify-center py-16 text-text-secondary">
              <Trash2 className="h-16 w-16 mb-4 opacity-50" />
              <p className="text-lg">Trash is empty</p>
              <p className="text-sm mt-1">Items you delete will appear here</p>
            </div>
          )}

          {!loading && !error && documents.length > 0 && (
            <div className="border border-border rounded-lg bg-surface divide-y divide-border">
              <div className="grid grid-cols-[1fr_auto_auto] gap-3 px-4 py-2 text-xs text-text-secondary uppercase font-semibold">
                <span>Name</span>
                <span>Deleted</span>
                <span></span>
              </div>
              {documents.map((doc) => (
                <div
                  key={doc.id}
                  className="grid grid-cols-[1fr_auto_auto] items-center gap-3 px-4 py-3 hover:bg-background transition-colors"
                >
                  <div className="flex items-center gap-3 min-w-0">
                    {TYPE_ICON[doc.document_type] || <FileText className="h-5 w-5 text-text-secondary" />}
                    <span className="font-medium truncate">{doc.name}</span>
                  </div>
                  <div className="text-sm text-text-secondary">
                    {formatTrashedDate(doc.trashed_at)}
                  </div>
                  <TrashActionsMenu
                    doc={doc}
                    onRestore={handleRestore}
                    onDelete={handleDelete}
                  />
                </div>
              ))}
            </div>
          )}

          {!loading && !error && documents.length > 0 && (
            <div className="mt-4 p-4 bg-amber-50 dark:bg-amber-950/30 border border-amber-200 dark:border-amber-900 rounded-lg flex items-start gap-3">
              <AlertTriangle className="h-5 w-5 text-amber-600 dark:text-amber-500 flex-shrink-0 mt-0.5" />
              <div className="text-sm text-amber-800 dark:text-amber-200">
                <p className="font-medium">Items in trash will be permanently deleted after 30 days</p>
                <p className="mt-1 text-amber-700 dark:text-amber-300">
                  You can restore items or delete them permanently from the menu.
                </p>
              </div>
            </div>
          )}
        </div>
      </div>
    </LayoutFrame>
  )
}

export default TrashPage
