/**
 * AIToolArtifacts Component
 *
 * Displays tool-generated artifacts (images, markdown tables, etc.) inline in chat messages.
 * Provides "Save to Library" functionality to persist artifacts as documents.
 *
 * Note: The save functionality requires passing an `api` prop with a `saveToolArtifact` method.
 * If not provided, the save button will be hidden.
 */

import * as React from 'react'
import { useState } from 'react'
import { Download, Library, Check, Loader2, ExternalLink, AlertCircle, Copy, Table2 } from 'lucide-react'
import { cn } from '../../lib/utils'
import { AIResponse } from './AIResponse'

/**
 * Single artifact display with save functionality
 */
const AIToolArtifactItem = React.forwardRef(
  ({ artifact, workspaceId, onSaved, api, className, ...props }, ref) => {
    const [saving, setSaving] = useState(false)
    const [saved, setSaved] = useState(false)
    const [error, setError] = useState(null)
    const [copied, setCopied] = useState(false)

    const handleSaveToLibrary = async () => {
      if (!workspaceId) {
        setError('No workspace selected')
        return
      }

      if (!api?.saveToolArtifact) {
        setError('Save API not available')
        return
      }

      // Inline content artifacts cannot be saved to library directly
      if (artifact.path?.startsWith('_inline_')) {
        setError('Inline artifacts cannot be saved to library')
        return
      }

      setSaving(true)
      setError(null)

      try {
        const result = await api.saveToolArtifact({
          artifact_type: artifact.type,
          file_path: artifact.path,
          workspace_id: workspaceId,
          title: artifact.title,
          mime_type: artifact.mime_type,
        })

        if (result.success) {
          setSaved(true)
          onSaved?.(result)
        } else {
          setError(result.message || 'Failed to save')
        }
      } catch (err) {
        console.error('Failed to save artifact:', err)
        setError(err.message || 'Failed to save artifact')
      } finally {
        setSaving(false)
      }
    }

    const handleCopyContent = async () => {
      if (!artifact.content) return
      try {
        await navigator.clipboard.writeText(artifact.content)
        setCopied(true)
        setTimeout(() => setCopied(false), 2000)
      } catch (err) {
        console.error('Failed to copy:', err)
      }
    }

    // Determine artifact type
    const isImage = artifact.type === 'image' || artifact.mime_type?.startsWith('image/')
    const isMarkdown = artifact.type === 'markdown' && artifact.content
    const isInline = artifact.path?.startsWith('_inline_')
    const canSave = api?.saveToolArtifact && !isInline

    return (
      <div
        ref={ref}
        className={cn(
          'relative group rounded-lg border border-border bg-background overflow-hidden',
          className
        )}
        {...props}
      >
        {/* Image display */}
        {isImage && artifact.url && (
          <div className="relative">
            <img
              src={artifact.url}
              alt={artifact.title || 'Generated image'}
              className="w-full max-h-96 object-contain bg-muted/20"
              loading="lazy"
            />

            {/* Overlay actions on hover */}
            <div className="absolute inset-0 bg-black/0 group-hover:bg-black/40 transition-colors flex items-center justify-center opacity-0 group-hover:opacity-100">
              <div className="flex gap-2">
                {/* Open in new tab */}
                <a
                  href={artifact.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="p-2 rounded-full bg-white/90 hover:bg-white text-gray-800 transition-colors"
                  title="Open in new tab"
                >
                  <ExternalLink className="h-4 w-4" />
                </a>

                {/* Download */}
                <a
                  href={artifact.url}
                  download={artifact.title || 'image'}
                  className="p-2 rounded-full bg-white/90 hover:bg-white text-gray-800 transition-colors"
                  title="Download"
                >
                  <Download className="h-4 w-4" />
                </a>
              </div>
            </div>
          </div>
        )}

        {/* Markdown content display (tables, etc.) */}
        {isMarkdown && (
          <div className="p-4 prose prose-sm dark:prose-invert max-w-none overflow-x-auto">
            <AIResponse>{artifact.content}</AIResponse>
          </div>
        )}

        {/* Footer with title and actions */}
        <div className="p-3 flex items-center justify-between gap-2 border-t border-border">
          <div className="flex-1 min-w-0 flex items-center gap-2">
            {isMarkdown && <Table2 className="h-4 w-4 text-muted-foreground flex-shrink-0" />}
            <div className="min-w-0">
              {artifact.title && (
                <p className="text-sm font-medium text-foreground truncate">
                  {artifact.title}
                </p>
              )}
              {artifact.mime_type && !isMarkdown && (
                <p className="text-xs text-muted-foreground">
                  {artifact.mime_type}
                </p>
              )}
            </div>
          </div>

          <div className="flex items-center gap-2">
            {/* Copy button for markdown content */}
            {isMarkdown && (
              <button
                onClick={handleCopyContent}
                className={cn(
                  'flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm font-medium transition-colors',
                  copied
                    ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400'
                    : 'bg-muted text-muted-foreground hover:bg-muted/80'
                )}
                title="Copy to clipboard"
              >
                {copied ? (
                  <>
                    <Check className="h-4 w-4" />
                    <span>Copied</span>
                  </>
                ) : (
                  <>
                    <Copy className="h-4 w-4" />
                    <span>Copy</span>
                  </>
                )}
              </button>
            )}

            {/* Save to Library button (not for inline artifacts) */}
            {canSave && (
              <button
                onClick={handleSaveToLibrary}
                disabled={saving || saved || !workspaceId}
                className={cn(
                  'flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm font-medium transition-colors',
                  saved
                    ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400'
                    : saving
                    ? 'bg-muted text-muted-foreground cursor-wait'
                    : 'bg-primary/10 text-primary hover:bg-primary/20'
                )}
                title={
                  saved
                    ? 'Saved to library'
                    : !workspaceId
                    ? 'Select a workspace to save'
                    : 'Save to document library'
                }
              >
                {saving ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin" />
                    <span>Saving...</span>
                  </>
                ) : saved ? (
                  <>
                    <Check className="h-4 w-4" />
                    <span>Saved</span>
                  </>
                ) : (
                  <>
                    <Library className="h-4 w-4" />
                    <span>Save to Library</span>
                  </>
                )}
              </button>
            )}
          </div>
        </div>

        {/* Error message */}
        {error && (
          <div className="px-3 pb-3">
            <div className="flex items-center gap-2 text-sm text-destructive">
              <AlertCircle className="h-4 w-4 flex-shrink-0" />
              <span>{error}</span>
            </div>
          </div>
        )}
      </div>
    )
  }
)
AIToolArtifactItem.displayName = 'AIToolArtifactItem'

/**
 * Container for multiple artifacts
 */
const AIToolArtifacts = React.forwardRef(
  ({ artifacts, workspaceId, api, onArtifactSaved, className, ...props }, ref) => {
    if (!artifacts || artifacts.length === 0) {
      return null
    }

    return (
      <div
        ref={ref}
        className={cn('mt-3 space-y-3', className)}
        {...props}
      >
        {artifacts.map((artifact, index) => (
          <AIToolArtifactItem
            key={artifact.path || index}
            artifact={artifact}
            workspaceId={workspaceId}
            api={api}
            onSaved={(result) => onArtifactSaved?.(artifact, result)}
          />
        ))}
      </div>
    )
  }
)
AIToolArtifacts.displayName = 'AIToolArtifacts'

export { AIToolArtifacts, AIToolArtifactItem }
