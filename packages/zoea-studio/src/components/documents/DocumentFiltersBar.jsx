/**
 * Document Filters Bar Component
 *
 * Google Drive-style filter bar with breadcrumb navigation,
 * filter dropdowns, and view mode toggle.
 *
 * When documents are selected, displays bulk actions instead of filters.
 */

import {
  FileText,
  FileType,
  FileSpreadsheet,
  Image as ImageIcon,
  Type,
  PenTool,
  GitBranch,
  Rows,
  Grid,
  Calendar,
  User,
  FolderOpen,
} from 'lucide-react'
import FolderBreadcrumb from './FolderBreadcrumb'
import FilterDropdown from './FilterDropdown'
import BulkActionsBar from './BulkActionsBar'
import { useDocumentFiltersStore, useDocumentSelectionStore } from '../../stores'

// Filter options
const TYPE_OPTIONS = [
  { id: 'Image', label: 'Images', icon: ImageIcon },
  { id: 'PDF', label: 'PDFs', icon: FileType },
  { id: 'WordDocument', label: 'Word Docs', icon: FileText },
  { id: 'SpreadsheetDocument', label: 'Spreadsheets', icon: FileSpreadsheet },
  { id: 'Markdown', label: 'Documents', icon: FileText },
  { id: 'YooptaDocument', label: 'Rich Text', icon: Type },
  { id: 'D2Diagram', label: 'D2 Diagrams', icon: FileText },
  { id: 'MermaidDiagram', label: 'Mermaid', icon: GitBranch },
  { id: 'ExcalidrawDiagram', label: 'Excalidraw', icon: PenTool },
]

const OWNER_OPTIONS = [
  { id: 'me', label: 'Owned by me', icon: User },
]

const MODIFIED_OPTIONS = [
  { id: 'today', label: 'Today', icon: Calendar },
  { id: 'week', label: 'Last 7 days', icon: Calendar },
  { id: 'month', label: 'Last 30 days', icon: Calendar },
  { id: 'year', label: 'This year', icon: Calendar },
]

const SOURCE_OPTIONS = [
  { id: 'uploads', label: 'Uploads', icon: FolderOpen },
]

function DocumentFiltersBar({
  folder,
  workspaceId,
  projectId = null,
  viewMode,
  onViewModeChange,
  onBulkMove,
  onBulkAddToNotebook,
  onBulkMoveToTrash,
}) {
  const typeFilter = useDocumentFiltersStore((state) => state.typeFilter)
  const ownerFilter = useDocumentFiltersStore((state) => state.ownerFilter)
  const modifiedFilter = useDocumentFiltersStore((state) => state.modifiedFilter)
  const sourceFilter = useDocumentFiltersStore((state) => state.sourceFilter)

  const setTypeFilter = useDocumentFiltersStore((state) => state.setTypeFilter)
  const setOwnerFilter = useDocumentFiltersStore((state) => state.setOwnerFilter)
  const setModifiedFilter = useDocumentFiltersStore((state) => state.setModifiedFilter)
  const setSourceFilter = useDocumentFiltersStore((state) => state.setSourceFilter)

  const selectedDocumentIds = useDocumentSelectionStore((state) => state.selectedDocumentIds)
  const clearSelection = useDocumentSelectionStore((state) => state.clearSelection)
  const selectedCount = selectedDocumentIds.size

  const hasSelection = selectedCount > 0

  return (
    <div className="flex flex-col border-b border-border bg-surface">
      {/* Row 1: Breadcrumb */}
      <div className="px-4 py-2">
        <FolderBreadcrumb folder={folder} workspaceId={workspaceId} />
      </div>

      {/* Row 2: Filters or Bulk Actions + View Toggle */}
      <div className="flex items-center justify-between px-4 py-2 border-t border-border">
        {/* Left side: Filters or Bulk Actions */}
        <div className="flex items-center gap-2 flex-shrink-0">
          {hasSelection ? (
            <BulkActionsBar
              selectedCount={selectedCount}
              selectedIds={Array.from(selectedDocumentIds)}
              projectId={projectId}
              onMove={onBulkMove}
              onAddToNotebook={onBulkAddToNotebook}
              onMoveToTrash={onBulkMoveToTrash}
              onClearSelection={clearSelection}
            />
          ) : (
            <>
              <FilterDropdown
                label="Type"
                options={TYPE_OPTIONS}
                value={typeFilter}
                onChange={setTypeFilter}
              />

              <FilterDropdown
                label="People"
                options={OWNER_OPTIONS}
                value={ownerFilter}
                onChange={setOwnerFilter}
              />

              <FilterDropdown
                label="Modified"
                options={MODIFIED_OPTIONS}
                value={modifiedFilter}
                onChange={setModifiedFilter}
              />

              <FilterDropdown
                label="Source"
                options={SOURCE_OPTIONS}
                value={sourceFilter}
                onChange={setSourceFilter}
              />
            </>
          )}
        </div>

        {/* Right side: View mode toggle (always visible) */}
        <div className="flex items-center gap-2 flex-shrink-0">
          <div className="inline-flex items-center gap-1 border border-border rounded-md bg-surface p-0.5">
            <button
              type="button"
              className={`h-7 w-7 rounded flex items-center justify-center transition-colors ${
                viewMode === 'list' ? 'bg-background' : 'hover:bg-muted/50'
              }`}
              onClick={() => onViewModeChange('list')}
              aria-label="List view"
            >
              <Rows className="h-4 w-4" />
            </button>
            <button
              type="button"
              className={`h-7 w-7 rounded flex items-center justify-center transition-colors ${
                viewMode === 'grid' ? 'bg-background' : 'hover:bg-muted/50'
              }`}
              onClick={() => onViewModeChange('grid')}
              aria-label="Grid view"
            >
              <Grid className="h-4 w-4" />
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

export default DocumentFiltersBar
