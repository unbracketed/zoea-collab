/**
 * Recent Documents List Component
 *
 * Displays a list of recent documents in the sidebar.
 * Shows document name, type, and last updated time.
 * Similar to ConversationList but for documents.
 */

import { useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useDocumentStore, useWorkspaceStore } from '../../stores'

function RecentDocumentsList({ limit = 5 }) {
  const navigate = useNavigate()

  const currentDocumentId = useDocumentStore((state) => state.currentDocumentId)
  const recentDocuments = useDocumentStore((state) => state.recentDocuments)
  const recentDocumentsLoading = useDocumentStore((state) => state.recentDocumentsLoading)
  const recentDocumentsError = useDocumentStore((state) => state.recentDocumentsError)
  const loadRecentDocuments = useDocumentStore((state) => state.loadRecentDocuments)

  const currentProjectId = useWorkspaceStore((state) => state.currentProjectId)

  useEffect(() => {
    if (currentProjectId) {
      loadRecentDocuments(currentProjectId)
    }
  }, [currentProjectId, loadRecentDocuments])

  const handleSelectDocument = (documentId) => {
    navigate(`/documents/${documentId}`)
  }

  if (recentDocumentsError) {
    return (
      <div className="bg-red-100 border border-red-400 text-red-700 px-3 py-2 rounded m-3 text-sm" role="alert">
        <small>Failed to load documents</small>
      </div>
    )
  }

  if (recentDocumentsLoading && recentDocuments.length === 0) {
    return (
      <div className="text-center p-3">
        <svg className="animate-spin h-4 w-4 text-primary mx-auto" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" role="status">
          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
        </svg>
        <span className="sr-only">Loading...</span>
        <p className="text-sm text-text-secondary mt-2">Loading documents...</p>
      </div>
    )
  }

  if (recentDocuments.length === 0) {
    return (
      <div className="text-center p-3">
        <p className="text-sm text-text-secondary">No documents yet</p>
        <p className="text-sm text-text-secondary">Upload or create documents to see them here</p>
      </div>
    )
  }

  const formatDate = (dateString) => {
    const date = new Date(dateString)
    const now = new Date()
    const diff = now - date

    // Less than 24 hours ago
    if (diff < 86400000) {
      return date.toLocaleTimeString('en-US', {
        hour: 'numeric',
        minute: '2-digit',
      })
    }

    // Less than 7 days ago
    if (diff < 604800000) {
      return date.toLocaleDateString('en-US', {
        weekday: 'short',
      })
    }

    // Older
    return date.toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
    })
  }

  // Sort documents by updated_at (most recent first) and limit
  const sortedDocuments = [...recentDocuments].sort((a, b) => {
    return new Date(b.updated_at) - new Date(a.updated_at)
  })
  const visibleDocuments = limit ? sortedDocuments.slice(0, limit) : sortedDocuments

  return (
    <div className="conversation-list">
      {visibleDocuments.map((doc) => (
        <div
          key={doc.id}
          className={`conversation-item ${
            currentDocumentId === doc.id ? 'active' : ''
          }`}
          onClick={() => handleSelectDocument(doc.id)}
          role="button"
          tabIndex={0}
          onKeyPress={(e) => {
            if (e.key === 'Enter') handleSelectDocument(doc.id)
          }}
        >
          <div className="conversation-item-content">
            <div className="conversation-title">{doc.name}</div>
            <div className="conversation-meta">
              <span className="message-count">
                {doc.document_type}
              </span>
              <span className="conversation-date">{formatDate(doc.updated_at)}</span>
            </div>
          </div>
        </div>
      ))}
    </div>
  )
}

export default RecentDocumentsList
