/**
 * DocxViewer Component
 *
 * Displays Word documents (.docx) by fetching HTML content from the backend.
 * Supports download of the original file.
 */

import { useState, useEffect } from 'react';
import { Download } from 'lucide-react';
import DOMPurify from 'dompurify';
import api from '../../services/api';

/**
 * DocxViewer - Word document viewer
 *
 * @param {Object} props
 * @param {Object} props.document - Document object with docx_file URL
 * @param {string} props.className - Additional CSS classes
 */
export default function DocxViewer({ document, className = '' }) {
  const [html, setHtml] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!document?.id) return;

    const fetchHtml = async () => {
      setLoading(true);
      setError(null);
      try {
        const response = await api.getDocxHtml(document.id);
        // Sanitize HTML to prevent XSS attacks
        const sanitizedHtml = DOMPurify.sanitize(response.html, {
          USE_PROFILES: { html: true },
          ADD_TAGS: ['table', 'thead', 'tbody', 'tr', 'th', 'td'],
        });
        setHtml(sanitizedHtml);
      } catch (err) {
        console.error('Failed to load Word document:', err);
        setError('Failed to load document content');
      } finally {
        setLoading(false);
      }
    };

    fetchHtml();
  }, [document?.id]);

  if (!document?.docx_file) {
    return (
      <div className={`text-text-secondary p-4 ${className}`}>
        No Word document file available.
      </div>
    );
  }

  return (
    <div className={`flex flex-col h-full ${className}`}>
      {/* Toolbar */}
      <div className="flex items-center justify-between px-4 py-2 border-b border-border bg-surface">
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium">{document.name}</span>
          {document.paragraph_count && (
            <span className="text-xs text-text-secondary">
              ({document.paragraph_count} paragraphs)
            </span>
          )}
        </div>

        <div className="flex items-center gap-2">
          <a
            href={document.docx_file}
            download
            className="p-2 rounded hover:bg-background"
            title="Download Word Document"
          >
            <Download className="h-4 w-4" />
          </a>
        </div>
      </div>

      {/* Document Content */}
      <div className="flex-1 overflow-auto p-6 bg-white dark:bg-zinc-900">
        {loading ? (
          <div className="flex items-center justify-center p-8">
            <svg className="animate-spin h-6 w-6 text-primary" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
            </svg>
          </div>
        ) : error ? (
          <div className="text-red-500 p-4">{error}</div>
        ) : (
          <div
            className="prose prose-sm max-w-none dark:prose-invert docx-content"
            dangerouslySetInnerHTML={{ __html: html }}
          />
        )}
      </div>

      {/* File info */}
      {document.file_size && (
        <div className="px-4 py-2 border-t border-border text-xs text-text-secondary text-center">
          {formatFileSize(document.file_size)}
        </div>
      )}
    </div>
  );
}

function formatFileSize(bytes) {
  if (!bytes) return '';
  const units = ['B', 'KB', 'MB', 'GB'];
  let size = bytes;
  let unitIndex = 0;
  while (size >= 1024 && unitIndex < units.length - 1) {
    size /= 1024;
    unitIndex++;
  }
  return `${size.toFixed(1)} ${units[unitIndex]}`;
}
