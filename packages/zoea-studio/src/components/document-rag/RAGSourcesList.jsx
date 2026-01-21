/**
 * RAG Sources List
 *
 * Sidebar panel showing source documents from the most recent retrieval.
 */

import { FileText, Link2 } from 'lucide-react';
import { useRAGStore } from '../../stores/ragStore';

export default function RAGSourcesList() {
  const { sources, session } = useRAGStore();

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="px-4 py-3 border-b border-border">
        <h3 className="font-medium text-sm">Sources</h3>
        {session && (
          <p className="text-xs text-text-secondary mt-1">
            {session.document_count} documents indexed
          </p>
        )}
      </div>

      {/* Sources list */}
      <div className="flex-1 overflow-y-auto p-3">
        {sources.length === 0 ? (
          <div className="text-center text-text-secondary py-8">
            <Link2 className="h-8 w-8 mx-auto mb-3 opacity-50" />
            <p className="text-sm">No sources yet</p>
            <p className="text-xs mt-1">
              Sources will appear here when the AI retrieves information from your documents.
            </p>
          </div>
        ) : (
          <div className="space-y-2">
            {sources.map((source, idx) => (
              <div
                key={idx}
                className="p-3 bg-background rounded-lg border border-border"
              >
                <div className="flex items-start gap-2">
                  <FileText className="h-4 w-4 text-primary flex-shrink-0 mt-0.5" />
                  <div className="flex-1 min-w-0">
                    <p className="font-medium text-sm truncate">
                      {source.title || source.document_name || `Source ${idx + 1}`}
                    </p>
                    {source.document_type && (
                      <p className="text-xs text-text-secondary mt-0.5">
                        {source.document_type}
                      </p>
                    )}
                    {source.excerpt && (
                      <p className="text-xs text-text-secondary mt-2 line-clamp-3">
                        {source.excerpt}
                      </p>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
