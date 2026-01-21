/**
 * FolderBreadcrumb Component
 *
 * Displays a clickable breadcrumb path for folder navigation.
 * Shows: All Documents > Parent Folder > ... > Current Folder (dropdown)
 *
 * The current folder is a dropdown menu showing sibling folders
 * for easy navigation between folders at the same level.
 */

import { useEffect, useRef, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { ChevronRight, ChevronDown, Home, Folder } from 'lucide-react'
import api from '../../services/api'

function FolderBreadcrumb({ folder, workspaceId }) {
  const navigate = useNavigate()
  const [isOpen, setIsOpen] = useState(false)
  const [siblings, setSiblings] = useState([])
  const [loading, setLoading] = useState(false)
  const dropdownRef = useRef(null)

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target)) {
        setIsOpen(false)
      }
    }

    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside)
    }

    return () => {
      document.removeEventListener('mousedown', handleClickOutside)
    }
  }, [isOpen])

  // Close on escape key
  useEffect(() => {
    const handleEscape = (event) => {
      if (event.key === 'Escape') {
        setIsOpen(false)
      }
    }

    if (isOpen) {
      document.addEventListener('keydown', handleEscape)
    }

    return () => {
      document.removeEventListener('keydown', handleEscape)
    }
  }, [isOpen])

  // Fetch sibling folders when dropdown opens
  useEffect(() => {
    if (!isOpen || !workspaceId) return

    const fetchSiblings = async () => {
      setLoading(true)
      try {
        // Fetch folders with the same parent_id as current folder
        const parentId = folder?.parent_id || null
        const allFolders = await api.fetchFolders({ workspace_id: workspaceId })
        // Filter to siblings (same parent_id)
        const siblingFolders = allFolders.filter(
          (f) => (f.parent_id || null) === parentId && f.id !== folder?.id
        )
        setSiblings(siblingFolders)
      } catch (err) {
        console.error('Failed to fetch sibling folders:', err)
        setSiblings([])
      } finally {
        setLoading(false)
      }
    }

    fetchSiblings()
  }, [isOpen, workspaceId, folder?.parent_id, folder?.id])

  const handleSelectFolder = (folderId) => {
    setIsOpen(false)
    if (folderId) {
      navigate(`/documents/folder/${folderId}`)
    } else {
      navigate('/documents')
    }
  }

  // If no folder selected, just show "All Documents"
  if (!folder) {
    return (
      <div className="flex items-center gap-1 text-sm">
        <Home className="h-4 w-4 text-text-secondary" />
        <span className="font-semibold">All Documents</span>
      </div>
    )
  }

  // Build breadcrumb items from ancestors + current folder
  const ancestors = folder.ancestors || []

  return (
    <nav className="flex items-center gap-1 text-sm flex-wrap" aria-label="Breadcrumb">
      {/* Root: All Documents */}
      <Link
        to="/documents"
        className="flex items-center gap-1 text-text-secondary hover:text-primary transition-colors"
      >
        <Home className="h-4 w-4" />
        <span>All Documents</span>
      </Link>

      {/* Ancestor folders */}
      {ancestors.map((ancestor) => (
        <span key={ancestor.id} className="flex items-center gap-1">
          <ChevronRight className="h-4 w-4 text-text-secondary flex-shrink-0" />
          <Link
            to={`/documents/folder/${ancestor.id}`}
            className="text-text-secondary hover:text-primary transition-colors"
          >
            {ancestor.name}
          </Link>
        </span>
      ))}

      {/* Current folder (dropdown) */}
      <span className="flex items-center gap-1">
        <ChevronRight className="h-4 w-4 text-text-secondary flex-shrink-0" />
        <div className="relative" ref={dropdownRef}>
          <button
            type="button"
            onClick={() => setIsOpen(!isOpen)}
            className="flex items-center gap-1 font-semibold text-text-primary hover:text-primary transition-colors"
            aria-expanded={isOpen}
            aria-haspopup="listbox"
          >
            <span>{folder.name}</span>
            <ChevronDown
              className={`h-4 w-4 transition-transform ${isOpen ? 'rotate-180' : ''}`}
            />
          </button>

          {isOpen && (
            <div className="absolute left-0 top-full mt-1 min-w-48 max-w-64 bg-card text-card-foreground border border-border rounded-lg shadow-lg py-1 z-50">
              {/* Current folder (highlighted) */}
              <div className="px-3 py-2 text-sm bg-primary/10 text-primary font-medium flex items-center gap-2">
                <Folder className="h-4 w-4 flex-shrink-0" />
                <span className="truncate">{folder.name}</span>
              </div>

              {/* Separator if there are siblings */}
              {(loading || siblings.length > 0) && (
                <div className="border-t border-border my-1" />
              )}

              {/* Loading state */}
              {loading && (
                <div className="px-3 py-2 text-sm text-muted-foreground">
                  Loading...
                </div>
              )}

              {/* Sibling folders */}
              {!loading && siblings.length > 0 && (
                <div className="max-h-60 overflow-y-auto">
                  {siblings.map((sibling) => (
                    <button
                      key={sibling.id}
                      type="button"
                      className="w-full px-3 py-2 text-sm text-left hover:bg-muted transition-colors flex items-center gap-2"
                      onClick={() => handleSelectFolder(sibling.id)}
                    >
                      <Folder className="h-4 w-4 text-muted-foreground flex-shrink-0" />
                      <span className="truncate">{sibling.name}</span>
                    </button>
                  ))}
                </div>
              )}

              {/* No siblings message */}
              {!loading && siblings.length === 0 && (
                <div className="px-3 py-2 text-sm text-muted-foreground">
                  No other folders at this level
                </div>
              )}
            </div>
          )}
        </div>
      </span>
    </nav>
  )
}

export default FolderBreadcrumb
