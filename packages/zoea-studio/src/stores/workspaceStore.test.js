import { describe, it, expect, vi, beforeEach } from 'vitest';

vi.mock('../services/api', () => ({
  default: {
    fetchProjects: vi.fn(),
    fetchWorkspaces: vi.fn(),
  },
}));

vi.mock('./index', () => ({
  useDocumentStore: {
    getState: vi.fn(() => ({
      clearCurrentDocumentId: vi.fn(),
    })),
  },
}));

import api from '../services/api';
import { useWorkspaceStore } from './workspaceStore';

const resetStoreState = () => {
  useWorkspaceStore.setState({
    currentProjectId: null,
    currentWorkspaceId: null,
    projects: [],
    workspaces: [],
    loading: false,
    error: null,
  });
};

describe('useWorkspaceStore', () => {
  beforeEach(() => {
    resetStoreState();
    vi.clearAllMocks();
  });

  describe('loadWorkspaces', () => {
    it('calls api.fetchWorkspaces with payload object and stores results', async () => {
      const mockWorkspaces = [{ id: 10, name: 'Root Workspace', level: 0 }];
      api.fetchWorkspaces.mockResolvedValue({ workspaces: mockWorkspaces });

      await useWorkspaceStore.getState().loadWorkspaces(123);

      expect(api.fetchWorkspaces).toHaveBeenCalledTimes(1);
      expect(api.fetchWorkspaces).toHaveBeenCalledWith({ project_id: 123 });

      const state = useWorkspaceStore.getState();
      expect(state.workspaces).toEqual(mockWorkspaces);
      expect(state.loading).toBe(false);
      expect(state.error).toBeNull();
    });
  });

  describe('switchProject - Security Fix ZoeaStudio-5kn', () => {
    it('clears currentDocumentId when switching projects to prevent cross-project document leaks', async () => {
      const mockWorkspaces = [{ id: 1, name: 'Workspace 1' }];
      api.fetchWorkspaces.mockResolvedValue({ workspaces: mockWorkspaces });

      // Import the mocked module to access the mock
      const { useDocumentStore } = await import('./index');
      const clearMock = vi.fn();
      useDocumentStore.getState.mockReturnValue({
        clearCurrentDocumentId: clearMock,
      });

      // Switch to project 456
      await useWorkspaceStore.getState().switchProject(456);

      // Verify clearCurrentDocumentId was called - THIS IS THE SECURITY FIX
      expect(clearMock).toHaveBeenCalledTimes(1);

      // Verify project state was updated
      const state = useWorkspaceStore.getState();
      expect(state.currentProjectId).toBe(456);
      expect(state.workspaces).toEqual(mockWorkspaces);
      // Note: currentWorkspaceId will be auto-set to first workspace (id=1) by loadWorkspaces
      expect(state.currentWorkspaceId).toBe(1);
    });
  });
});
