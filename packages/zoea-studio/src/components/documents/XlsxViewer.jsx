/**
 * XlsxViewer Component
 *
 * Displays Excel spreadsheets (.xlsx) by fetching HTML content from the backend.
 * Supports download of the original file.
 *
 * Security: HTML content is sanitized using DOMPurify before rendering.
 */

import { useState, useEffect } from 'react';
import { Download } from 'lucide-react';
import DOMPurify from 'dompurify';
import api from '../../services/api';

/**
 * XlsxViewer - Spreadsheet document viewer
 *
 * @param {Object} props
 * @param {Object} props.document - Document object with xlsx_file URL
 * @param {string} props.className - Additional CSS classes
 */
export default function XlsxViewer({ document, className = '' }) {
  // State holds sanitized HTML only - see useEffect for DOMPurify.sanitize() call
  const [sanitizedHtml, setSanitizedHtml] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!document?.id) return;

    const fetchHtml = async () => {
      setLoading(true);
      setError(null);
      try {
        const response = await api.getXlsxHtml(document.id);
        // Sanitize HTML with DOMPurify to prevent XSS attacks
        const clean = DOMPurify.sanitize(response.html, {
          USE_PROFILES: { html: true },
          ADD_TAGS: ['table', 'thead', 'tbody', 'tr', 'th', 'td'],
        });
        setSanitizedHtml(clean);
      } catch (err) {
        console.error('Failed to load spreadsheet:', err);
        setError('Failed to load spreadsheet content');
      } finally {
        setLoading(false);
      }
    };

    fetchHtml();
  }, [document?.id]);

  if (!document?.xlsx_file) {
    return (
      <div className={`text-text-secondary p-4 ${className}`}>
        No spreadsheet file available.
      </div>
    );
  }

  return (
    <div className={`flex flex-col h-full ${className}`}>
      {/* Toolbar */}
      <div className="flex items-center justify-between px-4 py-2 border-b border-border bg-surface">
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium">{document.name}</span>
          {document.sheet_count && (
            <span className="text-xs text-text-secondary">
              ({document.sheet_count} sheet{document.sheet_count !== 1 ? 's' : ''})
            </span>
          )}
        </div>

        <div className="flex items-center gap-2">
          <a
            href={document.xlsx_file}
            download
            className="p-2 rounded hover:bg-background"
            title="Download Spreadsheet"
          >
            <Download className="h-4 w-4" />
          </a>
        </div>
      </div>

      {/* Spreadsheet Content */}
      <div className="flex-1 overflow-auto p-4 bg-white dark:bg-zinc-900">
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
          // Content is DOMPurify-sanitized in useEffect before being stored in state
          <div
            className="xlsx-content"
            dangerouslySetInnerHTML={{ __html: sanitizedHtml }}
          />
        )}
      </div>

      {/* File info */}
      {document.file_size && (
        <div className="px-4 py-2 border-t border-border text-xs text-text-secondary text-center">
          {formatFileSize(document.file_size)}
        </div>
      )}

      <style>{`
        .xlsx-content table {
          border-collapse: collapse;
          width: 100%;
          margin-bottom: 1rem;
          font-size: 0.875rem;
        }
        .xlsx-content th,
        .xlsx-content td {
          border: 1px solid var(--border, #e5e7eb);
          padding: 0.5rem 0.75rem;
          text-align: left;
          white-space: nowrap;
        }
        .xlsx-content th {
          background-color: var(--muted, #f3f4f6);
          font-weight: 600;
        }
        .xlsx-content .xlsx-sheet {
          margin-bottom: 2rem;
        }
        .xlsx-content .xlsx-sheet h3 {
          font-size: 1rem;
          font-weight: 600;
          margin-bottom: 0.5rem;
          color: var(--foreground);
        }
        .xlsx-content .table-wrapper {
          overflow-x: auto;
        }
        .dark .xlsx-content th {
          background-color: var(--muted, #27272a);
        }
      `}</style>
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
