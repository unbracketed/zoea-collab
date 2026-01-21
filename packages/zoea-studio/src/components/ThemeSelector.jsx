/**
 * Theme Selector Component
 *
 * Dropdown for selecting color themes and light/dark mode.
 * Uses shadcn.io OKLCH-based themes.
 */

import { useEffect, useRef, useState } from 'react'
import { Check, ChevronDown, Monitor, Moon, Palette, Sun, ToggleLeft, ToggleRight } from 'lucide-react'
import { useThemeStore, THEMES, MODES } from '../stores/themeStore'
import { useWorkspaceStore } from '../stores/workspaceStore'
import api from '../services/api'

// Primary color swatches for each theme (approximate hex from OKLCH)
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

const MODE_ICONS = {
  light: Sun,
  dark: Moon,
  auto: Monitor,
}

function ThemeSelector() {
  const [isOpen, setIsOpen] = useState(false)
  const dropdownRef = useRef(null)

  const theme = useThemeStore((state) => state.theme)
  const mode = useThemeStore((state) => state.mode)
  const setTheme = useThemeStore((state) => state.setTheme)
  const setMode = useThemeStore((state) => state.setMode)

  const currentProjectId = useWorkspaceStore((state) => state.currentProjectId)
  const getCurrentProject = useWorkspaceStore((state) => state.getCurrentProject)
  const updateProjectInState = useWorkspaceStore((state) => state.updateProjectInState)

  // Get current project for primary header toggle
  const currentProject = getCurrentProject()
  const usePrimaryHeader = currentProject?.use_primary_header ?? false

  // Toggle primary header setting
  const handlePrimaryHeaderToggle = async () => {
    if (!currentProjectId) return

    const newValue = !usePrimaryHeader
    try {
      const updatedProject = await api.updateProject(currentProjectId, { use_primary_header: newValue })
      updateProjectInState(updatedProject)
    } catch (err) {
      console.error('Failed to toggle primary header:', err)
    }
  }

  // Persist theme change to project settings
  const handleThemeChange = async (newTheme) => {
    setTheme(newTheme)

    // Also persist to current project if one is selected
    if (currentProjectId) {
      try {
        const updatedProject = await api.updateProject(currentProjectId, { color_theme: newTheme })
        updateProjectInState(updatedProject)
      } catch (err) {
        console.error('Failed to persist theme to project:', err)
        // Theme is still applied locally even if API fails
      }
    }
  }

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

  const ModeIcon = MODE_ICONS[mode] || Monitor

  return (
    <div className="relative" ref={dropdownRef}>
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        className="inline-flex items-center gap-1.5 h-10 px-3 rounded-md border border-sidebar-border bg-sidebar hover:bg-sidebar-accent text-sidebar-foreground transition-colors"
        aria-label="Theme settings"
        aria-expanded={isOpen}
        aria-haspopup="true"
      >
        <Palette className="h-4 w-4" />
        <ChevronDown className={`h-3 w-3 transition-transform ${isOpen ? 'rotate-180' : ''}`} />
      </button>

      {isOpen && (
        <div className="absolute right-0 top-full mt-2 w-72 bg-card border border-border rounded-lg shadow-lg z-50 overflow-hidden">
          {/* Color Themes Section */}
          <div className="p-3 border-b border-border">
            <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-2">
              Color Theme
            </h3>
            <div className="grid grid-cols-3 gap-1.5 max-h-48 overflow-y-auto">
              {THEMES.map((t) => (
                <button
                  key={t.id}
                  type="button"
                  onClick={() => handleThemeChange(t.id)}
                  title={t.description}
                  className={`relative flex flex-col items-center gap-1 px-2 py-2 rounded-md text-center transition-colors ${
                    theme === t.id
                      ? 'bg-primary/10 ring-1 ring-primary'
                      : 'hover:bg-muted'
                  }`}
                >
                  <span
                    className="relative w-6 h-6 rounded-full flex-shrink-0 border-2 border-white/20 shadow-sm flex items-center justify-center"
                    style={{ backgroundColor: THEME_COLORS[t.id] }}
                  >
                    {theme === t.id && (
                      <Check className="h-4 w-4 text-white" />
                    )}
                  </span>
                  <span className="text-xs truncate w-full">{t.name}</span>
                </button>
              ))}
            </div>
          </div>

          {/* Mode Section */}
          <div className="p-3 border-b border-border">
            <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-2">
              Appearance
            </h3>
            <div className="flex gap-1 bg-muted p-1 rounded-md">
              {MODES.map((m) => {
                const Icon = MODE_ICONS[m.id]
                return (
                  <button
                    key={m.id}
                    type="button"
                    onClick={() => setMode(m.id)}
                    className={`flex-1 flex items-center justify-center gap-1.5 py-1.5 px-2 rounded text-sm transition-colors ${
                      mode === m.id
                        ? 'bg-card shadow-sm font-medium'
                        : 'text-muted-foreground hover:text-foreground'
                    }`}
                  >
                    <Icon className="h-3.5 w-3.5" />
                    <span>{m.name}</span>
                  </button>
                )
              })}
            </div>
          </div>

          {/* Primary Header Toggle - only show when a project is selected */}
          {currentProjectId && (
            <div className="p-3">
              <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-2">
                Header Style
              </h3>
              <button
                type="button"
                onClick={handlePrimaryHeaderToggle}
                className="w-full flex items-center justify-between px-3 py-2 rounded-md hover:bg-muted transition-colors"
              >
                <span className="text-sm">Use primary color header</span>
                {usePrimaryHeader ? (
                  <ToggleRight className="h-6 w-6 text-primary" />
                ) : (
                  <ToggleLeft className="h-6 w-6 text-muted-foreground" />
                )}
              </button>
              <p className="text-xs text-muted-foreground mt-1 px-3">
                Apply theme color to app header and navigation
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export default ThemeSelector
