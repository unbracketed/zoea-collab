/**
 * Import Documents Modal
 *
 * Supports directory and archive imports from the Documents page.
 */

import { useEffect, useRef, useState } from 'react'
import { X } from 'lucide-react'
import toast from 'react-hot-toast'
import api from '../../services/api'

const DEFAULT_CONFLICT = 'rename'

function formatBytes(bytes) {
  if (!Number.isFinite(bytes) || bytes <= 0) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  const exponent = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1)
  const value = bytes / Math.pow(1024, exponent)
  const display = value >= 10 ? value.toFixed(0) : value.toFixed(1)
  return `${display} ${units[exponent]}`
}

function ImportDocumentsModal({
  isOpen,
  mode,
  onClose,
  projectId,
  workspaceId,
  folderId,
  folderPath,
  onSuccess,
}) {
  const fileInputRef = useRef(null)
  const [path, setPath] = useState('')
  const [archiveFile, setArchiveFile] = useState(null)
  const [createRootFolder, setCreateRootFolder] = useState(true)
  const [rootFolderName, setRootFolderName] = useState('')
  const [onConflict, setOnConflict] = useState(DEFAULT_CONFLICT)
  const [followSymlinks, setFollowSymlinks] = useState(false)
  const [summary, setSummary] = useState(null)
  const [error, setError] = useState(null)
  const [isSubmitting, setIsSubmitting] = useState(false)

  const isDirectory = mode === 'directory'
  const title = isDirectory ? 'Import Directory' : 'Import Archive'
  const submitLabel = isDirectory ? 'Import Directory' : 'Import Archive'

  useEffect(() => {
    if (isOpen) {
      setPath('')
      setArchiveFile(null)
      setCreateRootFolder(true)
      setRootFolderName('')
      setOnConflict(DEFAULT_CONFLICT)
      setFollowSymlinks(false)
      setSummary(null)
      setError(null)
      if (fileInputRef.current) {
        fileInputRef.current.value = ''
      }
    }
  }, [isOpen, mode])

  useEffect(() => {
    const handleEscape = (event) => {
      if (event.key === 'Escape' && isOpen && !isSubmitting) {
        onClose()
      }
    }

    window.addEventListener('keydown', handleEscape)
    return () => window.removeEventListener('keydown', handleEscape)
  }, [isOpen, isSubmitting, onClose])

  const handleBackdropClick = (event) => {
    if (event.target === event.currentTarget && !isSubmitting) {
      onClose()
    }
  }

  const handlePathChange = (event) => {
    setPath(event.target.value)
    setSummary(null)
    setError(null)
  }

  const handleArchiveChange = (event) => {
    const file = event.target.files?.[0] || null
    setArchiveFile(file)
    setSummary(null)
    setError(null)
  }

  const handleImport = async () => {
    if (isSubmitting) return
    if (!projectId || !workspaceId) {
      setError('Project and workspace are required to import documents.')
      return
    }

    if (isDirectory && !path.trim()) {
      setError('Directory path is required.')
      return
    }

    if (!isDirectory && !archiveFile) {
      setError('Archive file is required.')
      return
    }

    setIsSubmitting(true)
    setError(null)
    setSummary(null)

    try {
      let result
      if (isDirectory) {
        result = await api.importDocumentsFromDirectory({
          path: path.trim(),
          project_id: projectId,
          workspace_id: workspaceId,
          folder_id: folderId,
          create_root_folder: createRootFolder,
          root_folder_name: rootFolderName.trim() || null,
          on_conflict: onConflict,
          follow_symlinks: followSymlinks,
        })
      } else {
        result = await api.importDocumentsFromArchive({
          file: archiveFile,
          project_id: projectId,
          workspace_id: workspaceId,
          folder_id: folderId,
          create_root_folder: createRootFolder,
          root_folder_name: rootFolderName.trim() || null,
          on_conflict: onConflict,
        })
      }

      setSummary(result)
      toast.success('Import completed')
      onSuccess?.(result)
    } catch (err) {
      console.error('Import failed:', err)
      setError(err.message || 'Import failed.')
      toast.error(err.message || 'Import failed.')
    } finally {
      setIsSubmitting(false)
    }
  }

  if (!isOpen) return null

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50"
      onClick={handleBackdropClick}
    >
      <div
        className="bg-card text-card-foreground rounded-xl shadow-lg border border-border w-full max-w-xl mx-4 overflow-hidden"
        role="dialog"
        aria-modal="true"
        aria-labelledby="import-documents-title"
      >
        <div className="flex items-center justify-between px-6 py-4 border-b border-border">
          <h2 id="import-documents-title" className="text-lg font-semibold">
            {title}
          </h2>
          <button
            type="button"
            onClick={onClose}
            disabled={isSubmitting}
            className="p-1 rounded-md hover:bg-muted text-muted-foreground hover:text-foreground transition-colors disabled:opacity-50"
            aria-label="Close"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="p-6 space-y-5">
          {error && (
            <div className="p-3 rounded-lg bg-red-500/10 text-red-500 text-sm">
              {error}
            </div>
          )}

          <div className="text-xs text-muted-foreground">
            Importing into: {folderPath || 'Workspace root'}
          </div>

          {isDirectory ? (
            <div className="space-y-2">
              <label className="text-sm font-medium">Directory path</label>
              <input
                type="text"
                value={path}
                onChange={handlePathChange}
                className="w-full px-3 py-2 rounded-lg border border-border bg-background focus:ring-2 focus:ring-primary/50 focus:border-primary outline-none transition-colors"
                placeholder="/absolute/path/to/documents"
                disabled={isSubmitting}
              />
              <p className="text-xs text-muted-foreground">
                Path must be absolute and within the configured allowed roots.
              </p>
            </div>
          ) : (
            <div className="space-y-2">
              <label className="text-sm font-medium">Archive file</label>
              <input
                ref={fileInputRef}
                type="file"
                accept=".zip,.tar,.tar.gz,.tgz"
                onChange={handleArchiveChange}
                disabled={isSubmitting}
                className="w-full text-sm"
              />
              <p className="text-xs text-muted-foreground">
                Supported formats: .zip, .tar, .tar.gz, .tgz.
              </p>
              {archiveFile && (
                <div className="text-xs text-muted-foreground">
                  Selected: {archiveFile.name} ({formatBytes(archiveFile.size)})
                </div>
              )}
            </div>
          )}

          <div className="grid gap-4 sm:grid-cols-2">
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={createRootFolder}
                onChange={(event) => setCreateRootFolder(event.target.checked)}
                disabled={isSubmitting}
                className="h-4 w-4"
              />
              Create root folder
            </label>
            <div className="space-y-1">
              <label className="text-sm font-medium">Root folder name</label>
              <input
                type="text"
                value={rootFolderName}
                onChange={(event) => {
                  setRootFolderName(event.target.value)
                  setSummary(null)
                }}
                className="w-full px-3 py-2 rounded-lg border border-border bg-background focus:ring-2 focus:ring-primary/50 focus:border-primary outline-none transition-colors"
                placeholder="Optional override"
                disabled={isSubmitting || !createRootFolder}
              />
            </div>
          </div>

          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-1">
              <label className="text-sm font-medium">On conflict</label>
              <select
                value={onConflict}
                onChange={(event) => {
                  setOnConflict(event.target.value)
                  setSummary(null)
                }}
                disabled={isSubmitting}
                className="w-full px-3 py-2 rounded-lg border border-border bg-background focus:ring-2 focus:ring-primary/50 focus:border-primary outline-none transition-colors"
              >
                <option value="rename">Rename new files</option>
                <option value="skip">Skip existing</option>
                <option value="overwrite">Overwrite existing</option>
              </select>
            </div>

            {isDirectory ? (
              <label className="flex items-center gap-2 text-sm pt-6">
                <input
                  type="checkbox"
                  checked={followSymlinks}
                  onChange={(event) => setFollowSymlinks(event.target.checked)}
                  disabled={isSubmitting}
                  className="h-4 w-4"
                />
                Follow symlinks
              </label>
            ) : (
              <div className="text-xs text-muted-foreground pt-6">
                Archives with unsupported files are skipped.
              </div>
            )}
          </div>

          {summary && (
            <div className="border border-border rounded-lg p-4 bg-muted/20 space-y-2 text-sm">
              <div className="font-medium">Import summary</div>
              <div className="grid grid-cols-2 gap-2 text-xs text-muted-foreground">
                <div>Created: {summary.created}</div>
                <div>Updated: {summary.updated}</div>
                <div>Skipped: {summary.skipped}</div>
                <div>Failed: {summary.failed}</div>
                <div>Total files: {summary.total_files}</div>
                <div>Total size: {formatBytes(summary.total_size)}</div>
              </div>
              {summary.root_folder_path && (
                <div className="text-xs text-muted-foreground">
                  Root folder: {summary.root_folder_path}
                </div>
              )}
              {summary.issues?.length > 0 && (
                <div className="text-xs text-muted-foreground">
                  {summary.issues.length} issue(s) recorded.
                </div>
              )}
            </div>
          )}
        </div>

        <div className="flex justify-end gap-3 px-6 py-4 border-t border-border bg-muted/50">
          <button
            type="button"
            onClick={onClose}
            disabled={isSubmitting}
            className="px-4 py-2 text-sm font-medium rounded-lg border border-border hover:bg-background transition-colors disabled:opacity-50"
          >
            Close
          </button>
          <button
            type="button"
            onClick={handleImport}
            disabled={isSubmitting}
            className="px-4 py-2 text-sm font-medium rounded-lg bg-primary text-white hover:bg-primary/90 transition-colors disabled:opacity-50"
          >
            {isSubmitting ? 'Importing...' : submitLabel}
          </button>
        </div>
      </div>
    </div>
  )
}

export default ImportDocumentsModal
