/**
 * Document RAG Chat Modal
 *
 * Modal overlay for chatting with selected documents.
 * Can be triggered from document list, clipboard, or document detail views.
 */

import { useEffect, useRef, useCallback } from 'react';
import { X, MessageSquare, Loader2 } from 'lucide-react';
import { useRAGStore } from '../../stores/ragStore';
import { useWorkspaceStore } from '../../stores';
import RAGChatPanel from './RAGChatPanel';
import RAGSourcesList from './RAGSourcesList';

export default function DocumentRAGModal({
  isOpen,
  onClose,
  contextType, // 'single' | 'folder' | 'clipboard' | 'collection'
  contextId, // ID of the context item
  contextName, // Display name for the context
}) {
  const modalRef = useRef(null);
  const currentProjectId = useWorkspaceStore((state) => state.currentProjectId);
  const currentWorkspaceId = useWorkspaceStore((state) => state.currentWorkspaceId);

  const { session, isLoading, error, createSession, closeSession } = useRAGStore();

  // Initialize session when modal opens
  useEffect(() => {
    if (isOpen && !session && currentProjectId && currentWorkspaceId && contextId) {
      createSession({
        contextType,
        contextId,
        projectId: currentProjectId,
        workspaceId: currentWorkspaceId,
      }).catch((err) => {
        console.error('Failed to create RAG session:', err);
      });
    }
  }, [isOpen, session, contextType, contextId, currentProjectId, currentWorkspaceId, createSession]);

  // Cleanup on close
  const handleClose = useCallback(() => {
    closeSession();
    onClose();
  }, [closeSession, onClose]);

  // Handle escape key
  useEffect(() => {
    const handleEscape = (e) => {
      if (e.key === 'Escape' && isOpen) {
        handleClose();
      }
    };
    document.addEventListener('keydown', handleEscape);
    return () => document.removeEventListener('keydown', handleEscape);
  }, [isOpen, handleClose]);

  // Handle click outside
  const handleBackdropClick = (e) => {
    if (e.target === e.currentTarget) {
      handleClose();
    }
  };

  if (!isOpen) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50"
      onClick={handleBackdropClick}
    >
      <div
        ref={modalRef}
        className="bg-surface rounded-xl shadow-lg w-full max-w-4xl h-[80vh] mx-4 flex flex-col overflow-hidden"
        role="dialog"
        aria-modal="true"
        aria-labelledby="rag-modal-title"
      >
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-border">
          <div className="flex items-center gap-3">
            <MessageSquare className="h-5 w-5 text-primary" />
            <div>
              <h2 id="rag-modal-title" className="text-lg font-semibold">
                Chat with Documents
              </h2>
              <p className="text-sm text-text-secondary">
                {contextName || (session ? `${session.document_count} documents` : 'Loading...')}
              </p>
            </div>
          </div>
          <button
            onClick={handleClose}
            className="p-2 rounded-md hover:bg-background transition-colors"
            aria-label="Close modal"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Content */}
        <div className="flex flex-1 min-h-0">
          {isLoading ? (
            <div className="flex flex-col items-center justify-center w-full gap-3">
              <Loader2 className="h-8 w-8 animate-spin text-primary" />
              <span className="text-text-secondary">Initializing document index...</span>
            </div>
          ) : error ? (
            <div className="flex flex-col items-center justify-center w-full p-6">
              <div className="text-red-500 text-center">
                <p className="font-medium">Failed to initialize session</p>
                <p className="text-sm mt-1">{error}</p>
              </div>
              <button
                onClick={handleClose}
                className="mt-4 px-4 py-2 bg-primary text-white rounded-md hover:bg-primary/90"
              >
                Close
              </button>
            </div>
          ) : (
            <>
              {/* Chat panel - main area */}
              <div className="flex-1 min-w-0 flex flex-col">
                <RAGChatPanel />
              </div>

              {/* Sources sidebar - hidden on small screens */}
              <div className="w-72 border-l border-border hidden lg:block overflow-hidden">
                <RAGSourcesList />
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
