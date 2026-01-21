import { useState, useEffect, useRef, useCallback } from 'react';
import { useParams, useNavigate, useSearchParams } from 'react-router-dom';
import toast, { Toaster } from 'react-hot-toast';
import { ClipboardPlus, Code, Paperclip, PanelRightClose, PanelRightOpen } from 'lucide-react';
import { cn } from '../lib/utils';
import ConversationList from '../components/ConversationList';
import ArtifactsPanel from '../components/ArtifactsPanel';
import AttachmentsPanel from '../components/AttachmentsPanel';
import LayoutFrame from '../components/layout/LayoutFrame';
import ViewPrimaryActions from '../components/layout/view/ViewPrimaryActions';
import {
  AIConversation,
  AIConversationMessages,
  AIConversationEmpty,
  AIMessage,
  AIMessageAvatar,
  AIMessageContent,
  AIMessageActions,
  AIResponse,
  AIActions,
  AIActionButton,
  AILoader,
  AIPromptInput,
  AIPromptInputTextarea,
  AIPromptInputFooter,
  AIPromptInputTools,
  AIPromptInputButton,
  AIPromptInputSubmit,
  AIToolArtifacts,
  AIMessageAttachments,
  useAIConversation,
} from '@zoea/web-components';
import {
  useConversationStore,
  useClipboardStore,
  useWorkspaceStore,
} from '../stores';
import { useShallow } from 'zustand/react/shallow';
import api from '../services/api';

// Helper component to track scroll position within AIConversation context
function ScrollPositionTracker({ conversationId, scrollPositionsRef }) {
  const { getScrollPosition, setScrollPosition } = useAIConversation();
  const lastConversationIdRef = useRef(conversationId);

  // Save scroll position when conversation changes
  useEffect(() => {
    const lastId = lastConversationIdRef.current;
    if (lastId && lastId !== conversationId) {
      // Save position for the previous conversation
      scrollPositionsRef.current.set(lastId, getScrollPosition());
    }
    lastConversationIdRef.current = conversationId;
  }, [conversationId, getScrollPosition, scrollPositionsRef]);

  // Restore scroll position when loading a conversation
  useEffect(() => {
    if (conversationId) {
      const savedPosition = scrollPositionsRef.current.get(conversationId);
      if (savedPosition !== undefined) {
        // Small delay to ensure content is rendered
        requestAnimationFrame(() => {
          setScrollPosition(savedPosition);
        });
      }
    }
  }, [conversationId, setScrollPosition, scrollPositionsRef]);

  return null;
}

function ChatPage() {
  const { conversationId: conversationIdParam } = useParams();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const hasRedirected = useRef(false);
  const clipboardNoticeTimeout = useRef(null);
  const lastUrlConversationIdRef = useRef(conversationIdParam); // Track URL conversation ID changes
  const scrollPositionsRef = useRef(new Map()); // Store scroll positions per conversation

  // Parse conversationId from URL param (string) to number for comparison
  const conversationId = conversationIdParam ? parseInt(conversationIdParam, 10) : null;

  // Parse project and workspace IDs from URL query params, with fallbacks from store
  const projectIdParam = searchParams.get('project') ? parseInt(searchParams.get('project'), 10) : null;
  const workspaceIdParam = searchParams.get('workspace')
    ? parseInt(searchParams.get('workspace'), 10)
    : null;

  const currentProjectId = useWorkspaceStore((state) => state.currentProjectId);
  const currentWorkspaceId = useWorkspaceStore((state) => state.currentWorkspaceId);
  const workspaces = useWorkspaceStore((state) => state.workspaces);

  // Use URL params if available, otherwise fall back to store values
  const projectId = projectIdParam || currentProjectId;

  // Only use the workspace if it belongs to the current project's workspaces list
  const isValidWorkspace = (wsId) => wsId && workspaces.some(w => w.id === wsId);
  const workspaceId = workspaceIdParam || (isValidWorkspace(currentWorkspaceId) ? currentWorkspaceId : null);
  const activeWorkspaceId = workspaceId;

  // Conversation store selectors - use individual primitive selectors for better stability
  const messages = useConversationStore((state) => state.messages);
  const conversations = useConversationStore((state) => state.conversations);
  const conversationLoading = useConversationStore((state) => state.loading);
  const hasLoadedConversations = useConversationStore((state) => state.hasLoadedConversations);
  const currentConversationId = useConversationStore((state) => state.currentConversationId);
  const currentConversation = useConversationStore((state) => {
    const { conversations, currentConversationId: activeId } = state;
    if (!activeId) return null;
    return conversations.find((conv) => conv.id === activeId) || null;
  });
  const addMessage = useConversationStore((state) => state.addMessage);
  const updateCurrentConversationId = useConversationStore(
    (state) => state.updateCurrentConversationId
  );
  const refreshConversations = useConversationStore((state) => state.refreshConversations);
  const selectConversation = useConversationStore((state) => state.selectConversation);

  const addMessageToClipboard = useClipboardStore((state) => state.addMessageToClipboard);
  const clipboard = useClipboardStore((state) => state.clipboard);
  const loadClipboardsForWorkspace = useClipboardStore((state) => state.loadClipboardsForWorkspace);
  const createNewConversation = useConversationStore((state) => state.createNewConversation);
  const emailThreadId = useConversationStore((state) => state.emailThreadId);

  // Local state
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [clipboardNotice, setClipboardNotice] = useState(null);
  const [clipboardAttachments, setClipboardAttachments] = useState([]);
  const [showArtifacts, setShowArtifacts] = useState(false);
  const [showAttachments, setShowAttachments] = useState(false);
  const [artifactsRefreshKey, setArtifactsRefreshKey] = useState(0);
  const [attachmentsRefreshKey, setAttachmentsRefreshKey] = useState(0);

  // If navigating to /chat without an ID, redirect to current conversation if one exists
  // UNLESS we just navigated away from a conversation (e.g., clicked "New Chat")
  useEffect(() => {
    const lastUrlId = lastUrlConversationIdRef.current;
    const justNavigatedAwayFromConversation = lastUrlId && !conversationIdParam;

    if (!conversationId && currentConversationId && !hasRedirected.current && !justNavigatedAwayFromConversation) {
      // We're at /chat but there's a persisted current conversation
      // Redirect to show it (only once)
      hasRedirected.current = true;
      navigate(`/chat/${currentConversationId}`, { replace: true });
    }

    // Update the last URL conversation ID only if we have a conversation ID
    // This preserves the "came from" state when navigating to /chat
    if (conversationIdParam) {
      lastUrlConversationIdRef.current = conversationIdParam;
    }
  }, [conversationId, conversationIdParam, currentConversationId, navigate]);

  // Sync URL param with conversation context
  const syncConversation = useCallback(async () => {
    console.log('[ChatPage] syncConversation called:', {
      conversationId,
      currentConversationId,
      messagesLength: messages.length,
      conversationsCount: conversations.length,
      hasLoadedConversations
    });

    // Only sync if there's a conversationId in the URL
    // The first useEffect handles the redirect case when !conversationId && currentConversationId

    // Only check project membership if conversations have been loaded
    // This prevents blocking conversation load on initial page load when conversations list is empty
    if (conversationId && hasLoadedConversations && conversations.length > 0) {
      const conversationExistsInProject = conversations.some(c => c.id === conversationId);
      console.log('[ChatPage] Project membership check:', { conversationExistsInProject, conversationId });
      if (!conversationExistsInProject) {
        // Conversation doesn't belong to current project, don't load it
        console.log('[ChatPage] Conversation not in project, returning early');
        return;
      }
    }

    // Load conversation if:
    // 1. The URL conversationId differs from the current one, OR
    // 2. The URL conversationId matches but messages are empty (needs hydration after reload/deep-link)
    if (conversationId && (conversationId !== currentConversationId || messages.length === 0)) {
      console.log('[ChatPage] Calling selectConversation for:', conversationId);
      await selectConversation(conversationId);
      console.log('[ChatPage] selectConversation completed');
    }
  }, [conversationId, currentConversationId, selectConversation, messages.length, conversations, hasLoadedConversations]);

  useEffect(() => {
    syncConversation();
  }, [syncConversation]);

  // Clear conversation state when at /chat with no ID (new conversation mode)
  useEffect(() => {
    if (!conversationId && (currentConversationId !== null || messages.length > 0)) {
      // We're at /chat with no ID, but store still has conversation data
      // This happens when persist middleware restores old state
      // Explicitly clear it to show new conversation UI
      selectConversation(null);
    }
  }, [conversationId, currentConversationId, messages.length, selectConversation]);

  // Redirect when workspace changes and conversation needs to switch
  useEffect(() => {
    // Check if the URL conversation exists in the current workspace's list
    const conversationExistsInProject = conversationId && conversations.some(c => c.id === conversationId);

    console.log('[ChatPage] Redirect effect check:', {
      conversationId,
      currentConversationId,
      messagesLength: messages.length,
      conversationLoading,
      hasLoadedConversations,
      conversationExistsInProject
    });

    // Case 1: URL has conversation that doesn't belong to current workspace
    // Redirect to restored conversation or /chat
    if (
      conversationId &&
      messages.length === 0 &&
      !conversationLoading &&
      hasLoadedConversations &&
      !conversationExistsInProject
    ) {
      // URL conversation doesn't exist in current workspace
      if (currentConversationId) {
        // A conversation was restored for this workspace - navigate to it
        console.log('[ChatPage] REDIRECTING to restored conversation:', currentConversationId);
        navigate(`/chat/${currentConversationId}`, { replace: true });
      } else {
        // No restored conversation - go to clean /chat
        console.log('[ChatPage] REDIRECTING to /chat - conversation not in project');
        navigate('/chat', { replace: true });
      }
    }

    // Case 2: At /chat but store has a restored conversation for this workspace
    // (This handles workspace switch when already at /chat)
    // Don't redirect if user just clicked "New Chat" (justNavigatedAwayFromConversation)
    const lastUrlId = lastUrlConversationIdRef.current;
    const justNavigatedAway = lastUrlId && !conversationIdParam;
    if (
      !conversationId &&
      currentConversationId &&
      hasLoadedConversations &&
      !conversationLoading &&
      !justNavigatedAway &&
      conversations.some(c => c.id === currentConversationId)
    ) {
      console.log('[ChatPage] REDIRECTING to current conversation:', currentConversationId);
      navigate(`/chat/${currentConversationId}`, { replace: true });
    }
  }, [conversationId, conversationIdParam, currentConversationId, messages.length, navigate, conversationLoading, hasLoadedConversations, conversations]);

  // Build conversation history from messages
  const buildConversationHistory = (messages) => {
    return messages
      .map((msg) => {
        const prefix = msg.role === 'user' ? 'User: ' : 'Assistant: ';
        return prefix + msg.content;
      })
      .join('\n\n');
  };

  const CLIPBOARD_TOKEN = '[Clipboard]';

  const insertContext = async () => {
    if (!clipboard) {
      toast.error('No active notebook. Please select or create one.');
      return;
    }

    // Ensure we have clipboard data loaded (for attachments display)
    if (activeWorkspaceId) {
      await loadClipboardsForWorkspace(activeWorkspaceId);
    }

    try {
      const items = await api.fetchClipboardItems(clipboard.id);
      const attachments =
        items.items
          ?.filter((item) => item.preview?.url && item.content_type === 'documents.document')
          .map((item) => ({
            id: item.id,
            url: item.preview.url,
            name: item.source_metadata?.document_name || 'Attachment',
          })) || [];
      setClipboardAttachments(attachments);
    } catch (err) {
      console.error('Failed to load clipboard items for attachments', err);
      setClipboardAttachments([]);
    }

    // Insert clipboard token at the end of the current input
    const tokenToInsert = CLIPBOARD_TOKEN;
    const newValue = input ? `${input} ${tokenToInsert}` : tokenToInsert;
    setInput(newValue);

    toast.success('Notebook placeholder inserted');
  };

  const sendMessage = async (messageText) => {
    const textToSend = messageText || input;
    if (!textToSend.trim()) return;

    const userMessage = { role: 'user', content: textToSend };
    addMessage(userMessage);

    const currentInput = textToSend;
    setInput('');
    setClipboardAttachments([]);
    setLoading(true);
    setError(null);

    try {
      // Build conversation history including the new message
      const updatedMessages = [...messages, userMessage];
      const conversationHistory = buildConversationHistory(updatedMessages);

      const includesClipboard = currentInput.includes(CLIPBOARD_TOKEN) && clipboard;

      // Send message with conversation_id, project_id, and workspace_id if we have them
      // Only send workspace_id for NEW conversations - existing conversations already have a workspace
      const data = await api.sendMessage({
        message: currentInput,
        agent_name: 'ZoeaAssistant',
        instructions: 'You are a helpful AI assistant for Zoea Studio.',
        conversation_id: currentConversationId,
        project_id: projectId,
        workspace_id: currentConversationId ? null : activeWorkspaceId,
        conversation_history: conversationHistory,
        clipboard_id: includesClipboard ? clipboard?.id : null,
      });

      // Update conversation_id if this was a new conversation
      if (!currentConversationId && data.conversation_id) {
        updateCurrentConversationId(data.conversation_id);
        // Refresh conversation list to show the new conversation
        await refreshConversations();
        // Navigate to the new conversation URL
        navigate(`/chat/${data.conversation_id}`);
      } else if (currentConversationId) {
        // Refresh conversation list to update the timestamp for existing conversation
        await refreshConversations();
      }

      // Add assistant response to messages (including any tool artifacts)
      const assistantMessage = {
        role: 'assistant',
        content: data.response,
        tool_artifacts: data.tool_artifacts || null,
      };
      addMessage(assistantMessage);

      // Trigger artifacts panel refresh if new artifacts were generated
      if (data.tool_artifacts && data.tool_artifacts.length > 0) {
        setArtifactsRefreshKey((prev) => prev + 1);
      }
    } catch (err) {
      console.error('Error sending message:', err);
      setError(err.message || 'Failed to send message. Please try again.');

      const errorMessage = {
        role: 'error',
        content: err.message || 'Failed to send message. Please try again.',
      };
      addMessage(errorMessage);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    return () => {
      if (clipboardNoticeTimeout.current) {
        clearTimeout(clipboardNoticeTimeout.current);
      }
    };
  }, []);

  const handleAddToClipboard = async (message) => {
    if (!activeWorkspaceId) {
      toast.error('Select a workspace before saving items to your notebook.');
      return;
    }

    try {
      // Create preview data for chat bubble visualization
      const preview = {
        type: 'chat_bubble',
        metadata: {
          role: message.role,
          text_snippet: message.content,
        },
      };

      await addMessageToClipboard({
        workspaceId: activeWorkspaceId,
        text: message.content,
        preview,
        metadata: {
          conversation_id: currentConversationId,
          role: message.role,
          added_at: new Date().toISOString(),
        },
      });

      toast.success('Added to notebook');
    } catch (clipError) {
      console.error('Failed to add clipboard item', clipError);
      toast.error(clipError.message || 'Failed to add item to notebook.');
    }
  };

  const sidebarContent = <ConversationList />;

  const headerActions = (
    <ViewPrimaryActions>
      <ViewPrimaryActions.Button
        variant="outline"
        title={showArtifacts ? 'Hide artifacts panel' : 'Show artifacts panel'}
        onClick={() => setShowArtifacts(!showArtifacts)}
      >
        {showArtifacts ? <PanelRightClose size={16} /> : <Code size={16} />}
        <span className="ml-1.5">Artifacts</span>
      </ViewPrimaryActions.Button>
      {emailThreadId && (
        <ViewPrimaryActions.Button
          variant="outline"
          title={showAttachments ? 'Hide attachments panel' : 'Show attachments panel'}
          onClick={() => setShowAttachments(!showAttachments)}
        >
          {showAttachments ? <PanelRightClose size={16} /> : <Paperclip size={16} />}
          <span className="ml-1.5">Attachments</span>
        </ViewPrimaryActions.Button>
      )}
      <ViewPrimaryActions.Button
        variant="outline"
        title="View all conversations"
        onClick={() => navigate('/conversations')}
      >
        All Conversations
      </ViewPrimaryActions.Button>
      <ViewPrimaryActions.Button
        variant="outline"
        title="Start new conversation"
        onClick={() => {
          hasRedirected.current = false; // Reset redirect flag to allow future redirects
          createNewConversation();
          navigate('/chat');
        }}
      >
        New Chat
      </ViewPrimaryActions.Button>
    </ViewPrimaryActions>
  );

  const hasSidePanel = showArtifacts || (showAttachments && emailThreadId);

  return (
    <LayoutFrame
      title={currentConversation?.title || 'Chat'}
      actions={headerActions}
      variant="full"
      sidebar={sidebarContent}
      viewSidebarTitle="Recents"
      noPadding
      hideHeader={!conversationId}
    >
      <div className={cn(
        "flex h-full w-full",
        !hasSidePanel && "justify-center"
      )}>
        {/* Main chat area - constrained to max-w-4xl, centered when no panels */}
        <div className="flex flex-col h-full w-full max-w-4xl min-w-0">
          <Toaster position="top-right" />

          {/* Error banner */}
          {error && (
            <div className="mx-4 mt-4 p-3 rounded-lg bg-destructive/10 border border-destructive/20 text-destructive flex items-center justify-between" role="alert">
              <span className="text-sm">{error}</span>
              <button
                type="button"
                className="ml-4 hover:opacity-70"
                onClick={() => setError(null)}
                aria-label="Close"
              >
                <svg className="h-4 w-4" fill="currentColor" viewBox="0 0 20 20"><path fillRule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clipRule="evenodd"/></svg>
              </button>
            </div>
          )}

          {/* Main conversation area */}
          <AIConversation className="flex-1 min-h-0">
          <ScrollPositionTracker
            conversationId={currentConversationId}
            scrollPositionsRef={scrollPositionsRef}
          />
          {messages.length === 0 ? (
            <AIConversationEmpty className="h-full">
              <img src="/zoea-logo.png" alt="Zoea Studio" className="w-24 h-24 mb-6 opacity-80" />
              <h2 className="text-2xl font-semibold text-foreground mb-2">Welcome to Zoea Studio!</h2>
              <p className="text-muted-foreground">Start a conversation with the AI assistant below.</p>
            </AIConversationEmpty>
          ) : (
            <AIConversationMessages className="max-w-4xl mx-auto">
              {messages.map((message) => (
                <AIMessage
                  key={message.id ?? `${message.role}-${message.content.substring(0, 20)}`}
                  from={message.role}
                >
                  <AIMessageAvatar
                    fallback={message.role === 'user' ? 'U' : message.role === 'error' ? '!' : 'AI'}
                  />
                  <AIMessageContent>
                    {/* Display email attachments as thumbnails above message content */}
                    {message.attachments && message.attachments.length > 0 && (
                      <AIMessageAttachments attachments={message.attachments} />
                    )}
                    <AIResponse>{message.content}</AIResponse>
                    {/* Display tool-generated artifacts (images, etc.) */}
                    {message.tool_artifacts && message.tool_artifacts.length > 0 && (
                      <AIToolArtifacts
                        artifacts={message.tool_artifacts}
                        workspaceId={activeWorkspaceId}
                        onArtifactSaved={(artifact, result) => {
                          toast.success(`Saved "${result.document?.name || 'artifact'}" to library`);
                        }}
                      />
                    )}
                  </AIMessageContent>
                  {message.role !== 'error' && (
                    <AIMessageActions>
                      <AIActions
                        className="bg-card border border-border rounded-lg shadow-sm px-1"
                        content={message.content}
                        onCopy={() => toast.success('Copied to clipboard')}
                        onCopyError={() => toast.error('Failed to copy to clipboard')}
                      >
                        <AIActionButton
                          onClick={() => handleAddToClipboard(message)}
                          tooltip="Add to Notebook"
                        >
                          <ClipboardPlus className="h-4 w-4" />
                        </AIActionButton>
                      </AIActions>
                    </AIMessageActions>
                  )}
                </AIMessage>
              ))}

              {/* Loading indicator */}
              {loading && (
                <AIMessage from="assistant">
                  <AIMessageAvatar fallback="AI" />
                  <AIMessageContent>
                    <AILoader variant="dots" text="Thinking" />
                  </AIMessageContent>
                </AIMessage>
              )}
            </AIConversationMessages>
          )}
        </AIConversation>

        {/* Input area */}
        <div className="flex-shrink-0 border-t border-border bg-background p-4">
          <div className="max-w-4xl mx-auto">
            <AIPromptInput
              value={input}
              onValueChange={setInput}
              onSubmit={sendMessage}
              isSubmitting={loading}
            >
              <AIPromptInputTextarea
                placeholder="Type your message..."
                minRows={1}
                maxRows={6}
              />
              <AIPromptInputFooter>
                <AIPromptInputTools>
                  <AIPromptInputButton
                    onClick={insertContext}
                    disabled={!clipboard || !activeWorkspaceId}
                    title={
                      !activeWorkspaceId
                        ? 'Select a workspace first'
                        : !clipboard
                        ? 'No active notebook'
                        : 'Insert Notebook placeholder'
                    }
                  >
                    <ClipboardPlus className="h-4 w-4 mr-1" />
                    Insert Notebook
                  </AIPromptInputButton>
                </AIPromptInputTools>
                <AIPromptInputSubmit />
              </AIPromptInputFooter>
            </AIPromptInput>

            {/* Notebook attachments preview */}
            {clipboardAttachments.length > 0 && (
              <div className="mt-3 p-3 rounded-lg bg-muted/50 border border-border">
                <div className="text-xs text-muted-foreground mb-2">Notebook attachments</div>
                <div className="flex gap-2 flex-wrap">
                  {clipboardAttachments.map((att) => (
                    <div
                      key={att.id}
                      className="flex items-center gap-2 px-2 py-1 rounded-md bg-background border border-border text-xs"
                    >
                      <img src={att.url} alt={att.name} className="w-6 h-6 rounded object-cover" />
                      <span className="text-foreground">{att.name}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
        </div>

        {/* Artifacts panel - takes remaining horizontal space */}
        {showArtifacts && (
          <div className="flex-1 min-w-80 max-w-2xl border-l border-border">
            <ArtifactsPanel conversationId={currentConversationId} refreshKey={artifactsRefreshKey} />
          </div>
        )}

        {/* Email attachments panel - takes remaining horizontal space */}
        {showAttachments && emailThreadId && (
          <div className="flex-1 min-w-80 max-w-2xl border-l border-border">
            <AttachmentsPanel emailThreadId={emailThreadId} refreshKey={attachmentsRefreshKey} />
          </div>
        )}
      </div>
    </LayoutFrame>
  );
}

export default ChatPage;
