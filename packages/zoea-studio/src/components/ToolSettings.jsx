/**
 * Tool Settings Component
 *
 * Displays and manages available AI tools for a project.
 * Allows enabling/disabling tools and shows API key requirements.
 */

import { useEffect, useState, useCallback } from 'react'
import { Wrench, AlertCircle, ToggleLeft, ToggleRight, RefreshCw, Search, Image, FileText, Sparkles } from 'lucide-react'
import api from '../services/api'

// Category icons mapping
const CATEGORY_ICONS = {
  search: Search,
  image: Image,
  analysis: FileText,
  data: FileText,
  skills: Sparkles,
  default: Wrench,
}

// Category display names
const CATEGORY_NAMES = {
  search: 'Search',
  image: 'Image Generation',
  analysis: 'Analysis',
  data: 'Data Extraction',
  skills: 'Skills',
}

/**
 * Individual tool row component
 */
function ToolRow({ tool, onToggle, isToggling }) {
  const CategoryIcon = CATEGORY_ICONS[tool.category] || CATEGORY_ICONS.default
  const isDisabled = isToggling || (tool.requires_api_key && !tool.api_key_available)
  const canEnable = !tool.requires_api_key || tool.api_key_available

  return (
    <div className="flex items-start justify-between py-4 border-b border-border last:border-0">
      <div className="flex items-start gap-3 min-w-0 flex-1">
        <div className="mt-0.5 p-2 rounded-lg bg-muted">
          <CategoryIcon className="h-4 w-4 text-muted-foreground" />
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <span className="font-medium text-sm">{tool.name}</span>
            <span className="px-1.5 py-0.5 text-xs rounded bg-muted text-muted-foreground">
              {CATEGORY_NAMES[tool.category] || tool.category}
            </span>
          </div>
          <p className="text-sm text-muted-foreground mt-0.5">{tool.description}</p>

          {/* API key warning */}
          {tool.requires_api_key && !tool.api_key_available && (
            <div className="flex items-center gap-1.5 mt-2 text-amber-600 dark:text-amber-400">
              <AlertCircle className="h-3.5 w-3.5 flex-shrink-0" />
              <span className="text-xs">
                Requires {tool.requires_api_key} environment variable
              </span>
            </div>
          )}

          {/* Contexts badge */}
          {tool.supported_contexts && tool.supported_contexts.length > 0 && tool.supported_contexts[0] !== '*' && (
            <div className="flex items-center gap-1 mt-2">
              <span className="text-xs text-muted-foreground">Contexts:</span>
              {tool.supported_contexts.map((ctx) => (
                <span key={ctx} className="px-1.5 py-0.5 text-xs rounded bg-primary/10 text-primary">
                  {ctx}
                </span>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Toggle button */}
      <button
        type="button"
        onClick={() => onToggle(tool.name, !tool.is_enabled)}
        disabled={isDisabled}
        className={`ml-4 flex-shrink-0 p-1 rounded transition-colors ${
          isDisabled
            ? 'opacity-50 cursor-not-allowed'
            : 'hover:bg-muted'
        }`}
        title={
          !canEnable
            ? `Requires ${tool.requires_api_key}`
            : tool.is_enabled
              ? 'Click to disable'
              : 'Click to enable'
        }
        aria-label={tool.is_enabled ? `Disable ${tool.name}` : `Enable ${tool.name}`}
      >
        {tool.is_enabled ? (
          <ToggleRight className="h-6 w-6 text-primary" />
        ) : (
          <ToggleLeft className="h-6 w-6 text-muted-foreground" />
        )}
      </button>
    </div>
  )
}

/**
 * Main ToolSettings component
 */
function ToolSettings({ projectId }) {
  const [tools, setTools] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [togglingTool, setTogglingTool] = useState(null)

  // Load tools
  const loadTools = useCallback(async () => {
    if (!projectId) return

    setLoading(true)
    setError(null)

    try {
      const data = await api.fetchProjectTools(projectId)
      // API returns { tools: [...], project_id: ... }
      setTools(data.tools || [])
    } catch (err) {
      console.error('Failed to load tools:', err)
      setError(err.message || 'Failed to load tools')
    } finally {
      setLoading(false)
    }
  }, [projectId])

  // Load tools on mount and when projectId changes
  useEffect(() => {
    loadTools()
  }, [loadTools])

  // Handle toggle
  const handleToggle = async (toolName, enabled) => {
    setTogglingTool(toolName)

    try {
      if (enabled) {
        await api.enableTool(projectId, toolName)
      } else {
        await api.disableTool(projectId, toolName)
      }

      // Update local state
      setTools((prev) =>
        prev.map((tool) =>
          tool.name === toolName ? { ...tool, is_enabled: enabled } : tool
        )
      )
    } catch (err) {
      console.error(`Failed to ${enabled ? 'enable' : 'disable'} tool:`, err)
      setError(err.message || `Failed to ${enabled ? 'enable' : 'disable'} ${toolName}`)
    } finally {
      setTogglingTool(null)
    }
  }

  // Group tools by category
  const toolsByCategory = tools.reduce((acc, tool) => {
    const category = tool.category || 'other'
    if (!acc[category]) {
      acc[category] = []
    }
    acc[category].push(tool)
    return acc
  }, {})

  // Loading state
  if (loading) {
    return (
      <div className="flex items-center justify-center py-8">
        <RefreshCw className="h-5 w-5 animate-spin text-muted-foreground" />
        <span className="ml-2 text-muted-foreground">Loading tools...</span>
      </div>
    )
  }

  // Error state
  if (error) {
    return (
      <div className="p-4 rounded-lg bg-destructive/10 text-destructive border border-destructive/20">
        <div className="flex items-center gap-2">
          <AlertCircle className="h-4 w-4" />
          <span>{error}</span>
        </div>
        <button
          type="button"
          onClick={loadTools}
          className="mt-2 text-sm underline hover:no-underline"
        >
          Try again
        </button>
      </div>
    )
  }

  // Empty state
  if (tools.length === 0) {
    return (
      <div className="text-center py-8 text-muted-foreground">
        <Sparkles className="h-8 w-8 mx-auto mb-2 opacity-50" />
        <p>No tools available</p>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <p className="text-sm text-muted-foreground">
        Enable or disable AI tools for this project. Some tools require API keys to be configured in environment variables.
      </p>

      {/* Tools by category */}
      {Object.entries(toolsByCategory).map(([category, categoryTools]) => (
        <div key={category}>
          <h3 className="text-sm font-medium text-muted-foreground uppercase tracking-wide mb-3">
            {CATEGORY_NAMES[category] || category}
          </h3>
          <div className="bg-muted/30 rounded-lg px-4">
            {categoryTools.map((tool) => (
              <ToolRow
                key={tool.name}
                tool={tool}
                onToggle={handleToggle}
                isToggling={togglingTool === tool.name}
              />
            ))}
          </div>
        </div>
      ))}

      {/* Stats */}
      <div className="flex items-center gap-4 text-sm text-muted-foreground pt-2">
        <span>
          {tools.filter((t) => t.is_enabled).length} of {tools.length} tools enabled
        </span>
        <span>
          {tools.filter((t) => t.api_key_available === false).length} missing API keys
        </span>
      </div>
    </div>
  )
}

export default ToolSettings
