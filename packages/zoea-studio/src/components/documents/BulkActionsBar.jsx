/**
 * Bulk Actions Bar Component
 *
 * Displays action buttons for selected documents.
 * Replaces filter dropdowns when documents are selected.
 */

import { useState, useEffect } from 'react'
import { FolderInput, BookmarkPlus, Trash2, X, Zap, ChevronDown, Loader2 } from 'lucide-react'
import toast from 'react-hot-toast'
import {
  DropdownMenu,
  DropdownMenuTrigger,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuLabel,
} from '@/components/ui/dropdown-menu'
import api from '../../services/api'

function BulkActionsBar({
  selectedCount,
  selectedIds = [],
  projectId = null,
  onMove,
  onAddToNotebook,
  onMoveToTrash,
  onClearSelection,
}) {
  const [workflows, setWorkflows] = useState([])
  const [isLoadingWorkflows, setIsLoadingWorkflows] = useState(false)
  const [runningWorkflowId, setRunningWorkflowId] = useState(null)

  // Fetch workflows for DOCUMENTS_SELECTED event type when selection changes
  useEffect(() => {
    if (selectedCount > 0 && projectId) {
      fetchWorkflows()
    } else {
      setWorkflows([])
    }
  }, [selectedCount, projectId])

  const fetchWorkflows = async () => {
    setIsLoadingWorkflows(true)
    try {
      const triggers = await api.fetchEventTriggers({
        event_type: 'documents_selected',
        project_id: projectId,
      })
      setWorkflows(triggers.filter(t => t.is_enabled))
    } catch (error) {
      console.error('Failed to fetch workflows:', error)
      setWorkflows([])
    } finally {
      setIsLoadingWorkflows(false)
    }
  }

  const handleRunWorkflow = async (workflow) => {
    if (!selectedIds || selectedIds.length === 0) {
      toast.error('No documents selected')
      return
    }

    setRunningWorkflowId(workflow.id)
    try {
      await api.dispatchEventTrigger(workflow.id, { document_ids: selectedIds })
      toast.success(`Workflow "${workflow.name}" started`)
    } catch (error) {
      console.error('Failed to run workflow:', error)
      toast.error(error.message || 'Failed to start workflow')
    } finally {
      setRunningWorkflowId(null)
    }
  }

  return (
    <div className="flex items-center gap-2">
      {/* Selection count */}
      <span className="text-sm text-muted-foreground mr-2">
        <span className="font-semibold text-foreground">{selectedCount}</span> selected
      </span>

      {/* Separator */}
      <div className="w-px h-5 bg-border" />

      {/* Action buttons */}
      <button
        type="button"
        onClick={onMove}
        className="inline-flex items-center gap-1.5 px-2.5 py-1.5 text-sm text-foreground hover:bg-muted rounded-md transition-colors"
      >
        <FolderInput className="h-4 w-4" />
        Move
      </button>

      <button
        type="button"
        onClick={onAddToNotebook}
        className="inline-flex items-center gap-1.5 px-2.5 py-1.5 text-sm text-foreground hover:bg-muted rounded-md transition-colors"
      >
        <BookmarkPlus className="h-4 w-4" />
        Add to Notebook
      </button>

      {/* Workflows dropdown - only shown if workflows are available */}
      {workflows.length > 0 && (
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <button
              type="button"
              className="inline-flex items-center gap-1.5 px-2.5 py-1.5 text-sm text-foreground hover:bg-muted rounded-md transition-colors"
              disabled={isLoadingWorkflows}
            >
              {isLoadingWorkflows ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Zap className="h-4 w-4" />
              )}
              Workflows
              <ChevronDown className="h-3.5 w-3.5" />
            </button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="start" className="w-56">
            <DropdownMenuLabel>Run workflow</DropdownMenuLabel>
            <DropdownMenuSeparator />
            {workflows.map((workflow) => (
              <DropdownMenuItem
                key={workflow.id}
                onClick={() => handleRunWorkflow(workflow)}
                disabled={runningWorkflowId === workflow.id}
                className="cursor-pointer"
              >
                {runningWorkflowId === workflow.id ? (
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                ) : (
                  <Zap className="h-4 w-4 mr-2" />
                )}
                <span className="truncate">{workflow.name}</span>
              </DropdownMenuItem>
            ))}
          </DropdownMenuContent>
        </DropdownMenu>
      )}

      <button
        type="button"
        onClick={onMoveToTrash}
        className="inline-flex items-center gap-1.5 px-2.5 py-1.5 text-sm text-destructive hover:bg-destructive/10 rounded-md transition-colors"
      >
        <Trash2 className="h-4 w-4" />
        Trash
      </button>

      {/* Separator */}
      <div className="w-px h-5 bg-border" />

      {/* Clear selection button */}
      <button
        type="button"
        onClick={onClearSelection}
        className="inline-flex items-center justify-center h-7 w-7 text-muted-foreground hover:text-foreground hover:bg-muted rounded-md transition-colors"
        aria-label="Clear selection"
      >
        <X className="h-4 w-4" />
      </button>
    </div>
  )
}

export default BulkActionsBar
