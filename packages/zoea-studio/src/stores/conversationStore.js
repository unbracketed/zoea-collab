/**
 * Conversation Store
 *
 * Manages conversation state including list of conversations,
 * current conversation, and messages.
 * Uses persist middleware to save currentConversationId to localStorage.
 * Implements race condition protection for rapid conversation switching.
 */

import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import api from '../services/api';

const generateMessageId = () => `msg_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 8)}`;
const withMessageId = (message) => ({
  id: message.id ?? generateMessageId(),
  role: message.role,
  content: message.content,
  // Preserve tool artifacts for assistant messages (Issue #107)
  ...(message.tool_artifacts ? { tool_artifacts: message.tool_artifacts } : {}),
  // Preserve email attachments for email-originated messages
  ...(message.attachments ? { attachments: message.attachments } : {}),
});
const buildContextFilter = (project_id, workspace_id) => ({
  project_id: project_id ?? null,
  workspace_id: workspace_id ?? null,
});
const isSameContext = (a, b) => a && b && a.project_id === b.project_id && a.workspace_id === b.workspace_id;

export const useConversationStore = create(
  persist(
    (set, get) => ({
      // State
      conversations: [], // Array of conversation metadata
      currentConversationId: null, // Active conversation ID
      perWorkspaceConversations: {}, // Map of workspace ID -> conversation ID (remembers current conversation per workspace)
      messages: [], // Messages for current conversation ONLY
      emailThreadId: null, // Email thread ID if conversation originated from email
      loading: false,
      error: null,
      latestSelectCallId: 0, // Race condition counter
      hasLoadedConversations: false, // Track if conversations have been loaded (survives StrictMode remounts)
      scrollPositions: {}, // Store scroll positions per conversation ID
      lastConversationsFilter: null, // Track last project/workspace context

      // Actions

      /**
       * Fetch all conversations from API
       * Optionally filter by project and workspace
       * Only loads once per session using hasLoadedConversations flag (unless force=true)
       *
       * @param {Object} params
       * @param {number} [params.project_id] - Filter by project ID
       * @param {number} [params.workspace_id] - Filter by workspace ID
       * @param {boolean} [params.force=false] - Force reload even if already loaded
       */
      loadConversations: async ({ project_id = null, workspace_id = null, force = false } = {}) => {
        // Prevent duplicate loads (important for StrictMode double-mounting)
        const requestedFilter = buildContextFilter(project_id, workspace_id);
        const lastFilter = get().lastConversationsFilter;
        if (get().hasLoadedConversations && !force && isSameContext(lastFilter, requestedFilter)) {
          return;
        }

        try {
          set({ loading: true, error: null, hasLoadedConversations: true });
          const data = await api.fetchConversations({ project_id, workspace_id });
          const newConversations = data.conversations || [];

          // Check if current conversation is in the new list
          // If not (e.g., switched projects/workspaces), save it for the old workspace and restore for new
          const currentId = get().currentConversationId;
          const currentInNewList = currentId && newConversations.some(c => c.id === currentId);
          const oldWorkspaceId = lastFilter?.workspace_id;
          const perWorkspaceConversations = { ...get().perWorkspaceConversations };

          // Save current conversation for the old workspace before switching
          if (currentId && oldWorkspaceId && oldWorkspaceId !== workspace_id) {
            perWorkspaceConversations[oldWorkspaceId] = currentId;
          }

          // Determine the conversation to show for the new workspace
          let newCurrentConversationId = currentId;
          let shouldClearMessages = false;

          if (currentId && !currentInNewList) {
            // Current conversation doesn't belong to new workspace
            // Try to restore the saved conversation for this workspace
            const savedConversationId = workspace_id ? perWorkspaceConversations[workspace_id] : null;
            const savedInNewList = savedConversationId && newConversations.some(c => c.id === savedConversationId);

            newCurrentConversationId = savedInNewList ? savedConversationId : null;
            shouldClearMessages = true;
          }

          set({
            conversations: newConversations,
            lastConversationsFilter: requestedFilter,
            perWorkspaceConversations,
            ...(shouldClearMessages ? {
              currentConversationId: newCurrentConversationId,
              messages: [],
              emailThreadId: null
            } : {}),
          });
        } catch (err) {
          console.error('Failed to load conversations:', err);
          set({
            error: err.message,
            hasLoadedConversations: false,
            lastConversationsFilter: null,
          }); // Reset on error
        } finally {
          set({ loading: false });
        }
      },

      /**
       * Select a conversation by ID and load its messages
       * Also sets it as the current conversation
       * Includes race condition protection for rapid conversation switching
       */
      selectConversation: async (conversationId) => {
        // Assign a unique ID to this call to track if it's still the latest
        const callId = get().latestSelectCallId + 1;
        set({ latestSelectCallId: callId });

        if (!conversationId) {
          // Only update if this is still the latest call
          if (get().latestSelectCallId === callId) {
            set({ currentConversationId: null, messages: [], emailThreadId: null });
          }
          return;
        }

        try {
          set({ loading: true, error: null });

          // Fetch conversation details with messages
          const conversationData = await api.fetchConversation(conversationId);

          // Only update state if this is still the latest request
          if (get().latestSelectCallId === callId) {
            // Convert backend message format to frontend format
            // Preserve tool_artifacts for inline image/artifact display
            // Preserve attachments for email-originated messages
            const formattedMessages = conversationData.messages.map((msg) =>
              withMessageId({
                id: msg.id,
                role: msg.role,
                content: msg.content,
                tool_artifacts: msg.tool_artifacts,
                attachments: msg.attachments,
              })
            );

            set({
              currentConversationId: conversationId,
              messages: formattedMessages,
              emailThreadId: conversationData.email_thread_id || null,
            });
          }
        } catch (err) {
          console.error('Failed to load conversation:', err);
          // Only update error state if this is still the latest call
          if (get().latestSelectCallId === callId) {
            set({
              error: err.message,
              currentConversationId: null,
              messages: [],
              emailThreadId: null,
            });
          }
        } finally {
          // Only update loading state if this is still the latest call
          if (get().latestSelectCallId === callId) {
            set({ loading: false });
          }
        }
      },

      /**
       * Create a new conversation
       * Clears the current conversation and removes persistence
       * so user can start fresh
       */
      createNewConversation: () => {
        set({
          currentConversationId: null,
          messages: [],
          emailThreadId: null,
        });

        // Immediately update localStorage to prevent persist middleware from restoring old value
        // This ensures the null value is persisted synchronously
        try {
          const storageKey = 'zoea-conversation';
          const stored = localStorage.getItem(storageKey);
          if (stored) {
            const parsed = JSON.parse(stored);
            if (parsed.state) {
              parsed.state.currentConversationId = null;
              localStorage.setItem(storageKey, JSON.stringify(parsed));
            }
          }
        } catch (e) {
          console.error('Failed to clear persisted conversation ID:', e);
        }
      },

      /**
       * Add a message to the current conversation
       */
      addMessage: (message) => {
        set((state) => ({
          messages: [...state.messages, withMessageId(message)],
        }));
      },

      /**
       * Set multiple messages at once
       */
      setMessagesForConversation: (newMessages) => {
        set({ messages: newMessages.map(withMessageId) });
      },

      /**
       * Update current conversation ID after creating new conversation
       * Also persists it as the "current" conversation
       */
      updateCurrentConversationId: (conversationId) => {
        set({ currentConversationId: conversationId });
      },

      /**
       * Update conversations list when a new conversation is created
       */
      addConversationToList: (conversation) => {
        set((state) => ({
          conversations: [conversation, ...state.conversations],
        }));
      },

      /**
       * Refresh conversation list
       * Forces a reload of conversations
       */
      refreshConversations: async () => {
        const filter = get().lastConversationsFilter || { project_id: null, workspace_id: null };
        await get().loadConversations({ ...filter, force: true });
      },

      /**
       * Delete a conversation
       * Removes it from the list and clears current conversation if it was selected
       * @param {number} conversationId - ID of the conversation to delete
       */
      deleteConversation: async (conversationId) => {
        try {
          await api.deleteConversation(conversationId);

          // Remove from conversations list
          set((state) => ({
            conversations: state.conversations.filter((c) => c.id !== conversationId),
            // Clear current conversation if it was the deleted one
            ...(state.currentConversationId === conversationId
              ? { currentConversationId: null, messages: [], emailThreadId: null }
              : {}),
          }));

          return true;
        } catch (err) {
          console.error('Failed to delete conversation:', err);
          throw err;
        }
      },

      /**
       * Get current conversation from list
       * Returns the full conversation object or null
       */
      getCurrentConversation: () => {
        const { conversations, currentConversationId } = get();
        if (!currentConversationId) return null;
        return conversations.find((conv) => conv.id === currentConversationId) || null;
      },

      /**
       * Save scroll position for a conversation
       * @param {number} conversationId - Conversation ID
       * @param {Object} position - { scrollTop: number, shouldAutoScroll: boolean }
       */
      saveScrollPosition: (conversationId, position) => {
        set((state) => ({
          scrollPositions: {
            ...state.scrollPositions,
            [conversationId]: position,
          },
        }));
      },

      /**
       * Get saved scroll position for a conversation
       * @param {number} conversationId - Conversation ID
       * @returns {Object|null} - Saved position or null
       */
      getScrollPosition: (conversationId) => {
        const { scrollPositions } = get();
        return scrollPositions[conversationId] || null;
      },
    }),
    {
      name: 'zoea-conversation', // localStorage key
      partialize: (state) => ({
        // Persist currentConversationId, perWorkspaceConversations, and scrollPositions
        // conversations and messages are fetched from API
        currentConversationId: state.currentConversationId,
        perWorkspaceConversations: state.perWorkspaceConversations,
        scrollPositions: state.scrollPositions,
      }),
    }
  )
);
