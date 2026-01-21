/**
 * Workflows Sidebar
 *
 * Shows a summary of available workflows, event types, and triggers.
 * Provides navigation to detail views for drilling down into the
 * events and workflow systems.
 */

import { useState, useEffect } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import {
  Zap,
  Mail,
  FileText,
  FilePlus,
  FileCheck,
  MousePointer,
  ChevronDown,
  ChevronRight,
  Loader2,
  CheckCircle,
  XCircle,
  Clock,
} from 'lucide-react';
import api from '../services/api';

// Icons for each event type
const EVENT_TYPE_ICONS = {
  email_received: Mail,
  document_created: FilePlus,
  document_updated: FileCheck,
  documents_selected: MousePointer,
};

// Status configuration for run counts
const STATUS_STYLES = {
  pending: 'text-yellow-600',
  running: 'text-blue-600',
  completed: 'text-green-600',
  failed: 'text-red-600',
};

export default function WorkflowsSidebar({ projectId, onSelectEventType, onSelectTrigger }) {
  const navigate = useNavigate();
  const location = useLocation();
  const [eventTypes, setEventTypes] = useState([]);
  const [triggers, setTriggers] = useState([]);
  const [runStats, setRunStats] = useState({ total: 0, byStatus: {} });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [expandedSections, setExpandedSections] = useState({
    summary: true,
    eventTypes: true,
    triggers: true,
  });

  useEffect(() => {
    loadData();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId]);

  const loadData = async () => {
    try {
      setLoading(true);
      setError(null);

      // Fetch event types, triggers, and runs in parallel
      const [eventTypesRes, triggersData, runsData] = await Promise.all([
        api.fetchEventTypes(),
        api.fetchEventTriggers({ project_id: projectId }),
        api.fetchEventTriggerRuns({ project_id: projectId, limit: 100 }),
      ]);

      setEventTypes(eventTypesRes.event_types || []);
      setTriggers(triggersData || []);

      // Calculate run statistics
      const stats = { total: runsData.length, byStatus: {} };
      runsData.forEach((run) => {
        stats.byStatus[run.status] = (stats.byStatus[run.status] || 0) + 1;
      });
      setRunStats(stats);
    } catch (err) {
      console.error('Failed to load workflows data:', err);
      setError(err.message || 'Failed to load data');
    } finally {
      setLoading(false);
    }
  };

  const toggleSection = (section) => {
    setExpandedSections((prev) => ({
      ...prev,
      [section]: !prev[section],
    }));
  };

  const handleEventTypeClick = (eventType) => {
    if (onSelectEventType) {
      onSelectEventType(eventType);
    }
  };

  const handleTriggerClick = (trigger) => {
    if (onSelectTrigger) {
      onSelectTrigger(trigger);
    }
  };

  const isOnWorkflowsPage = location.pathname === '/workflows';

  if (loading) {
    return (
      <div className="h-full flex items-center justify-center p-4">
        <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-4">
        <div className="text-sm text-red-500">{error}</div>
        <button
          type="button"
          onClick={loadData}
          className="mt-2 text-sm text-primary hover:underline"
        >
          Try again
        </button>
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col">
      {/* Summary Section */}
      <div className="mb-4">
        <button
          type="button"
          onClick={() => toggleSection('summary')}
          className="w-full flex items-center justify-between px-2 py-1.5 text-sm font-medium text-foreground hover:bg-muted rounded-md transition-colors"
        >
          <span className="flex items-center gap-2">
            <Zap className="h-4 w-4" />
            Summary
          </span>
          {expandedSections.summary ? (
            <ChevronDown className="h-4 w-4" />
          ) : (
            <ChevronRight className="h-4 w-4" />
          )}
        </button>
        {expandedSections.summary && (
          <div className="mt-2 space-y-2 px-2">
            <div className="grid grid-cols-2 gap-2">
              <div className="bg-muted/50 rounded-md p-2">
                <div className="text-2xl font-bold text-foreground">{triggers.length}</div>
                <div className="text-xs text-muted-foreground">Triggers</div>
              </div>
              <div className="bg-muted/50 rounded-md p-2">
                <div className="text-2xl font-bold text-foreground">{runStats.total}</div>
                <div className="text-xs text-muted-foreground">Runs</div>
              </div>
            </div>
            {runStats.total > 0 && (
              <div className="flex flex-wrap gap-2 text-xs">
                {runStats.byStatus.completed > 0 && (
                  <span className="flex items-center gap-1 text-green-600">
                    <CheckCircle className="h-3 w-3" />
                    {runStats.byStatus.completed}
                  </span>
                )}
                {runStats.byStatus.running > 0 && (
                  <span className="flex items-center gap-1 text-blue-600">
                    <Loader2 className="h-3 w-3 animate-spin" />
                    {runStats.byStatus.running}
                  </span>
                )}
                {runStats.byStatus.pending > 0 && (
                  <span className="flex items-center gap-1 text-yellow-600">
                    <Clock className="h-3 w-3" />
                    {runStats.byStatus.pending}
                  </span>
                )}
                {runStats.byStatus.failed > 0 && (
                  <span className="flex items-center gap-1 text-red-600">
                    <XCircle className="h-3 w-3" />
                    {runStats.byStatus.failed}
                  </span>
                )}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Event Types Section */}
      <div className="mb-4">
        <button
          type="button"
          onClick={() => toggleSection('eventTypes')}
          className="w-full flex items-center justify-between px-2 py-1.5 text-sm font-medium text-foreground hover:bg-muted rounded-md transition-colors"
        >
          <span className="flex items-center gap-2">
            <FileText className="h-4 w-4" />
            Event Types
          </span>
          {expandedSections.eventTypes ? (
            <ChevronDown className="h-4 w-4" />
          ) : (
            <ChevronRight className="h-4 w-4" />
          )}
        </button>
        {expandedSections.eventTypes && (
          <div className="mt-2 space-y-0.5">
            {eventTypes.map((eventType) => {
              const Icon = EVENT_TYPE_ICONS[eventType.value] || FileText;
              const triggerCount = triggers.filter(
                (t) => t.event_type === eventType.value
              ).length;

              return (
                <button
                  key={eventType.value}
                  type="button"
                  onClick={() => handleEventTypeClick(eventType)}
                  className="w-full flex items-center justify-between px-2 py-1.5 text-sm text-foreground hover:bg-muted rounded-md transition-colors group"
                >
                  <span className="flex items-center gap-2">
                    <Icon className="h-4 w-4 text-muted-foreground group-hover:text-foreground" />
                    <span>{eventType.label}</span>
                  </span>
                  {triggerCount > 0 && (
                    <span className="text-xs text-muted-foreground bg-muted px-1.5 py-0.5 rounded">
                      {triggerCount}
                    </span>
                  )}
                </button>
              );
            })}
          </div>
        )}
      </div>

      {/* Triggers Section */}
      <div className="flex-1 overflow-y-auto">
        <button
          type="button"
          onClick={() => toggleSection('triggers')}
          className="w-full flex items-center justify-between px-2 py-1.5 text-sm font-medium text-foreground hover:bg-muted rounded-md transition-colors"
        >
          <span className="flex items-center gap-2">
            <Zap className="h-4 w-4" />
            Triggers
          </span>
          {expandedSections.triggers ? (
            <ChevronDown className="h-4 w-4" />
          ) : (
            <ChevronRight className="h-4 w-4" />
          )}
        </button>
        {expandedSections.triggers && (
          <div className="mt-2 space-y-0.5">
            {triggers.length === 0 ? (
              <div className="px-2 py-2 text-sm text-muted-foreground">
                No triggers configured
              </div>
            ) : (
              triggers.map((trigger) => {
                const Icon = EVENT_TYPE_ICONS[trigger.event_type] || Zap;

                return (
                  <button
                    key={trigger.id}
                    type="button"
                    onClick={() => handleTriggerClick(trigger)}
                    className="w-full flex items-start gap-2 px-2 py-2 text-sm text-foreground hover:bg-muted rounded-md transition-colors group text-left"
                  >
                    <Icon className="h-4 w-4 mt-0.5 text-muted-foreground group-hover:text-foreground flex-shrink-0" />
                    <div className="min-w-0 flex-1">
                      <div className="font-medium truncate">{trigger.name}</div>
                      <div className="text-xs text-muted-foreground flex items-center gap-2">
                        <span
                          className={`w-1.5 h-1.5 rounded-full ${
                            trigger.is_enabled ? 'bg-green-500' : 'bg-gray-400'
                          }`}
                        />
                        <span>{trigger.skill_count} skill{trigger.skill_count !== 1 ? 's' : ''}</span>
                      </div>
                    </div>
                  </button>
                );
              })
            )}
          </div>
        )}
      </div>

      {/* View All Runs Link */}
      {!isOnWorkflowsPage && (
        <div className="border-t border-border pt-2 mt-2">
          <button
            type="button"
            onClick={() => navigate('/workflows')}
            className="w-full flex items-center gap-2 px-2 py-1.5 text-sm text-muted-foreground hover:text-foreground hover:bg-muted rounded-md transition-colors"
          >
            <Zap className="h-4 w-4" />
            View All Runs
          </button>
        </div>
      )}
    </div>
  );
}
