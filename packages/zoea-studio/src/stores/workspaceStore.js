/**
 * Workspace Store
 *
 * Manages current project and workspace selection.
 * Session state (project/workspace/route) is persisted via sessionStore.
 * URL params take precedence for deep linking and shareable URLs.
 */

import { create } from 'zustand';
import api from '../services/api';

export const useWorkspaceStore = create((set, get) => ({
  // State
  currentProjectId: null,
  currentWorkspaceId: null,
  projects: [],
  workspaces: [],
  loading: false,
  error: null,

  // Actions
  setCurrentProject: (projectId) => {
    set({ currentProjectId: projectId });
  },

  setCurrentWorkspace: (workspaceId) => {
    set({ currentWorkspaceId: workspaceId });
  },

  /**
   * Load all projects for the current user's organization
   */
  loadProjects: async () => {
    set({ loading: true, error: null });
    try {
      const data = await api.fetchProjects();
      set({
        projects: data.projects || [],
        loading: false
      });

      // Auto-select first project if none selected and projects exist
      if (!get().currentProjectId && data.projects && data.projects.length > 0) {
        const firstProject = data.projects[0];
        set({ currentProjectId: firstProject.id });

        // Also load workspaces for the first project
        await get().loadWorkspaces(firstProject.id);
      }
    } catch (err) {
      console.error('Failed to load projects:', err);
      set({ error: err.message, loading: false });
    }
  },

  /**
   * Load workspaces for a specific project
   */
  loadWorkspaces: async (projectId) => {
    if (!projectId) {
      set({ workspaces: [] });
      return;
    }

    set({ loading: true, error: null });
    try {
      const data = await api.fetchWorkspaces({ project_id: projectId });
      set({
        workspaces: data.workspaces || [],
        loading: false
      });

      // Auto-select first workspace (should be root) if none selected
      if (!get().currentWorkspaceId && data.workspaces && data.workspaces.length > 0) {
        const firstWorkspace = data.workspaces[0];
        set({ currentWorkspaceId: firstWorkspace.id });
      }
    } catch (err) {
      console.error('Failed to load workspaces:', err);
      set({ error: err.message, loading: false });
    }
  },

  /**
   * Switch to a different project
   * This will also reload workspaces and auto-select the first one
   */
  switchProject: async (projectId) => {
    set({
      currentProjectId: projectId,
      currentWorkspaceId: null,  // Clear workspace when switching projects
      workspaces: []
    });

    // CRITICAL SECURITY FIX: Clear current document when switching projects
    // to prevent showing documents from another project (ZoeaStudio-5kn)
    const { useDocumentStore } = await import('./index');
    useDocumentStore.getState().clearCurrentDocumentId();

    if (projectId) {
      await get().loadWorkspaces(projectId);
    }
  },

  /**
   * Initialize from URL parameters
   * Call this when the app loads or when URL params change
   */
  initializeFromUrl: async (projectId, workspaceId) => {
    // Load projects if not already loaded
    if (get().projects.length === 0) {
      await get().loadProjects();
    }

    // If URL has project ID, use it
    if (projectId) {
      set({ currentProjectId: Number(projectId) });
      await get().loadWorkspaces(Number(projectId));

      // If URL has workspace ID, use it
      if (workspaceId) {
        set({ currentWorkspaceId: Number(workspaceId) });
      }
    }
  },

  /**
   * Get current project object
   */
  getCurrentProject: () => {
    const projectId = get().currentProjectId;
    return get().projects.find(p => p.id === projectId) || null;
  },

  /**
   * Get current workspace object
   */
  getCurrentWorkspace: () => {
    const workspaceId = get().currentWorkspaceId;
    return get().workspaces.find(w => w.id === workspaceId) || null;
  },

  /**
   * Update a project in the local state
   * Call this after successfully saving project changes via API
   */
  updateProjectInState: (updatedProject) => {
    set((state) => ({
      projects: state.projects.map((p) =>
        p.id === updatedProject.id ? { ...p, ...updatedProject } : p
      ),
    }));
  },

  /**
   * Add a new project to the local state
   * Call this after successfully creating a project via API
   */
  addProjectToState: (newProject) => {
    set((state) => ({
      projects: [newProject, ...state.projects],
    }));
  },

  /**
   * Reset all state (useful for logout)
   */
  reset: () => {
    set({
      currentProjectId: null,
      currentWorkspaceId: null,
      projects: [],
      workspaces: [],
      loading: false,
      error: null,
    });
  },
}));
