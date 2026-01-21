import { useState, useEffect, useCallback } from 'react';
import { Paperclip, Download, ChevronDown, ChevronRight, FileText, Image, File } from 'lucide-react';
import api from '../services/api';

function AttachmentItem({ attachment, isExpanded, onToggle }) {
  const { filename, content_type, file_size, url } = attachment;

  const isImage = content_type?.startsWith('image/');
  const isPdf = content_type === 'application/pdf';

  const getIcon = () => {
    if (isImage) return <Image size={16} className="text-muted-foreground" />;
    if (isPdf) return <FileText size={16} className="text-muted-foreground" />;
    return <File size={16} className="text-muted-foreground" />;
  };

  const formatFileSize = (bytes) => {
    if (!bytes) return '';
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  return (
    <div className="border border-border rounded-lg mb-2 overflow-hidden">
      <div
        className="flex items-center justify-between px-3 py-2 bg-muted/50 cursor-pointer hover:bg-muted/70 transition-colors"
        onClick={onToggle}
      >
        <div className="flex items-center gap-2">
          <button
            type="button"
            className="p-0 bg-transparent border-none"
            aria-label={isExpanded ? 'Collapse' : 'Expand'}
          >
            {isExpanded ? (
              <ChevronDown size={16} className="text-muted-foreground" />
            ) : (
              <ChevronRight size={16} className="text-muted-foreground" />
            )}
          </button>
          {getIcon()}
          <span className="text-sm font-medium text-foreground truncate max-w-[180px]">
            {filename || 'Untitled'}
          </span>
          {file_size && (
            <span className="text-xs text-muted-foreground">
              ({formatFileSize(file_size)})
            </span>
          )}
        </div>
        {url && (
          <a
            href={url}
            target="_blank"
            rel="noopener noreferrer"
            className="p-1.5 text-muted-foreground hover:text-foreground hover:bg-muted rounded transition-colors"
            onClick={(e) => e.stopPropagation()}
            title="Download"
          >
            <Download size={14} />
          </a>
        )}
      </div>
      {isExpanded && (
        <div className="p-3 bg-zinc-900">
          {isImage && url && (
            <img
              src={url}
              alt={filename || 'Attachment'}
              className="max-w-full max-h-64 object-contain rounded"
            />
          )}
          {isPdf && url && (
            <div className="text-sm text-muted-foreground">
              <a
                href={url}
                target="_blank"
                rel="noopener noreferrer"
                className="text-primary hover:underline"
              >
                Open PDF in new tab
              </a>
            </div>
          )}
          {!isImage && !isPdf && (
            <p className="text-sm text-muted-foreground">
              {content_type || 'Unknown'} file
            </p>
          )}
        </div>
      )}
    </div>
  );
}

function AttachmentsPanel({ emailThreadId, refreshKey = 0 }) {
  const [attachments, setAttachments] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [expandedIds, setExpandedIds] = useState(new Set());

  const loadAttachments = useCallback(async () => {
    if (!emailThreadId) {
      setAttachments([]);
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const data = await api.fetchEmailThreadAttachments(emailThreadId);
      setAttachments(data.items || []);
    } catch (err) {
      console.error('Failed to load attachments:', err);
      setError(err.message);
      setAttachments([]);
    } finally {
      setLoading(false);
    }
  }, [emailThreadId]);

  useEffect(() => {
    loadAttachments();
  }, [loadAttachments, refreshKey]);

  const toggleExpanded = (id) => {
    setExpandedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  };

  if (!emailThreadId) {
    return null;
  }

  if (loading) {
    return (
      <aside className="p-4 bg-background h-full">
        <div className="flex items-center gap-2 mb-4 text-foreground">
          <Paperclip size={18} />
          <span className="font-medium">Attachments</span>
        </div>
        <div className="flex items-center justify-center py-8">
          <div className="animate-spin h-5 w-5 border-2 border-primary border-t-transparent rounded-full" />
        </div>
      </aside>
    );
  }

  if (error) {
    return (
      <aside className="p-4 bg-background h-full">
        <div className="flex items-center gap-2 mb-4 text-foreground">
          <Paperclip size={18} />
          <span className="font-medium">Attachments</span>
        </div>
        <div className="p-3 bg-destructive/10 border border-destructive/20 rounded-lg text-sm text-destructive">
          {error}
        </div>
      </aside>
    );
  }

  return (
    <aside className="p-4 bg-background h-full overflow-y-auto">
      <div className="flex items-center gap-2 mb-4 text-foreground">
        <Paperclip size={18} />
        <span className="font-medium">Attachments</span>
        {attachments.length > 0 && (
          <span className="ml-auto text-xs text-muted-foreground bg-muted px-2 py-0.5 rounded-full">
            {attachments.length}
          </span>
        )}
      </div>

      {attachments.length === 0 ? (
        <p className="text-sm text-muted-foreground">
          No attachments in this email thread.
        </p>
      ) : (
        <div className="space-y-2">
          {attachments.map((attachment) => (
            <AttachmentItem
              key={attachment.id}
              attachment={attachment}
              isExpanded={expandedIds.has(attachment.id)}
              onToggle={() => toggleExpanded(attachment.id)}
            />
          ))}
        </div>
      )}
    </aside>
  );
}

export default AttachmentsPanel;
