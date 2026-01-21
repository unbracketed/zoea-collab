/**
 * New Document Button Component
 *
 * Google Drive-style "New" button with dropdown menu for creating documents.
 */

import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Plus,
  FileText,
  FileType,
  FileSpreadsheet,
  Image,
  FolderPlus,
  FolderOpen,
  MessageSquare,
  Type,
  PenTool,
  GitBranch,
  Workflow,
  Upload,
} from 'lucide-react'
import api from '../../services/api'

function NewDocumentButton({
  workspaceId,
  parentFolderId = null,
  onFolderCreated,
  onChatWithDocuments,
  onImportDirectory,
  onImportArchive,
}) {
  const navigate = useNavigate()
  const [isOpen, setIsOpen] = useState(false)
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

  const handleNewFolder = async () => {
    setIsOpen(false)
    if (!workspaceId) return
    const name = window.prompt('Folder name')
    if (!name) return
    try {
      await api.createFolder({ name, workspace_id: workspaceId, parent_id: parentFolderId })
      onFolderCreated?.()
    } catch (err) {
      console.error('Failed to create folder', err)
      alert(`Failed to create folder: ${err?.message || err}`)
    }
  }

  const handleChatWithDocuments = () => {
    setIsOpen(false)
    onChatWithDocuments?.()
  }

  const handleImportDirectory = () => {
    setIsOpen(false)
    onImportDirectory?.()
  }

  const handleImportArchive = () => {
    setIsOpen(false)
    onImportArchive?.()
  }

  const handleNavigate = (path) => {
    setIsOpen(false)
    navigate(path)
  }

  return (
    <div className="relative" ref={dropdownRef}>
      <button
        type="button"
        className="px-4 py-2 rounded-full shadow-sm bg-primary hover:bg-primary/90 transition-colors flex items-center gap-2 font-medium text-white"
        onClick={() => setIsOpen(!isOpen)}
      >
        <Plus className="h-5 w-5" />
        <span>New</span>
      </button>

      {isOpen && (
        <div className="absolute left-0 top-full mt-2 w-56 bg-card text-card-foreground border border-border rounded-lg shadow-lg py-1 z-50">
          <button
            type="button"
            className="w-full flex items-center gap-2 px-3 py-2 text-sm text-left hover:bg-muted transition-colors"
            onClick={handleNewFolder}
          >
            <FolderPlus className="h-4 w-4 text-muted-foreground" />
            New folder
          </button>

          <div className="border-t border-border my-1" />

          <button
            type="button"
            className="w-full flex items-center gap-2 px-3 py-2 text-sm text-left hover:bg-muted transition-colors"
            onClick={() => handleNavigate('/documents/new')}
          >
            <FileText className="h-4 w-4 text-muted-foreground" />
            New markdown document
          </button>
          <button
            type="button"
            className="w-full flex items-center gap-2 px-3 py-2 text-sm text-left hover:bg-muted transition-colors"
            onClick={() => handleNavigate('/documents/new/richtext')}
          >
            <Type className="h-4 w-4 text-muted-foreground" />
            New rich text document
          </button>
          <button
            type="button"
            className="w-full flex items-center gap-2 px-3 py-2 text-sm text-left hover:bg-muted transition-colors"
            onClick={() => handleNavigate('/documents/new/image')}
          >
            <Image className="h-4 w-4 text-muted-foreground" />
            Upload image
          </button>
          <button
            type="button"
            className="w-full flex items-center gap-2 px-3 py-2 text-sm text-left hover:bg-muted transition-colors"
            onClick={() => handleNavigate('/documents/new/pdf')}
          >
            <FileType className="h-4 w-4 text-muted-foreground" />
            Upload PDF
          </button>
          <button
            type="button"
            className="w-full flex items-center gap-2 px-3 py-2 text-sm text-left hover:bg-muted transition-colors"
            onClick={() => handleNavigate('/documents/new/docx')}
          >
            <FileText className="h-4 w-4 text-muted-foreground" />
            Upload Word document
          </button>
          <button
            type="button"
            className="w-full flex items-center gap-2 px-3 py-2 text-sm text-left hover:bg-muted transition-colors"
            onClick={() => handleNavigate('/documents/new/xlsx')}
          >
            <FileSpreadsheet className="h-4 w-4 text-muted-foreground" />
            Upload spreadsheet
          </button>

          <button
            type="button"
            className="w-full flex items-center gap-2 px-3 py-2 text-sm text-left hover:bg-muted transition-colors"
            onClick={handleImportDirectory}
          >
            <FolderOpen className="h-4 w-4 text-muted-foreground" />
            Import directory
          </button>
          <button
            type="button"
            className="w-full flex items-center gap-2 px-3 py-2 text-sm text-left hover:bg-muted transition-colors"
            onClick={handleImportArchive}
          >
            <Upload className="h-4 w-4 text-muted-foreground" />
            Import archive
          </button>

          <div className="border-t border-border my-1" />

          <button
            type="button"
            className="w-full flex items-center gap-2 px-3 py-2 text-sm text-left hover:bg-muted transition-colors"
            onClick={() => handleNavigate('/canvas/d2')}
          >
            <GitBranch className="h-4 w-4 text-muted-foreground" />
            New D2 diagram
          </button>
          <button
            type="button"
            className="w-full flex items-center gap-2 px-3 py-2 text-sm text-left hover:bg-muted transition-colors"
            onClick={() => handleNavigate('/documents/new/mermaid')}
          >
            <Workflow className="h-4 w-4 text-muted-foreground" />
            New Mermaid diagram
          </button>
          <button
            type="button"
            className="w-full flex items-center gap-2 px-3 py-2 text-sm text-left hover:bg-muted transition-colors"
            onClick={() => handleNavigate('/canvas')}
          >
            <PenTool className="h-4 w-4 text-muted-foreground" />
            New Excalidraw
          </button>

          <div className="border-t border-border my-1" />

          <button
            type="button"
            className="w-full flex items-center gap-2 px-3 py-2 text-sm text-left hover:bg-muted transition-colors"
            onClick={handleChatWithDocuments}
          >
            <MessageSquare className="h-4 w-4 text-muted-foreground" />
            Chat with documents
          </button>
        </div>
      )}
    </div>
  )
}

export default NewDocumentButton
