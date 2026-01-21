import { useCallback, useEffect, useMemo, useState } from 'react'
import { FileText, FileType, FileSpreadsheet, Image as ImageIcon, PenTool, GitBranch, MoreVertical, Workflow, ClipboardPlus, Type, Pencil, FolderInput, Trash2 } from 'lucide-react'
import toast from 'react-hot-toast'
import api from '../../services/api'
import { useFlowsStore, useDocumentSelectionStore, useDocumentFiltersStore, useAuthStore } from '../../stores'

/**
 * Dropdown menu for document actions
 */
function DocumentActionsMenu({ doc, onAddToClipboard, onSummarize, onRename, onChangeFolder, onMoveToTrash, isSelected }) {
  const [open, setOpen] = useState(false)
  const [buttonRect, setButtonRect] = useState(null)

  const handleOpen = (e) => {
    e.stopPropagation()
    const rect = e.currentTarget.getBoundingClientRect()
    setButtonRect(rect)
    setOpen((prev) => !prev)
  }

  return (
    <div className="relative" data-actions-menu>
      <button
        type="button"
        className={`p-1 rounded hover:bg-background/50 transition-colors ${isSelected ? 'text-white' : ''}`}
        onClick={handleOpen}
        aria-label="Document actions"
      >
        <MoreVertical className={`h-4 w-4 ${isSelected ? 'text-white' : 'text-text-secondary'}`} />
      </button>
      {open && buttonRect && (
        <>
          <div
            className="fixed inset-0 z-40"
            onClick={(e) => {
              e.stopPropagation()
              setOpen(false)
            }}
          />
          <div
            className="fixed w-44 bg-white dark:bg-zinc-800 border border-border rounded-lg shadow-lg py-1 z-50"
            style={{
              top: buttonRect.bottom + 4,
              left: Math.min(buttonRect.right - 176, window.innerWidth - 180),
            }}
          >
            <button
              className="w-full flex items-center gap-2 px-3 py-2 text-sm text-left hover:bg-background transition-colors"
              onClick={(e) => {
                e.stopPropagation()
                setOpen(false)
                onRename?.(doc)
              }}
            >
              <Pencil className="h-4 w-4 text-text-secondary" />
              Rename
            </button>
            <button
              className="w-full flex items-center gap-2 px-3 py-2 text-sm text-left hover:bg-background transition-colors"
              onClick={(e) => {
                e.stopPropagation()
                setOpen(false)
                onChangeFolder?.(doc)
              }}
            >
              <FolderInput className="h-4 w-4 text-text-secondary" />
              Change folder
            </button>
            <div className="border-t border-border my-1" />
            <button
              className="w-full flex items-center gap-2 px-3 py-2 text-sm text-left hover:bg-background transition-colors"
              onClick={(e) => {
                e.stopPropagation()
                setOpen(false)
                onAddToClipboard(doc)
              }}
            >
              <ClipboardPlus className="h-4 w-4 text-text-secondary" />
              Add to Notebook
            </button>
            <button
              className="w-full flex items-center gap-2 px-3 py-2 text-sm text-left hover:bg-background transition-colors"
              onClick={(e) => {
                e.stopPropagation()
                setOpen(false)
                onSummarize(doc)
              }}
            >
              <Workflow className="h-4 w-4 text-text-secondary" />
              Summarize
            </button>
            <div className="border-t border-border my-1" />
            <button
              className="w-full flex items-center gap-2 px-3 py-2 text-sm text-left hover:bg-background transition-colors text-red-500"
              onClick={(e) => {
                e.stopPropagation()
                setOpen(false)
                onMoveToTrash?.(doc)
              }}
            >
              <Trash2 className="h-4 w-4" />
              Move to trash
            </button>
          </div>
        </>
      )}
    </div>
  )
}

const TYPE_ICON = {
  Image: <ImageIcon className="h-5 w-5 text-text-secondary" />,
  Markdown: <FileText className="h-5 w-5 text-text-secondary" />,
  D2Diagram: <FileText className="h-5 w-5 text-blue-500" />,
  ExcalidrawDiagram: <PenTool className="h-5 w-5 text-purple-500" />,
  MermaidDiagram: <GitBranch className="h-5 w-5 text-green-500" />,
  YooptaDocument: <Type className="h-5 w-5 text-orange-500" />,
  PDF: <FileType className="h-5 w-5 text-red-500" />,
  WordDocument: <FileText className="h-5 w-5 text-blue-600" />,
  SpreadsheetDocument: <FileSpreadsheet className="h-5 w-5 text-green-600" />,
}

function DocumentCard({ doc, index, isSelected, onSelect, onDoubleClick, onAddToClipboard, onSummarize, onRename, onChangeFolder, onMoveToTrash }) {
  // Preview URL comes from preview.url (thumbnail) or image_file (full image for Image docs)
  const previewUrl = doc.preview?.url || doc.image_file
  const hasImagePreview = Boolean(previewUrl)
  // Text snippet for text-based documents
  const textSnippet = doc.preview?.metadata?.text_snippet
  const icon = TYPE_ICON[doc.document_type] || <FileText className="h-5 w-5 text-text-secondary" />

  return (
    <div
      className={`rounded-lg cursor-pointer hover:shadow-md transition overflow-hidden h-[220px] flex flex-col ${
        isSelected
          ? 'bg-primary border-2 border-primary'
          : 'bg-surface border border-border'
      }`}
      onClick={(e) => onSelect(e, doc, index)}
      onDoubleClick={() => onDoubleClick(doc)}
    >
      {/* Preview area - fills remaining space */}
      <div className={`flex-1 flex items-center justify-center overflow-hidden px-2 pt-2 pb-0 ${isSelected ? 'bg-primary/10' : 'bg-zinc-100 dark:bg-zinc-800'}`}>
        {hasImagePreview ? (
          <img
            src={previewUrl}
            alt={doc.name}
            className="w-full h-full object-cover"
          />
        ) : textSnippet ? (
          <div className="w-full h-full overflow-hidden">
            <div className="h-full p-2 bg-white dark:bg-zinc-900 overflow-hidden">
              <p className="text-[8px] text-text-secondary leading-tight line-clamp-6 font-mono whitespace-pre-wrap">
                {textSnippet}
              </p>
            </div>
          </div>
        ) : (
          <div className="flex flex-col items-center gap-1 text-text-secondary">
            {icon}
            <span className="text-[10px] uppercase tracking-wide">{doc.document_type || 'Document'}</span>
          </div>
        )}
      </div>
      {/* Info footer - compact */}
      <div className={`px-2 py-1.5 ${isSelected ? 'bg-primary/15' : 'bg-zinc-100 dark:bg-zinc-800'}`}>
        <div className="flex items-center gap-1.5">
          <div className="flex-shrink-0">{icon}</div>
          <span className="text-xs font-medium truncate flex-1">{doc.name}</span>
          <DocumentActionsMenu
            doc={doc}
            onAddToClipboard={onAddToClipboard}
            onSummarize={onSummarize}
            onRename={onRename}
            onChangeFolder={onChangeFolder}
            onMoveToTrash={onMoveToTrash}
            isSelected={isSelected}
          />
        </div>
      </div>
    </div>
  )
}

function DocumentRow({ doc, index, isSelected, onSelect, onDoubleClick, onAddToClipboard, onSummarize, onRename, onChangeFolder, onMoveToTrash }) {
  return (
    <div
      className={`grid grid-cols-[1.5fr_2fr_1fr_auto] items-center gap-3 px-3 py-2 rounded-md cursor-pointer ${
        isSelected
          ? 'bg-primary text-white'
          : 'hover:bg-background'
      }`}
      onClick={(e) => onSelect(e, doc, index)}
      onDoubleClick={() => onDoubleClick(doc)}
    >
      <div className="flex items-center gap-2 min-w-0">
        {TYPE_ICON[doc.document_type] || <FileText className="h-4 w-4" />}
        <span className="font-medium truncate">{doc.name}</span>
      </div>
      <div className="text-sm text-text-secondary truncate">{doc.description || '---'}</div>
      <div className="text-xs text-text-secondary">
        {doc.updated_at ? new Date(doc.updated_at).toLocaleDateString() : ''}
      </div>
      <DocumentActionsMenu
        doc={doc}
        onAddToClipboard={onAddToClipboard}
        onSummarize={onSummarize}
        onRename={onRename}
        onChangeFolder={onChangeFolder}
        onMoveToTrash={onMoveToTrash}
        isSelected={isSelected}
      />
    </div>
  )
}

function DocumentsList({ folderId, projectId, workspaceId, viewMode = 'grid', onAddToClipboard, onRename, onChangeFolder, onMoveToTrash }) {
  const runWorkflow = useFlowsStore((state) => state.runWorkflow)
  const [documents, setDocuments] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  // Selection store
  const selectedDocumentIds = useDocumentSelectionStore((state) => state.selectedDocumentIds)
  const selectDocument = useDocumentSelectionStore((state) => state.selectDocument)
  const toggleDocumentSelection = useDocumentSelectionStore((state) => state.toggleDocumentSelection)
  const extendSelectionRange = useDocumentSelectionStore((state) => state.extendSelectionRange)
  const setFolderContext = useDocumentSelectionStore((state) => state.setFolderContext)

  // Filters store
  const typeFilter = useDocumentFiltersStore((state) => state.typeFilter)
  const ownerFilter = useDocumentFiltersStore((state) => state.ownerFilter)
  const modifiedFilter = useDocumentFiltersStore((state) => state.modifiedFilter)
  const getModifiedCutoff = useDocumentFiltersStore((state) => state.getModifiedCutoff)

  // Auth store for current user
  const currentUser = useAuthStore((state) => state.user)

  // Clear selection when folder changes
  useEffect(() => {
    setFolderContext(folderId)
  }, [folderId, setFolderContext])

  // Apply client-side filters
  const filteredDocuments = useMemo(() => {
    let result = documents

    // Type filter
    if (typeFilter) {
      result = result.filter((doc) => doc.document_type === typeFilter)
    }

    // Owner filter
    if (ownerFilter === 'me' && currentUser?.id) {
      result = result.filter((doc) => doc.created_by_id === currentUser.id)
    }

    // Modified filter
    if (modifiedFilter) {
      const cutoff = getModifiedCutoff()
      if (cutoff) {
        result = result.filter((doc) => new Date(doc.updated_at) >= cutoff)
      }
    }

    return result
  }, [documents, typeFilter, ownerFilter, modifiedFilter, currentUser?.id, getModifiedCutoff])

  // Memoized document IDs for range selection (use filtered documents)
  const documentIds = useMemo(() => filteredDocuments.map((d) => d.id), [filteredDocuments])

  useEffect(() => {
    let ignore = false
    const load = async () => {
      try {
        setLoading(true)
        const response = await api.fetchDocuments({
          folder_id: folderId || null,
          project_id: projectId || null,
          workspace_id: workspaceId || null,
          page_size: 50,
        })
        if (!ignore) {
          setDocuments(response.documents || [])
        }
      } catch (err) {
        if (!ignore) setError(err.message || 'Failed to load documents')
      } finally {
        if (!ignore) setLoading(false)
      }
    }
    load()
    return () => {
      ignore = true
    }
  }, [folderId, projectId, workspaceId])

  const handleSummarize = useCallback(async (doc) => {
    try {
      const result = await runWorkflow(
        'summarize_content',
        {
          source_type: 'document',
          source_id: String(doc.id),
          summary_style: 'brief',
        },
        {
          background: true,
          workspace_id: doc.workspace_id,
        }
      )

      if (result?.run_id) {
        toast.success('Summarizing document...', {
          duration: 3000,
          icon: '📝',
        })
      }
    } catch (err) {
      console.error('Failed to start summarization:', err)
      toast.error(err.message || 'Failed to start summarization')
    }
  }, [runWorkflow])

  // Handle single click - select document
  const handleDocumentClick = useCallback(
    (e, doc, index) => {
      // Prevent selection when clicking on actions menu
      if (e.target.closest('[data-actions-menu]')) return

      const isMac = navigator.platform.toUpperCase().indexOf('MAC') >= 0
      const isModifierKey = isMac ? e.metaKey : e.ctrlKey

      if (e.shiftKey) {
        extendSelectionRange(documentIds, index)
      } else if (isModifierKey) {
        toggleDocumentSelection(doc.id, index)
      } else {
        selectDocument(doc.id, index)
      }
    },
    [documentIds, selectDocument, toggleDocumentSelection, extendSelectionRange]
  )

  // Handle double click - open in new tab
  const handleDocumentDoubleClick = useCallback((doc) => {
    window.open(`/documents/${doc.id}`, '_blank')
  }, [])

  const renderDocs = useMemo(() => {
    if (loading) return <div className="text-text-secondary">Loading documents...</div>
    if (error) return <div className="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded">Failed to load documents: {error}</div>
    if (!filteredDocuments.length) {
      if (documents.length > 0) {
        return <div className="text-text-secondary">No documents match the current filters.</div>
      }
      return <div className="text-text-secondary">No documents in this folder.</div>
    }

    if (viewMode === 'grid') {
      return (
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-3">
          {filteredDocuments.map((doc, index) => (
            <DocumentCard
              key={doc.id}
              doc={doc}
              index={index}
              isSelected={selectedDocumentIds.has(doc.id)}
              onSelect={handleDocumentClick}
              onDoubleClick={handleDocumentDoubleClick}
              onAddToClipboard={onAddToClipboard}
              onSummarize={handleSummarize}
              onRename={onRename}
              onChangeFolder={onChangeFolder}
              onMoveToTrash={onMoveToTrash}
            />
          ))}
        </div>
      )
    }

    return (
      <div className="border border-border rounded-lg bg-surface divide-y divide-border">
        <div className="grid grid-cols-[1.5fr_2fr_1fr_auto] gap-3 px-3 py-2 text-xs text-text-secondary uppercase font-semibold">
          <span>Name</span>
          <span>Details</span>
          <span>Updated</span>
          <span></span>
        </div>
        {filteredDocuments.map((doc, index) => (
          <DocumentRow
            key={doc.id}
            doc={doc}
            index={index}
            isSelected={selectedDocumentIds.has(doc.id)}
            onSelect={handleDocumentClick}
            onDoubleClick={handleDocumentDoubleClick}
            onAddToClipboard={onAddToClipboard}
            onSummarize={handleSummarize}
            onRename={onRename}
            onChangeFolder={onChangeFolder}
            onMoveToTrash={onMoveToTrash}
          />
        ))}
      </div>
    )
  }, [documents, filteredDocuments, viewMode, loading, error, onAddToClipboard, handleSummarize, selectedDocumentIds, handleDocumentClick, handleDocumentDoubleClick, onRename, onChangeFolder, onMoveToTrash])

  return renderDocs
}

export default DocumentsList
