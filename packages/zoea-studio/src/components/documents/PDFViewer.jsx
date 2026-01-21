/**
 * PDFViewer Component
 *
 * Embedded PDF viewer using react-pdf (pdf.js).
 * Supports page navigation, zoom, and full document viewing.
 *
 * @see https://github.com/wojtekmaj/react-pdf
 */

import { useState, useCallback } from 'react';
import { Document, Page, pdfjs } from 'react-pdf';
import { ChevronLeft, ChevronRight, ZoomIn, ZoomOut, Download } from 'lucide-react';
import 'react-pdf/dist/Page/AnnotationLayer.css';
import 'react-pdf/dist/Page/TextLayer.css';

// Configure pdf.js worker
pdfjs.GlobalWorkerOptions.workerSrc = new URL(
  'pdfjs-dist/build/pdf.worker.min.mjs',
  import.meta.url
).toString();

/**
 * PDFViewer - Interactive PDF document viewer
 *
 * @param {Object} props
 * @param {Object} props.document - Document object with pdf_file URL
 * @param {string} props.className - Additional CSS classes
 */
export default function PDFViewer({ document, className = '' }) {
  const [numPages, setNumPages] = useState(null);
  const [pageNumber, setPageNumber] = useState(1);
  const [scale, setScale] = useState(1.0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const onDocumentLoadSuccess = useCallback(({ numPages }) => {
    setNumPages(numPages);
    setLoading(false);
    setError(null);
  }, []);

  const onDocumentLoadError = useCallback((err) => {
    console.error('PDF load error:', err);
    setError('Failed to load PDF document');
    setLoading(false);
  }, []);

  const goToPrevPage = () => setPageNumber((p) => Math.max(1, p - 1));
  const goToNextPage = () => setPageNumber((p) => Math.min(numPages || p, p + 1));
  const zoomIn = () => setScale((s) => Math.min(3.0, s + 0.25));
  const zoomOut = () => setScale((s) => Math.max(0.5, s - 0.25));

  if (!document?.pdf_file) {
    return (
      <div className={`text-text-secondary p-4 ${className}`}>
        No PDF file available.
      </div>
    );
  }

  return (
    <div className={`flex flex-col h-full ${className}`}>
      {/* Toolbar */}
      <div className="flex items-center justify-between px-4 py-2 border-b border-border bg-surface">
        <div className="flex items-center gap-2">
          <button
            onClick={goToPrevPage}
            disabled={pageNumber <= 1}
            className="p-2 rounded hover:bg-background disabled:opacity-50"
            title="Previous page"
          >
            <ChevronLeft className="h-4 w-4" />
          </button>
          <span className="text-sm">
            Page {pageNumber} of {numPages || '...'}
          </span>
          <button
            onClick={goToNextPage}
            disabled={pageNumber >= (numPages || 1)}
            className="p-2 rounded hover:bg-background disabled:opacity-50"
            title="Next page"
          >
            <ChevronRight className="h-4 w-4" />
          </button>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={zoomOut}
            disabled={scale <= 0.5}
            className="p-2 rounded hover:bg-background disabled:opacity-50"
            title="Zoom out"
          >
            <ZoomOut className="h-4 w-4" />
          </button>
          <span className="text-sm w-16 text-center">{Math.round(scale * 100)}%</span>
          <button
            onClick={zoomIn}
            disabled={scale >= 3.0}
            className="p-2 rounded hover:bg-background disabled:opacity-50"
            title="Zoom in"
          >
            <ZoomIn className="h-4 w-4" />
          </button>
          <a
            href={document.pdf_file}
            download
            className="p-2 rounded hover:bg-background ml-2"
            title="Download PDF"
          >
            <Download className="h-4 w-4" />
          </a>
        </div>
      </div>

      {/* PDF Content */}
      <div className="flex-1 overflow-auto flex justify-center p-4 bg-zinc-100 dark:bg-zinc-800">
        {error ? (
          <div className="text-red-500 p-4">{error}</div>
        ) : (
          <Document
            file={document.pdf_file}
            onLoadSuccess={onDocumentLoadSuccess}
            onLoadError={onDocumentLoadError}
            loading={
              <div className="flex items-center justify-center p-8">
                <svg className="animate-spin h-6 w-6 text-primary" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                </svg>
              </div>
            }
          >
            <Page
              pageNumber={pageNumber}
              scale={scale}
              renderTextLayer={true}
              renderAnnotationLayer={true}
              className="shadow-lg"
            />
          </Document>
        )}
      </div>

      {/* Page count info */}
      {document.page_count && (
        <div className="px-4 py-2 border-t border-border text-xs text-text-secondary text-center">
          {document.page_count} page{document.page_count !== 1 ? 's' : ''}
        </div>
      )}
    </div>
  );
}
