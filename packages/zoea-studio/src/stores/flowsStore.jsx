/**
 * Flows Store
 *
 * Manages state for the Flows/Workflows feature.
 * Stores workflow definitions, tracks the currently active flow,
 * and manages workflow run history and polling.
 */

import { create } from 'zustand';
import toast from 'react-hot-toast';
import api from '../services/api';

export const useFlowsStore = create((set, get) => ({
  // =========================================================================
  // Workflows State
  // =========================================================================
  workflows: [],
  isLoading: false,
  error: null,
  activeFlowSlug: null,

  // =========================================================================
  // Workflow Runs State
  // =========================================================================
  runs: [],
  runsTotal: 0,
  runsPage: 1,
  runsPerPage: 20,
  runsLoading: false,
  runsError: null,

  // Current run being viewed/polled
  currentRun: null,
  currentRunLoading: false,
  currentRunError: null,

  // Polling state
  pollingInterval: null,

  // =========================================================================
  // Workflows Actions
  // =========================================================================

  /**
   * Fetch all workflows from the API
   * Caches results to avoid redundant requests unless force is true
   */
  fetchWorkflows: async (force = false) => {
    // Skip if already loaded and not forcing refresh
    if (!force && get().workflows.length > 0 && !get().error) {
      return get().workflows;
    }

    set({ isLoading: true, error: null });
    try {
      const data = await api.fetchWorkflows();
      const workflows = data || [];
      set({ workflows, isLoading: false });
      return workflows;
    } catch (err) {
      console.error('Failed to fetch workflows:', err);
      set({ error: err.message || 'Failed to fetch workflows', isLoading: false });
      return [];
    }
  },

  /**
   * Get a workflow by its slug from cache, or fetch if not available
   * @param {string} slug - The workflow slug to look up
   * @returns {Promise<Object|null>} The workflow object or null if not found
   */
  getWorkflowBySlug: async (slug) => {
    if (!slug) return null;

    // Check cache first
    const cached = get().workflows.find((w) => w.slug === slug);
    if (cached) {
      return cached;
    }

    // Fetch workflows if not cached
    const workflows = await get().fetchWorkflows();
    return workflows.find((w) => w.slug === slug) || null;
  },

  /**
   * Set the active flow slug
   * @param {string|null} slug - The slug of the active flow, or null to clear
   */
  setActiveFlow: (slug) => {
    set({ activeFlowSlug: slug });
  },

  /**
   * Clear the error state
   */
  clearError: () => {
    set({ error: null });
  },

  /**
   * Get the currently active workflow object
   * @returns {Object|null} The active workflow or null
   */
  getActiveWorkflow: () => {
    const slug = get().activeFlowSlug;
    if (!slug) return null;
    return get().workflows.find((w) => w.slug === slug) || null;
  },

  // =========================================================================
  // Workflow Runs Actions
  // =========================================================================

  /**
   * Fetch workflow runs with optional filters
   * @param {Object} params - Query parameters
   * @param {string} [params.status] - Filter by status
   * @param {string} [params.workflow_slug] - Filter by workflow slug
   * @param {number} [params.page] - Page number
   * @param {number} [params.per_page] - Items per page
   */
  fetchRuns: async (params = {}) => {
    set({ runsLoading: true, runsError: null });
    try {
      const data = await api.fetchWorkflowRuns({
        page: params.page || get().runsPage,
        per_page: params.per_page || get().runsPerPage,
        status: params.status,
        workflow_slug: params.workflow_slug,
      });

      set({
        runs: data.runs || [],
        runsTotal: data.total || 0,
        runsPage: data.page || 1,
        runsPerPage: data.per_page || 20,
        runsLoading: false,
      });

      return data;
    } catch (err) {
      console.error('Failed to fetch workflow runs:', err);
      set({
        runsError: err.message || 'Failed to fetch workflow runs',
        runsLoading: false,
      });
      return null;
    }
  },

  /**
   * Fetch a single workflow run by ID
   * @param {string} runId - The workflow run ID
   * @param {boolean} [silent] - If true, don't update loading state (for polling)
   */
  fetchRun: async (runId, silent = false) => {
    if (!runId) return null;

    if (!silent) {
      set({ currentRunLoading: true, currentRunError: null });
    }

    try {
      const data = await api.fetchWorkflowRun(runId);
      set({ currentRun: data, currentRunLoading: false });
      return data;
    } catch (err) {
      console.error('Failed to fetch workflow run:', err);
      if (!silent) {
        set({
          currentRunError: err.message || 'Failed to fetch workflow run',
          currentRunLoading: false,
        });
      }
      return null;
    }
  },

  /**
   * Execute a workflow
   * @param {string} slug - Workflow slug
   * @param {Object} inputs - Workflow inputs
   * @param {Object} options - Execution options
   * @returns {Promise<Object|null>} The workflow run response
   */
  runWorkflow: async (slug, inputs = {}, options = {}) => {
    try {
      const result = await api.runWorkflow(slug, inputs, options);

      // If background execution, set as current run and start polling
      if (options.background && result.run_id) {
        set({ currentRun: result });

        // Optionally start polling for status updates
        if (result.status === 'pending' || result.status === 'running') {
          get().startPolling(result.run_id);
        }
      }

      return result;
    } catch (err) {
      console.error('Failed to run workflow:', err);
      throw err;
    }
  },

  /**
   * Start polling for run status updates
   * @param {string} runId - The workflow run ID to poll
   * @param {number} [intervalMs] - Polling interval in milliseconds (default 2000)
   * @param {boolean} [showToast] - Whether to show toast notification on completion (default true)
   */
  startPolling: (runId, intervalMs = 2000, showToast = true) => {
    // Clear any existing polling
    get().stopPolling();

    // Track initial status to detect changes
    let lastStatus = null;

    const poll = async () => {
      const run = await get().fetchRun(runId, true);

      if (!run) return;

      // Show toast notification when status changes to a terminal state
      if (showToast && lastStatus !== run.status) {
        if (run.status === 'completed') {
          // Check if there's a document output to link to
          const documentOutput = run.outputs
            ? Object.values(run.outputs).find(
                (out) => out.type === 'MarkdownDocument' && out.id
              )
            : null;

          if (documentOutput) {
            toast.success(
              (t) => (
                <div>
                  <div style={{ marginBottom: '0.5rem' }}>
                    {run.workflow_name} completed!
                  </div>
                  <a
                    href={`/documents/${documentOutput.id}`}
                    onClick={() => toast.dismiss(t.id)}
                    style={{
                      color: 'var(--primary)',
                      textDecoration: 'underline',
                      fontWeight: '500',
                    }}
                  >
                    View {documentOutput.name || 'document'} →
                  </a>
                </div>
              ),
              { duration: 8000 }
            );
          } else {
            toast.success(`Workflow "${run.workflow_name}" completed successfully`, {
              duration: 5000,
            });
          }
        } else if (run.status === 'failed') {
          toast.error(`Workflow "${run.workflow_name}" failed: ${run.error || 'Unknown error'}`, {
            duration: 8000,
          });
        } else if (run.status === 'cancelled') {
          toast(`Workflow "${run.workflow_name}" was cancelled`, {
            icon: '⚠️',
            duration: 5000,
          });
        }
      }

      lastStatus = run.status;

      // Stop polling if run is complete
      if (['completed', 'failed', 'cancelled'].includes(run.status)) {
        get().stopPolling();
      }
    };

    // Initial poll
    poll();

    // Set up interval
    const interval = setInterval(poll, intervalMs);
    set({ pollingInterval: interval });
  },

  /**
   * Stop polling for run status updates
   */
  stopPolling: () => {
    const { pollingInterval } = get();
    if (pollingInterval) {
      clearInterval(pollingInterval);
      set({ pollingInterval: null });
    }
  },

  /**
   * Clear current run state
   */
  clearCurrentRun: () => {
    get().stopPolling();
    set({ currentRun: null, currentRunLoading: false, currentRunError: null });
  },

  /**
   * Set the current page for runs pagination
   * @param {number} page - Page number
   */
  setRunsPage: (page) => {
    set({ runsPage: page });
  },

  // =========================================================================
  // Reset
  // =========================================================================

  /**
   * Reset all state (useful for logout or cleanup)
   */
  reset: () => {
    get().stopPolling();
    set({
      workflows: [],
      isLoading: false,
      error: null,
      activeFlowSlug: null,
      runs: [],
      runsTotal: 0,
      runsPage: 1,
      runsPerPage: 20,
      runsLoading: false,
      runsError: null,
      currentRun: null,
      currentRunLoading: false,
      currentRunError: null,
      pollingInterval: null,
    });
  },
}));
