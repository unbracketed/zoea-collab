/**
 * Add Project Modal
 *
 * Modal for creating a new project with name, description, and color theme.
 */

import { useEffect, useRef, useState } from 'react'
import { Check, X } from 'lucide-react'
import { THEMES } from '../stores/themeStore'
import { useWorkspaceStore } from '../stores/workspaceStore'
import api from '../services/api'

// Primary color swatches for each theme (from shadcn OKLCH values)
const THEME_COLORS = {
  'amber-minimal': '#d4a259',
  'claude': '#c75f2a',
  'corporate': '#2563eb',
  'modern-minimal': '#7c3aed',
  'nature': '#059669',
  'slack': '#611f69',
  'twitter': '#1d9bf0',
  'cyberpunk': '#e11d48',
  'red': '#dc2626',
  'summer': '#ea580c',
  'notebook': '#3b82f6',
}

function AddProjectModal({ isOpen, onClose, onProjectCreated }) {
  const modalRef = useRef(null)

  // Form state
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [colorTheme, setColorTheme] = useState('claude')

  // UI state
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState(null)

  // Store actions
  const addProjectToState = useWorkspaceStore((state) => state.addProjectToState)

  // Reset form when modal opens
  useEffect(() => {
    if (isOpen) {
      setName('')
      setDescription('')
      setColorTheme('claude')
      setError(null)
    }
  }, [isOpen])

  // Close on escape key
  useEffect(() => {
    const handleEscape = (event) => {
      if (event.key === 'Escape' && isOpen) {
        onClose()
      }
    }

    document.addEventListener('keydown', handleEscape)
    return () => document.removeEventListener('keydown', handleEscape)
  }, [isOpen, onClose])

  // Close when clicking outside
  const handleBackdropClick = (event) => {
    if (event.target === event.currentTarget) {
      onClose()
    }
  }

  // Create project
  const handleCreate = async () => {
    if (!name.trim()) return

    setSaving(true)
    setError(null)

    try {
      const payload = {
        name: name.trim(),
        description: description.trim() || '',
        color_theme: colorTheme,
      }

      const newProject = await api.createProject(payload)

      // Add project to local state
      addProjectToState(newProject)

      // Notify parent
      if (onProjectCreated) {
        onProjectCreated(newProject)
      }

      onClose()
    } catch (err) {
      console.error('Failed to create project:', err)
      setError(err.message || 'Failed to create project')
    } finally {
      setSaving(false)
    }
  }

  if (!isOpen) return null

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50"
      onClick={handleBackdropClick}
    >
      <div
        ref={modalRef}
        className="bg-card text-card-foreground rounded-xl shadow-lg border border-border w-full max-w-md mx-4 overflow-hidden"
        role="dialog"
        aria-modal="true"
        aria-labelledby="add-project-title"
      >
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-border">
          <h2 id="add-project-title" className="text-lg font-semibold">
            New Project
          </h2>
          <button
            type="button"
            onClick={onClose}
            className="p-1 rounded-md hover:bg-muted text-muted-foreground hover:text-foreground transition-colors"
            aria-label="Close"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Content */}
        <div className="p-6 space-y-6">
          {/* Error display */}
          {error && (
            <div className="p-3 rounded-lg bg-red-500/10 text-red-500 text-sm">
              {error}
            </div>
          )}

          {/* Name Field */}
          <div>
            <label htmlFor="project-name" className="block text-sm font-medium mb-2">
              Name
            </label>
            <input
              id="project-name"
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="w-full px-3 py-2 rounded-lg border border-border bg-background focus:ring-2 focus:ring-primary/50 focus:border-primary outline-none transition-colors"
              placeholder="Project name"
              autoFocus
            />
          </div>

          {/* Description Field */}
          <div>
            <label htmlFor="project-description" className="block text-sm font-medium mb-2">
              Description
            </label>
            <textarea
              id="project-description"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={3}
              className="w-full px-3 py-2 rounded-lg border border-border bg-background focus:ring-2 focus:ring-primary/50 focus:border-primary outline-none transition-colors resize-none"
              placeholder="Project description (optional)"
            />
          </div>

          {/* Color Theme Section */}
          <div>
            <label className="block text-sm font-medium mb-2">Color Theme</label>
            <div className="flex flex-wrap gap-2">
              {THEMES.map((theme) => (
                <button
                  key={theme.id}
                  type="button"
                  onClick={() => setColorTheme(theme.id)}
                  className={`relative w-10 h-10 rounded-lg transition-all ${
                    colorTheme === theme.id
                      ? 'ring-2 ring-primary ring-offset-2 ring-offset-card'
                      : 'hover:scale-110'
                  }`}
                  style={{ backgroundColor: THEME_COLORS[theme.id] }}
                  title={theme.name}
                  aria-label={`${theme.name} theme`}
                  aria-pressed={colorTheme === theme.id}
                >
                  {colorTheme === theme.id && (
                    <Check className="absolute inset-0 m-auto h-5 w-5 text-white" />
                  )}
                </button>
              ))}
            </div>
            {colorTheme && (
              <p className="mt-2 text-sm text-muted-foreground">
                {THEMES.find((t) => t.id === colorTheme)?.name}
              </p>
            )}
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
            onClick={handleCreate}
            disabled={saving || !name.trim()}
            className="px-4 py-2 text-sm font-medium rounded-lg bg-primary text-white hover:bg-primary/90 transition-colors disabled:opacity-50"
          >
            {saving ? 'Creating...' : 'Create Project'}
          </button>
        </div>
      </div>
    </div>
  )
}

export default AddProjectModal
