/**
 * RAG Store
 *
 * Manages Document RAG chat sessions.
 */

import { create } from 'zustand';
import ragApi from '../services/ragApi';

const initialState = {
  session: null,
  messages: [],
  sources: [],
  isLoading: false,
  isStreaming: false,
  error: null,
};

export const useRAGStore = create((set, get) => ({
  ...initialState,

  /**
   * Reset the store to initial state.
   */
  reset: () => set(initialState),

  /**
   * Create a new RAG session.
   *
   * @param {Object} params - Session parameters
   * @param {string} params.contextType - Type: 'single', 'folder', 'clipboard', 'collection'
   * @param {number} params.contextId - ID of the context item
   * @param {number} params.projectId - Project ID
   * @param {number} params.workspaceId - Workspace ID
   * @returns {Promise<Object>} Created session
   */
  createSession: async ({ contextType, contextId, projectId, workspaceId }) => {
    set({ isLoading: true, error: null });
    try {
      const session = await ragApi.createSession({
        context_type: contextType,
        context_id: contextId,
        project_id: projectId,
        workspace_id: workspaceId,
        reuse_existing: true,
      });

      // If reusing existing session, load its messages
      if (session.status === 'active') {
        try {
          const sessionData = await ragApi.getSession(session.session_id);
          const messages = (sessionData.messages || []).map((msg) => ({
            id: msg.id,
            role: msg.role,
            content: msg.content,
            timestamp: msg.created_at,
            sources: msg.sources || [],
            thinkingSteps: msg.thinking_steps || [],
          }));
          set({ session, isLoading: false, messages, sources: [] });
        } catch {
          // If loading messages fails, just use empty messages
          set({ session, isLoading: false, messages: [], sources: [] });
        }
      } else {
        set({ session, isLoading: false, messages: [], sources: [] });
      }

      return session;
    } catch (error) {
      console.error('Failed to create RAG session', error);
      set({ error: error.message, isLoading: false });
      throw error;
    }
  },

  /**
   * Send a message to the RAG agent.
   *
   * @param {string} message - User's message
   * @returns {Promise<Object>} Agent response
   */
  sendMessage: async (message) => {
    const { session, messages } = get();
    if (!session) {
      throw new Error('No active session');
    }

    // Add user message to state
    const userMessage = {
      id: Date.now(),
      role: 'user',
      content: message,
      timestamp: new Date().toISOString(),
      sources: [],
      thinkingSteps: [],
    };

    set({
      messages: [...messages, userMessage],
      isStreaming: true,
      error: null,
    });

    try {
      const response = await ragApi.chat(session.session_id, {
        message,
        include_sources: true,
      });

      // Add assistant message to state
      const assistantMessage = {
        id: response.message_id,
        role: 'assistant',
        content: response.response,
        timestamp: new Date().toISOString(),
        sources: response.sources || [],
        thinkingSteps: response.thinking_steps || [],
      };

      set((state) => ({
        messages: [...state.messages, assistantMessage],
        sources: response.sources || [],
        isStreaming: false,
      }));

      return response;
    } catch (error) {
      console.error('Failed to send message', error);
      set({ error: error.message, isStreaming: false });
      throw error;
    }
  },

  /**
   * Close the current session and cleanup.
   */
  closeSession: async () => {
    const { session } = get();
    if (session) {
      try {
        await ragApi.closeSession(session.session_id);
      } catch (error) {
        console.error('Failed to close session', error);
        // Continue with cleanup even if API call fails
      }
    }
    set(initialState);
  },

  /**
   * Load an existing session with its messages.
   *
   * @param {string} sessionId - Session ID to load
   * @returns {Promise<Object>} Session with messages
   */
  loadSession: async (sessionId) => {
    set({ isLoading: true, error: null });
    try {
      const sessionData = await ragApi.getSession(sessionId);
      set({
        session: {
          session_id: sessionData.session_id,
          status: sessionData.status,
          document_count: sessionData.document_count,
          context_type: sessionData.context_type,
          context_display: sessionData.context_display,
          created_at: sessionData.created_at,
        },
        messages: sessionData.messages.map((msg) => ({
          id: msg.id,
          role: msg.role,
          content: msg.content,
          timestamp: msg.created_at,
          sources: msg.sources || [],
          thinkingSteps: msg.thinking_steps || [],
        })),
        isLoading: false,
      });
      return sessionData;
    } catch (error) {
      console.error('Failed to load session', error);
      set({ error: error.message, isLoading: false });
      throw error;
    }
  },
}));
