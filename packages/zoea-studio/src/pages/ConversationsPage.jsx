/**
 * Conversations Page
 *
 * Full list view for all chat conversations in the current Project/Workspace.
 * Provides search, filter, and navigation to individual conversations.
 */

import { useState, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { MessageSquare, Search, Plus, Trash2 } from 'lucide-react';
import { useConversationStore, useWorkspaceStore } from '../stores';
import { useShallow } from 'zustand/react/shallow';
import LayoutFrame from '../components/layout/LayoutFrame';

function ConversationsPage() {
  const navigate = useNavigate();
  const [searchQuery, setSearchQuery] = useState('');
  const [deletingId, setDeletingId] = useState(null);

  const currentWorkspaceId = useWorkspaceStore((state) => state.currentWorkspaceId);
  const currentProjectId = useWorkspaceStore((state) => state.currentProjectId);
  const currentWorkspace = useWorkspaceStore((state) => state.getCurrentWorkspace());
  const currentProject = useWorkspaceStore((state) => state.getCurrentProject());

  const {
    conversations,
    currentConversationId,
    loading,
    error,
    deleteConversation,
  } = useConversationStore(
    useShallow((state) => ({
      conversations: state.conversations,
      currentConversationId: state.currentConversationId,
      loading: state.loading,
      error: state.error,
      deleteConversation: state.deleteConversation,
    }))
  );

  const handleSelectConversation = (conversationId) => {
    navigate(`/chat/${conversationId}`);
  };

  const handleNewChat = () => {
    navigate('/chat');
  };

  const handleDeleteConversation = async (e, conversationId) => {
    e.stopPropagation(); // Prevent selecting the conversation when clicking delete

    if (!window.confirm('Are you sure you want to delete this conversation?')) {
      return;
    }

    try {
      setDeletingId(conversationId);
      await deleteConversation(conversationId);

      // If the deleted conversation was the current one, clear selection
      if (currentConversationId === conversationId) {
        navigate('/conversations');
      }
    } catch (err) {
      console.error('Failed to delete conversation:', err);
      alert('Failed to delete conversation. Please try again.');
    } finally {
      setDeletingId(null);
    }
  };

  const formatDate = (dateString) => {
    const date = new Date(dateString);
    const now = new Date();
    const diff = now - date;

    // Less than 24 hours ago - show time
    if (diff < 86400000) {
      return date.toLocaleTimeString('en-US', {
        hour: 'numeric',
        minute: '2-digit',
      });
    }

    // Less than 7 days ago - show day
    if (diff < 604800000) {
      return date.toLocaleDateString('en-US', {
        weekday: 'short',
        hour: 'numeric',
        minute: '2-digit',
      });
    }

    // Older - show full date
    return date.toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: date.getFullYear() !== now.getFullYear() ? 'numeric' : undefined,
    });
  };

  // Sort conversations by updated_at (most recent first) and filter by search
  const filteredConversations = useMemo(() => {
    let result = [...conversations].sort((a, b) => {
      return new Date(b.updated_at) - new Date(a.updated_at);
    });

    if (searchQuery.trim()) {
      const query = searchQuery.toLowerCase();
      result = result.filter((conv) =>
        conv.title?.toLowerCase().includes(query)
      );
    }

    return result;
  }, [conversations, searchQuery]);

  const actions = (
    <button className="px-4 py-2 bg-primary text-white rounded-md hover:opacity-90 transition-opacity flex items-center" onClick={handleNewChat}>
      <Plus size={18} className="mr-1" />
      New Chat
    </button>
  );

  const content = currentWorkspaceId ? (
    <div className="conversations-page">
      {/* Search bar */}
      <div className="mb-4">
        <div className="relative">
          <Search
            size={18}
            className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400"
          />
          <input
            type="text"
            className="w-full px-3 py-2 pl-10 border border-border rounded-md bg-background focus:outline-none focus:ring-2 focus:ring-primary"
            placeholder="Search conversations..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
          />
        </div>
      </div>

      {/* Error state */}
      {error && (
        <div className="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded" role="alert">
          Failed to load conversations: {error}
        </div>
      )}

      {/* Loading state */}
      {loading && conversations.length === 0 && (
        <div className="text-center py-8">
          <svg className="animate-spin h-8 w-8 text-primary mx-auto" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" role="status">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
          </svg>
          <span className="sr-only">Loading...</span>
          <p className="text-gray-500 mt-2">Loading conversations...</p>
        </div>
      )}

      {/* Empty state */}
      {!loading && filteredConversations.length === 0 && (
        <div className="text-center py-12">
          <MessageSquare size={48} className="mx-auto text-gray-300 mb-4" />
          {searchQuery ? (
            <>
              <h5 className="text-gray-600">No matching conversations</h5>
              <p className="text-gray-500">
                Try adjusting your search query
              </p>
            </>
          ) : (
            <>
              <h5 className="text-gray-600">No conversations yet</h5>
              <p className="text-gray-500 mb-4">
                Start a new chat to begin
              </p>
              <button className="px-4 py-2 bg-primary text-white rounded-md hover:opacity-90 transition-opacity flex items-center" onClick={handleNewChat}>
                <Plus size={18} className="mr-1" />
                Start New Chat
              </button>
            </>
          )}
        </div>
      )}

      {/* Conversations list */}
      {filteredConversations.length > 0 && (
        <div className="conversations-list-full">
          {filteredConversations.map((conversation) => (
            <div
              key={conversation.id}
              className={`conversation-card ${
                currentConversationId === conversation.id ? 'active' : ''
              }`}
              onClick={() => handleSelectConversation(conversation.id)}
              role="button"
              tabIndex={0}
              onKeyPress={(e) => {
                if (e.key === 'Enter') handleSelectConversation(conversation.id);
              }}
            >
              <div className="conversation-card-icon">
                <MessageSquare size={20} />
              </div>
              <div className="conversation-card-content">
                <div className="conversation-card-title">{conversation.title}</div>
                <div className="conversation-card-meta">
                  <span className="message-count">
                    {conversation.message_count} message{conversation.message_count !== 1 ? 's' : ''}
                  </span>
                  <span className="separator">·</span>
                  <span className="updated-at">{formatDate(conversation.updated_at)}</span>
                </div>
              </div>
              <button
                className="conversation-card-delete"
                onClick={(e) => handleDeleteConversation(e, conversation.id)}
                disabled={deletingId === conversation.id}
                title="Delete conversation"
                aria-label="Delete conversation"
              >
                {deletingId === conversation.id ? (
                  <svg className="animate-spin h-4 w-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" role="status" aria-hidden="true">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                  </svg>
                ) : (
                  <Trash2 size={18} />
                )}
              </button>
            </div>
          ))}
        </div>
      )}

      {/* Results count */}
      {!loading && filteredConversations.length > 0 && (
        <div className="text-sm text-gray-500 mt-4 text-center">
          Showing {filteredConversations.length} of {conversations.length} conversation{conversations.length !== 1 ? 's' : ''}
        </div>
      )}
    </div>
  ) : (
    <div className="text-center py-12">
      <MessageSquare size={48} className="mx-auto text-gray-300 mb-4" />
      <h5 className="text-gray-600">Select a workspace</h5>
      <p className="text-gray-500">
        Choose a project and workspace from the sidebar to view conversations.
      </p>
    </div>
  );

  return (
    <LayoutFrame title="Conversations" actions={actions} variant="content-centered">
      {content}
    </LayoutFrame>
  );
}

export default ConversationsPage;
