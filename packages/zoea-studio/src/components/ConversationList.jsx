/**
 * Conversation List Component
 *
 * Displays list of conversations in the sidebar.
 * Shows conversation titles only for a clean, maximized display.
 */

import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useConversationStore } from '../stores';

function ConversationList() {
  const navigate = useNavigate();
  const [deletingId, setDeletingId] = useState(null);
  const conversations = useConversationStore((state) => state.conversations);
  const currentConversationId = useConversationStore((state) => state.currentConversationId);
  const deleteConversation = useConversationStore((state) => state.deleteConversation);
  const loading = useConversationStore((state) => state.loading);
  const error = useConversationStore((state) => state.error);

  const handleSelectConversation = (conversationId) => {
    // Navigate first, then ChatPage's syncConversation effect will load the conversation.
    // This prevents a race condition where the "clear conversation when at /chat" effect
    // clears the conversation before the URL changes.
    console.log('[ConversationList] handleSelectConversation - navigating to:', `/chat/${conversationId}`);
    navigate(`/chat/${conversationId}`);
  };

  const handleDeleteConversation = async (e, conversationId) => {
    e.stopPropagation(); // Prevent selecting the conversation when clicking delete

    if (!window.confirm('Are you sure you want to delete this conversation?')) {
      return;
    }

    try {
      setDeletingId(conversationId);
      await deleteConversation(conversationId);

      // If the deleted conversation was the current one, navigate to /chat
      if (currentConversationId === conversationId) {
        navigate('/chat');
      }
    } catch (err) {
      console.error('Failed to delete conversation:', err);
      alert('Failed to delete conversation. Please try again.');
    } finally {
      setDeletingId(null);
    }
  };

  if (error) {
    return (
      <div className="bg-red-100 border border-red-400 text-red-700 px-3 py-2 rounded m-3 text-sm" role="alert">
        <small>Failed to load conversations</small>
      </div>
    );
  }

  if (loading && conversations.length === 0) {
    return (
      <div className="text-center p-3">
        <svg className="animate-spin h-4 w-4 text-primary mx-auto" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
        </svg>
        <span className="sr-only">Loading...</span>
        <p className="text-sm text-text-secondary mt-2">Loading conversations...</p>
      </div>
    );
  }

  if (conversations.length === 0) {
    return (
      <div className="text-center p-3">
        <p className="text-sm text-text-secondary">No conversations yet</p>
        <p className="text-sm text-text-secondary">Start a new chat to begin</p>
      </div>
    );
  }

  // Sort conversations by updated_at (most recent first)
  const sortedConversations = [...conversations].sort((a, b) => {
    return new Date(b.updated_at) - new Date(a.updated_at);
  });

  return (
    <div className="conversation-list">
      {sortedConversations.map((conversation) => (
        <div
          key={conversation.id}
          className={`conversation-item ${
            currentConversationId === conversation.id ? 'active' : ''
          }`}
          onClick={() => handleSelectConversation(conversation.id)}
          role="button"
          tabIndex={0}
          onKeyPress={(e) => {
            if (e.key === 'Enter') handleSelectConversation(conversation.id);
          }}
        >
          <div className="conversation-item-content">
            <div className="conversation-title">{conversation.title || 'Untitled'}</div>
          </div>
          <button
            className="conversation-delete-btn"
            onClick={(e) => handleDeleteConversation(e, conversation.id)}
            disabled={deletingId === conversation.id}
            title="Delete conversation"
            aria-label="Delete conversation"
          >
            {deletingId === conversation.id ? (
              <svg className="animate-spin h-4 w-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
              </svg>
            ) : (
              <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" viewBox="0 0 16 16">
                <path d="M5.5 5.5A.5.5 0 0 1 6 6v6a.5.5 0 0 1-1 0V6a.5.5 0 0 1 .5-.5zm2.5 0a.5.5 0 0 1 .5.5v6a.5.5 0 0 1-1 0V6a.5.5 0 0 1 .5-.5zm3 .5a.5.5 0 0 0-1 0v6a.5.5 0 0 0 1 0V6z"/>
                <path fillRule="evenodd" d="M14.5 3a1 1 0 0 1-1 1H13v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V4h-.5a1 1 0 0 1-1-1V2a1 1 0 0 1 1-1H6a1 1 0 0 1 1-1h2a1 1 0 0 1 1 1h3.5a1 1 0 0 1 1 1v1zM4.118 4 4 4.059V13a1 1 0 0 0 1 1h6a1 1 0 0 0 1-1V4.059L11.882 4H4.118zM2.5 3V2h11v1h-11z"/>
              </svg>
            )}
          </button>
        </div>
      ))}
    </div>
  );
}

export default ConversationList;
