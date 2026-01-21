/**
 * AIMessageAttachments Component
 *
 * Displays email attachments as a thumbnail grid above message content.
 * Clicking a thumbnail opens a modal preview for images.
 */

import * as React from 'react'
import { useState } from 'react'
import { X, Download, ExternalLink, File } from 'lucide-react'
import { cn } from '../../lib/utils'

/**
 * Modal for previewing image attachments
 */
function ImagePreviewModal({ attachment, onClose }) {
  // Close on escape key
  React.useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === 'Escape') {
        onClose()
      }
    }
    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [onClose])

  // Prevent scroll on body when modal is open
  React.useEffect(() => {
    document.body.style.overflow = 'hidden'
    return () => {
      document.body.style.overflow = ''
    }
  }, [])

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/80"
      onClick={onClose}
    >
      {/* Close button */}
      <button
        onClick={onClose}
        className="absolute top-4 right-4 p-2 rounded-full bg-white/10 hover:bg-white/20 text-white transition-colors"
        aria-label="Close preview"
      >
        <X className="h-6 w-6" />
      </button>

      {/* Action buttons */}
      <div className="absolute top-4 right-16 flex gap-2">
        <a
          href={attachment.url}
          target="_blank"
          rel="noopener noreferrer"
          className="p-2 rounded-full bg-white/10 hover:bg-white/20 text-white transition-colors"
          title="Open in new tab"
          onClick={(e) => e.stopPropagation()}
        >
          <ExternalLink className="h-5 w-5" />
        </a>
        <a
          href={attachment.url}
          download={attachment.filename}
          className="p-2 rounded-full bg-white/10 hover:bg-white/20 text-white transition-colors"
          title="Download"
          onClick={(e) => e.stopPropagation()}
        >
          <Download className="h-5 w-5" />
        </a>
      </div>

      {/* Image container */}
      <div
        className="relative max-w-[90vw] max-h-[90vh]"
        onClick={(e) => e.stopPropagation()}
      >
        <img
          src={attachment.url}
          alt={attachment.filename}
          className="max-w-full max-h-[90vh] object-contain rounded-lg"
        />

        {/* Filename label */}
        <div className="absolute bottom-0 left-0 right-0 p-3 bg-gradient-to-t from-black/60 to-transparent rounded-b-lg">
          <p className="text-white text-sm truncate">{attachment.filename}</p>
        </div>
      </div>
    </div>
  )
}

/**
 * Single attachment thumbnail
 */
function AttachmentThumbnail({ attachment, onClick }) {
  const isImage = attachment.content_type?.startsWith('image/')

  if (isImage) {
    return (
      <button
        onClick={onClick}
        className="relative aspect-square rounded-lg border-2 border-border overflow-hidden hover:border-primary/50 transition-colors focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2"
      >
        <img
          src={attachment.url}
          alt={attachment.filename}
          className="w-full h-full object-cover"
          loading="lazy"
        />
      </button>
    )
  }

  // Non-image attachment (fallback - show icon and filename)
  return (
    <a
      href={attachment.url}
      target="_blank"
      rel="noopener noreferrer"
      className="relative aspect-square rounded-lg border-2 border-border overflow-hidden hover:border-primary/50 transition-colors flex flex-col items-center justify-center gap-1 bg-muted/50 p-2"
    >
      <File className="h-6 w-6 text-muted-foreground" />
      <span className="text-xs text-muted-foreground truncate w-full text-center">
        {attachment.filename}
      </span>
    </a>
  )
}

/**
 * Grid of attachment thumbnails
 */
const AIMessageAttachments = React.forwardRef(
  ({ attachments, className, ...props }, ref) => {
    const [previewAttachment, setPreviewAttachment] = useState(null)

    if (!attachments || attachments.length === 0) {
      return null
    }

    // Filter to only show images for now (as per requirements)
    const imageAttachments = attachments.filter(att =>
      att.content_type?.startsWith('image/')
    )

    if (imageAttachments.length === 0) {
      return null
    }

    return (
      <>
        <div
          ref={ref}
          className={cn(
            'grid gap-2 mb-3',
            // Responsive grid columns based on attachment count
            imageAttachments.length === 1 && 'grid-cols-1 max-w-[200px]',
            imageAttachments.length === 2 && 'grid-cols-2 max-w-[300px]',
            imageAttachments.length >= 3 && 'grid-cols-3 max-w-[400px]',
            className
          )}
          {...props}
        >
          {imageAttachments.map((attachment) => (
            <AttachmentThumbnail
              key={attachment.id}
              attachment={attachment}
              onClick={() => setPreviewAttachment(attachment)}
            />
          ))}
        </div>

        {/* Modal preview */}
        {previewAttachment && (
          <ImagePreviewModal
            attachment={previewAttachment}
            onClose={() => setPreviewAttachment(null)}
          />
        )}
      </>
    )
  }
)
AIMessageAttachments.displayName = 'AIMessageAttachments'

export { AIMessageAttachments, ImagePreviewModal }
