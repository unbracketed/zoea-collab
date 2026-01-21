/**
 * Rename Document Modal
 *
 * Simple modal for renaming a document.
 */

import { useEffect, useRef, useState } from 'react'
import { X } from 'lucide-react'
import toast from 'react-hot-toast'
import api from '../../services/api'

function RenameDocumentModal({ isOpen, onClose, document: doc, onSuccess }) {
  const inputRef = useRef(null)
  const [name, setName] = useState('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState(null)

  // Reset form and focus input when modal opens
  useEffect(() => {
    if (isOpen && doc) {
      setName(doc.name || '')
      setError(null)
      setSaving(false)
      // Focus input after state updates
      setTimeout(() => inputRef.current?.focus(), 0)
    }
  }, [isOpen, doc])

  // Close on escape key
  useEffect(() => {
    const handleEscape = (event) => {
      if (event.key === 'Escape' && isOpen && !saving) {
        onClose()
      }
    }

    window.addEventListener('keydown', handleEscape)
    return () => window.removeEventListener('keydown', handleEscape)
  }, [isOpen, onClose, saving])

  // Close when clicking outside
  const handleBackdropClick = (event) => {
    if (event.target === event.currentTarget && !saving) {
      onClose()
    }
  }

  const handleSave = async () => {
    const trimmedName = name.trim()
    if (!trimmedName) return

    setSaving(true)
    setError(null)

    try {
      await api.renameDocument(doc.id, trimmedName)
      toast.success('Document renamed')
      onSuccess?.({ ...doc, name: trimmedName })
      onClose()
    } catch (err) {
      console.error('Failed to rename document:', err)
      setError(err.message || 'Failed to rename document')
      setSaving(false)
    }
  }

  const handleKeyDown = (event) => {
    if (event.key === 'Enter' && name.trim() && !saving) {
      handleSave()
    }
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
        aria-labelledby="rename-document-title"
      >
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-border">
          <h2 id="rename-document-title" className="text-lg font-semibold">
            Rename
          </h2>
          <button
            type="button"
            onClick={onClose}
            disabled={saving}
            className="p-1 rounded-md hover:bg-muted text-muted-foreground hover:text-foreground transition-colors disabled:opacity-50"
            aria-label="Close"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Content */}
        <div className="p-6 space-y-4">
          {/* Error display */}
          {error && (
            <div className="p-3 rounded-lg bg-red-500/10 text-red-500 text-sm">
              {error}
            </div>
          )}

          {/* Name Field */}
          <div>
            <input
              ref={inputRef}
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              onKeyDown={handleKeyDown}
              className="w-full px-3 py-2 rounded-lg border border-border bg-background focus:ring-2 focus:ring-primary/50 focus:border-primary outline-none transition-colors"
              placeholder="Enter document name"
              disabled={saving}
            />
          </div>
        </div>

        {/* Footer */}
        <div className="flex justify-end gap-3 px-6 py-4 border-t border-border bg-muted/50">
          <button
            type="button"
            onClick={onClose}
            disabled={saving}
            className="px-4 py-2 text-sm font-medium rounded-lg border border-border hover:bg-background transition-colors disabled:opacity-50"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={handleSave}
            disabled={saving || !name.trim()}
            className="px-4 py-2 text-sm font-medium rounded-lg bg-primary text-white hover:bg-primary/90 transition-colors disabled:opacity-50"
          >
            {saving ? 'Saving...' : 'OK'}
          </button>
        </div>
      </div>
    </div>
  )
}

export default RenameDocumentModal
