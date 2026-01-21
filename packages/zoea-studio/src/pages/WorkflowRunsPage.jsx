/**
 * Workflow Runs Page
 *
 * List view for workflow executions (event trigger runs).
 * Shows recent runs with status, trigger name, and document count.
 * Includes a sidebar with summary of workflows, event types, and triggers.
 */

import { useState, useEffect, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { Zap, Clock, CheckCircle, XCircle, Loader2, ChevronDown } from 'lucide-react';
import LayoutFrame from '../components/layout/LayoutFrame';
import WorkflowsSidebar from '../components/WorkflowsSidebar';
import {
  DropdownMenu,
  DropdownMenuTrigger,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuLabel,
} from '@/components/ui/dropdown-menu';
import { useWorkspaceStore } from '../stores';
import api from '../services/api';

const STATUS_CONFIG = {
  pending: {
    label: 'Pending',
    icon: Clock,
    className: 'text-yellow-600 bg-yellow-100',
  },
  running: {
    label: 'Running',
    icon: Loader2,
    className: 'text-blue-600 bg-blue-100',
    animate: true,
  },
  completed: {
    label: 'Completed',
    icon: CheckCircle,
    className: 'text-green-600 bg-green-100',
  },
  failed: {
    label: 'Failed',
    icon: XCircle,
    className: 'text-red-600 bg-red-100',
  },
};

function StatusBadge({ status }) {
  const config = STATUS_CONFIG[status] || STATUS_CONFIG.pending;
  const Icon = config.icon;

  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium ${config.className}`}>
      <Icon className={`h-3 w-3 ${config.animate ? 'animate-spin' : ''}`} />
      {config.label}
    </span>
  );
}

function formatRelativeTime(dateString) {
  if (!dateString) return '';
  const date = new Date(dateString);
  const now = new Date();
  const diff = now - date;

  // Less than a minute
  if (diff < 60000) {
    return 'Just now';
  }

  // Less than an hour
  if (diff < 3600000) {
    const minutes = Math.floor(diff / 60000);
    return `${minutes}m ago`;
  }

  // Less than 24 hours
  if (diff < 86400000) {
    const hours = Math.floor(diff / 3600000);
    return `${hours}h ago`;
  }

  // Less than 7 days
  if (diff < 604800000) {
    const days = Math.floor(diff / 86400000);
    return `${days}d ago`;
  }

  // Older - show date
  return date.toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: date.getFullYear() !== now.getFullYear() ? 'numeric' : undefined,
  });
}

function formatDuration(seconds) {
  if (!seconds) return '';
  if (seconds < 1) return '<1s';
  if (seconds < 60) return `${Math.round(seconds)}s`;
  const minutes = Math.floor(seconds / 60);
  const remainingSeconds = Math.round(seconds % 60);
  return `${minutes}m ${remainingSeconds}s`;
}

function WorkflowRunsPage() {
  const navigate = useNavigate();
  const currentProjectId = useWorkspaceStore((state) => state.currentProjectId);
  const [runs, setRuns] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [statusFilter, setStatusFilter] = useState(null);
  const [triggerFilter, setTriggerFilter] = useState(null);

  useEffect(() => {
    if (currentProjectId) {
      fetchRuns();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [statusFilter, currentProjectId]);

  const handleSelectEventType = () => {
    // Event type selection currently just clears trigger filter
    // In the future, could filter runs by event type
    setTriggerFilter(null);
  };

  const handleSelectTrigger = (trigger) => {
    setTriggerFilter(trigger?.id || null);
  };

  const fetchRuns = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.fetchEventTriggerRuns({
        status: statusFilter,
        project_id: currentProjectId,
      });
      setRuns(data);
    } catch (err) {
      console.error('Failed to fetch workflow runs:', err);
      setError(err.message || 'Failed to load workflow runs');
    } finally {
      setLoading(false);
    }
  };

  const handleSelectRun = (runId) => {
    navigate(`/workflows/${runId}`);
  };

  const statusOptions = [
    { value: null, label: 'All statuses' },
    { value: 'pending', label: 'Pending' },
    { value: 'running', label: 'Running' },
    { value: 'completed', label: 'Completed' },
    { value: 'failed', label: 'Failed' },
  ];

  const filteredRuns = useMemo(() => {
    let result = [...runs];

    // Note: Event type filtering would require adding event_type to run response
    // or fetching trigger details. For now, we skip this filter since the
    // runs already show the trigger name which indicates the workflow type.

    // Filter by trigger if selected
    if (triggerFilter) {
      result = result.filter((run) => run.trigger_id === triggerFilter);
    }

    // Sort by created_at descending
    return result.sort((a, b) => {
      return new Date(b.created_at) - new Date(a.created_at);
    });
  }, [runs, triggerFilter]);

  const actions = (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button
          type="button"
          className="inline-flex items-center gap-2 px-3 py-2 text-sm border border-border rounded-md hover:bg-muted transition-colors"
        >
          {statusFilter ? STATUS_CONFIG[statusFilter]?.label : 'All statuses'}
          <ChevronDown className="h-4 w-4" />
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-40">
        <DropdownMenuLabel>Filter by status</DropdownMenuLabel>
        <DropdownMenuSeparator />
        {statusOptions.map((option) => (
          <DropdownMenuItem
            key={option.value ?? 'all'}
            onClick={() => setStatusFilter(option.value)}
            className={statusFilter === option.value ? 'bg-muted' : ''}
          >
            {option.label}
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  );

  const content = (
    <div className="workflow-runs-page">
      {/* Error state */}
      {error && (
        <div className="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded mb-4" role="alert">
          {error}
        </div>
      )}

      {/* Loading state */}
      {loading && runs.length === 0 && (
        <div className="text-center py-8">
          <Loader2 className="animate-spin h-8 w-8 text-primary mx-auto" />
          <p className="text-gray-500 mt-2">Loading workflow runs...</p>
        </div>
      )}

      {/* No project selected */}
      {!currentProjectId && (
        <div className="text-center py-12">
          <Zap size={48} className="mx-auto text-gray-300 mb-4" />
          <h5 className="text-gray-600">No project selected</h5>
          <p className="text-gray-500">
            Select a project to view its workflow runs
          </p>
        </div>
      )}

      {/* Empty state */}
      {currentProjectId && !loading && filteredRuns.length === 0 && (
        <div className="text-center py-12">
          <Zap size={48} className="mx-auto text-gray-300 mb-4" />
          {statusFilter ? (
            <>
              <h5 className="text-gray-600">No {statusFilter} workflows</h5>
              <p className="text-gray-500">
                Try selecting a different status filter
              </p>
            </>
          ) : (
            <>
              <h5 className="text-gray-600">No workflow runs yet</h5>
              <p className="text-gray-500">
                Select documents and run a workflow to see runs here
              </p>
            </>
          )}
        </div>
      )}

      {/* Runs list */}
      {filteredRuns.length > 0 && (
        <div className="space-y-2">
          {filteredRuns.map((run) => {
            const documentCount = run.inputs?.document_count || run.inputs?.document_ids?.length || 0;

            return (
              <div
                key={run.id}
                className="flex items-center gap-4 p-4 bg-card border border-border rounded-lg hover:bg-muted/50 cursor-pointer transition-colors"
                onClick={() => handleSelectRun(run.run_id)}
                role="button"
                tabIndex={0}
                onKeyPress={(e) => {
                  if (e.key === 'Enter') handleSelectRun(run.run_id);
                }}
              >
                <div className="flex-shrink-0">
                  <div className="h-10 w-10 rounded-full bg-primary/10 flex items-center justify-center">
                    <Zap className="h-5 w-5 text-primary" />
                  </div>
                </div>

                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="font-medium text-foreground truncate">
                      {run.trigger_name}
                    </span>
                    <StatusBadge status={run.status} />
                  </div>
                  <div className="flex items-center gap-3 text-sm text-muted-foreground">
                    <span>{documentCount} document{documentCount !== 1 ? 's' : ''}</span>
                    <span className="text-border">·</span>
                    <span>{formatRelativeTime(run.created_at)}</span>
                    {run.duration_seconds && (
                      <>
                        <span className="text-border">·</span>
                        <span>{formatDuration(run.duration_seconds)}</span>
                      </>
                    )}
                  </div>
                </div>

                <div className="flex-shrink-0 text-muted-foreground">
                  <ChevronDown className="h-5 w-5 -rotate-90" />
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Results count */}
      {!loading && filteredRuns.length > 0 && (
        <div className="text-sm text-gray-500 mt-4 text-center">
          Showing {filteredRuns.length} workflow run{filteredRuns.length !== 1 ? 's' : ''}
          {statusFilter && ` (${statusFilter})`}
        </div>
      )}
    </div>
  );

  const sidebarContent = (
    <WorkflowsSidebar
      projectId={currentProjectId}
      onSelectEventType={handleSelectEventType}
      onSelectTrigger={handleSelectTrigger}
    />
  );

  return (
    <LayoutFrame
      title="Workflows"
      actions={actions}
      variant="full"
      sidebar={sidebarContent}
      viewSidebarTitle="Overview"
    >
      <div className="p-6 max-w-4xl mx-auto">
        {content}
      </div>
    </LayoutFrame>
  );
}

export default WorkflowRunsPage;
