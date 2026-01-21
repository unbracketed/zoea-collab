/**
 * Conversation Header Component
 *
 * Displays the current conversation title and metadata.
 */

import { useNavigate } from 'react-router-dom';
import { useConversationStore } from '../stores';

function ConversationHeader() {
  const navigate = useNavigate();
  const createNewConversation = useConversationStore((state) => state.createNewConversation);

  // Subscribe to the derived conversation directly so the component re-renders when conversations load
  const currentConversation = useConversationStore((state) => {
    const { conversations, currentConversationId } = state;
    if (!currentConversationId) return null;
    return conversations.find((conv) => conv.id === currentConversationId) || null;
  });

  const handleNewChat = () => {
    createNewConversation();
    navigate('/chat');
  };

  return (
    <div className="conversation-header">
      <div className="flex justify-between items-center">
        <div className="conversation-info">
          {currentConversation ? (
            <>
              <h5 className="mb-0 text-lg font-medium">{currentConversation.title}</h5>
              <small className="text-text-secondary">
                {currentConversation.message_count} message
                {currentConversation.message_count !== 1 ? 's' : ''}
                {' • '}
                {currentConversation.agent_name}
              </small>
            </>
          ) : (
            <>
              <h5 className="mb-0 text-lg font-medium">New Conversation</h5>
              <small className="text-text-secondary">Start chatting with ZoeaAssistant</small>
            </>
          )}
        </div>

        <button
          className="px-3 py-1 text-sm border border-primary text-primary rounded hover:bg-primary hover:text-white transition-colors"
          onClick={handleNewChat}
          title="Start new conversation"
        >
          <i className="bi bi-plus-lg"></i> New Chat
        </button>
      </div>
    </div>
  );
}

export default ConversationHeader;
