/**
 * Session Store
 *
 * Persists the user's last session state (route, project, workspace)
 * so they can return to where they left off.
 * Uses Zustand persist middleware to save to localStorage.
 */

import { create } from 'zustand';
import { persist } from 'zustand/middleware';

export const useSessionStore = create(
  persist(
    (set, get) => ({
      // State - last known session
      lastPath: null,           // e.g., '/chat/123', '/documents', '/canvas'
      lastProjectId: null,
      lastWorkspaceId: null,
      lastConversationId: null, // For chat page specifically

      // Per-project route state: { [projectId]: { path, workspaceId } }
      projectRoutes: {},

      // Actions
      /**
       * Save current session state
       * Call this when navigating or when project/workspace changes
       */
      saveSession: ({ path, projectId, workspaceId, conversationId } = {}) => {
        const updates = {};

        if (path !== undefined) {
          updates.lastPath = path;
        }
        if (projectId !== undefined) {
          updates.lastProjectId = projectId;
        }
        if (workspaceId !== undefined) {
          updates.lastWorkspaceId = workspaceId;
        }
        if (conversationId !== undefined) {
          updates.lastConversationId = conversationId;
        }

        if (Object.keys(updates).length > 0) {
          set(updates);
        }
      },

      /**
       * Save route state for a specific project
       * Call this before switching away from a project
       */
      saveProjectRoute: (projectId, { path, workspaceId }) => {
        if (!projectId) return;
        set((state) => ({
          projectRoutes: {
            ...state.projectRoutes,
            [projectId]: { path, workspaceId },
          },
        }));
      },

      /**
       * Get saved route state for a project
       * Returns null if no saved state exists
       */
      getProjectRoute: (projectId) => {
        if (!projectId) return null;
        return get().projectRoutes[projectId] || null;
      },

      /**
       * Get the full session state for restoration
       */
      getSession: () => {
        const { lastPath, lastProjectId, lastWorkspaceId, lastConversationId } = get();
        return { lastPath, lastProjectId, lastWorkspaceId, lastConversationId };
      },

      /**
       * Clear session (useful for logout)
       */
      clearSession: () => {
        set({
          lastPath: null,
          lastProjectId: null,
          lastWorkspaceId: null,
          lastConversationId: null,
          projectRoutes: {},
        });
      },
    }),
    {
      name: 'zoea-session', // localStorage key
      // Only persist the session state, not any derived state
      partialize: (state) => ({
        lastPath: state.lastPath,
        lastProjectId: state.lastProjectId,
        lastWorkspaceId: state.lastWorkspaceId,
        lastConversationId: state.lastConversationId,
        projectRoutes: state.projectRoutes,
      }),
    }
  )
);
