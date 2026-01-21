import { describe, it, expect, vi, beforeEach } from 'vitest';
import { act } from '@testing-library/react';
import { useFlowsStore } from './flowsStore';
import api from '../services/api';

vi.mock('../services/api', () => ({
  __esModule: true,
  default: {
    fetchWorkflows: vi.fn(),
  },
}));

const mockWorkflows = [
  { slug: 'summarize', name: 'Summarize Document', description: 'Create summaries', inputs: [], outputs: [] },
  { slug: 'translate', name: 'Translate Text', description: 'Translate content', inputs: [], outputs: [] },
];

const resetStoreState = () => {
  useFlowsStore.setState({
    workflows: [],
    isLoading: false,
    error: null,
    activeFlowSlug: null,
  });
};

describe('flowsStore', () => {
  beforeEach(() => {
    resetStoreState();
    vi.clearAllMocks();
  });

  describe('fetchWorkflows', () => {
    it('fetches workflows and stores them', async () => {
      api.fetchWorkflows.mockResolvedValueOnce(mockWorkflows);

      await act(async () => {
        await useFlowsStore.getState().fetchWorkflows();
      });

      const state = useFlowsStore.getState();
      expect(state.workflows).toEqual(mockWorkflows);
      expect(state.isLoading).toBe(false);
      expect(state.error).toBeNull();
      expect(api.fetchWorkflows).toHaveBeenCalledTimes(1);
    });

    it('uses cached workflows on subsequent calls', async () => {
      api.fetchWorkflows.mockResolvedValueOnce(mockWorkflows);

      await act(async () => {
        await useFlowsStore.getState().fetchWorkflows();
      });

      api.fetchWorkflows.mockClear();

      await act(async () => {
        await useFlowsStore.getState().fetchWorkflows();
      });

      expect(api.fetchWorkflows).not.toHaveBeenCalled();
      expect(useFlowsStore.getState().workflows).toEqual(mockWorkflows);
    });

    it('forces refresh when force parameter is true', async () => {
      api.fetchWorkflows.mockResolvedValue(mockWorkflows);

      await act(async () => {
        await useFlowsStore.getState().fetchWorkflows();
      });

      api.fetchWorkflows.mockClear();

      await act(async () => {
        await useFlowsStore.getState().fetchWorkflows(true);
      });

      expect(api.fetchWorkflows).toHaveBeenCalledTimes(1);
    });

    it('sets error on fetch failure', async () => {
      api.fetchWorkflows.mockRejectedValueOnce(new Error('Network error'));

      await act(async () => {
        await useFlowsStore.getState().fetchWorkflows();
      });

      const state = useFlowsStore.getState();
      expect(state.error).toBe('Network error');
      expect(state.isLoading).toBe(false);
      expect(state.workflows).toEqual([]);
    });

    it('handles null response gracefully', async () => {
      api.fetchWorkflows.mockResolvedValueOnce(null);

      await act(async () => {
        await useFlowsStore.getState().fetchWorkflows();
      });

      const state = useFlowsStore.getState();
      expect(state.workflows).toEqual([]);
      expect(state.error).toBeNull();
    });
  });

  describe('getWorkflowBySlug', () => {
    it('returns workflow from cache if available', async () => {
      useFlowsStore.setState({ workflows: mockWorkflows });

      const result = await useFlowsStore.getState().getWorkflowBySlug('summarize');

      expect(result).toEqual(mockWorkflows[0]);
      expect(api.fetchWorkflows).not.toHaveBeenCalled();
    });

    it('fetches workflows if not cached and returns found workflow', async () => {
      api.fetchWorkflows.mockResolvedValueOnce(mockWorkflows);

      const result = await useFlowsStore.getState().getWorkflowBySlug('translate');

      expect(result).toEqual(mockWorkflows[1]);
      expect(api.fetchWorkflows).toHaveBeenCalledTimes(1);
    });

    it('returns null for non-existent slug', async () => {
      api.fetchWorkflows.mockResolvedValueOnce(mockWorkflows);

      const result = await useFlowsStore.getState().getWorkflowBySlug('nonexistent');

      expect(result).toBeNull();
    });

    it('returns null for null/undefined slug', async () => {
      const result = await useFlowsStore.getState().getWorkflowBySlug(null);

      expect(result).toBeNull();
      expect(api.fetchWorkflows).not.toHaveBeenCalled();
    });
  });

  describe('setActiveFlow', () => {
    it('sets the active flow slug', () => {
      useFlowsStore.getState().setActiveFlow('summarize');

      expect(useFlowsStore.getState().activeFlowSlug).toBe('summarize');
    });

    it('clears the active flow when set to null', () => {
      useFlowsStore.setState({ activeFlowSlug: 'summarize' });

      useFlowsStore.getState().setActiveFlow(null);

      expect(useFlowsStore.getState().activeFlowSlug).toBeNull();
    });
  });

  describe('getActiveWorkflow', () => {
    it('returns active workflow when slug is set and workflow exists', () => {
      useFlowsStore.setState({
        workflows: mockWorkflows,
        activeFlowSlug: 'summarize',
      });

      const result = useFlowsStore.getState().getActiveWorkflow();

      expect(result).toEqual(mockWorkflows[0]);
    });

    it('returns null when no active slug is set', () => {
      useFlowsStore.setState({
        workflows: mockWorkflows,
        activeFlowSlug: null,
      });

      const result = useFlowsStore.getState().getActiveWorkflow();

      expect(result).toBeNull();
    });

    it('returns null when active slug does not match any workflow', () => {
      useFlowsStore.setState({
        workflows: mockWorkflows,
        activeFlowSlug: 'nonexistent',
      });

      const result = useFlowsStore.getState().getActiveWorkflow();

      expect(result).toBeNull();
    });
  });

  describe('clearError', () => {
    it('clears the error state', () => {
      useFlowsStore.setState({ error: 'Some error' });

      useFlowsStore.getState().clearError();

      expect(useFlowsStore.getState().error).toBeNull();
    });
  });

  describe('reset', () => {
    it('resets all state to initial values', () => {
      useFlowsStore.setState({
        workflows: mockWorkflows,
        isLoading: true,
        error: 'Some error',
        activeFlowSlug: 'summarize',
      });

      useFlowsStore.getState().reset();

      const state = useFlowsStore.getState();
      expect(state.workflows).toEqual([]);
      expect(state.isLoading).toBe(false);
      expect(state.error).toBeNull();
      expect(state.activeFlowSlug).toBeNull();
    });
  });
});
