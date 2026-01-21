/**
 * Workflow Run Detail Page
 *
 * Shows detailed information about a specific workflow run including
 * inputs, outputs, errors, and telemetry data.
 */

import { useState, useEffect } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import {
  Zap,
  Clock,
  CheckCircle,
  XCircle,
  Loader2,
  ArrowLeft,
  FileText,
  ChevronDown,
  ChevronUp,
  ExternalLink,
  Copy,
  Check,
} from 'lucide-react';
import toast from 'react-hot-toast';
import LayoutFrame from '../components/layout/LayoutFrame';
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
    <span className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-sm font-medium ${config.className}`}>
      <Icon className={`h-4 w-4 ${config.animate ? 'animate-spin' : ''}`} />
      {config.label}
    </span>
  );
}

function formatDateTime(dateString) {
  if (!dateString) return '-';
  return new Date(dateString).toLocaleString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
    second: '2-digit',
  });
}

function formatDuration(seconds) {
  if (!seconds) return '-';
  if (seconds < 1) return '<1s';
  if (seconds < 60) return `${seconds.toFixed(1)}s`;
  const minutes = Math.floor(seconds / 60);
  const remainingSeconds = (seconds % 60).toFixed(1);
  return `${minutes}m ${remainingSeconds}s`;
}

function CollapsibleSection({ title, defaultOpen = true, children }) {
  const [isOpen, setIsOpen] = useState(defaultOpen);

  return (
    <div className="border border-border rounded-lg overflow-hidden">
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        className="w-full flex items-center justify-between px-4 py-3 bg-muted/30 hover:bg-muted/50 transition-colors"
      >
        <span className="font-medium text-foreground">{title}</span>
        {isOpen ? (
          <ChevronUp className="h-4 w-4 text-muted-foreground" />
        ) : (
          <ChevronDown className="h-4 w-4 text-muted-foreground" />
        )}
      </button>
      {isOpen && <div className="p-4 border-t border-border">{children}</div>}
    </div>
  );
}

function CopyButton({ text }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      toast.error('Failed to copy');
    }
  };

  return (
    <button
      type="button"
      onClick={handleCopy}
      className="p-1 hover:bg-muted rounded transition-colors"
      title="Copy to clipboard"
    >
      {copied ? (
        <Check className="h-4 w-4 text-green-600" />
      ) : (
        <Copy className="h-4 w-4 text-muted-foreground" />
      )}
    </button>
  );
}

function DocumentLink({ doc }) {
  return (
    <Link
      to={`/documents/${doc.id}`}
      className="flex items-center gap-2 p-2 rounded-md hover:bg-muted transition-colors group"
    >
      <FileText className="h-4 w-4 text-muted-foreground" />
      <span className="text-sm text-foreground group-hover:text-primary truncate">
        {doc.name}
      </span>
      <span className="text-xs text-muted-foreground">
        ({doc.document_type})
      </span>
      <ExternalLink className="h-3 w-3 text-muted-foreground ml-auto opacity-0 group-hover:opacity-100" />
    </Link>
  );
}

function CreatedDocumentLink({ documentId }) {
  return (
    <Link
      to={`/documents/${documentId}`}
      className="flex items-center gap-2 p-2 rounded-md hover:bg-muted transition-colors group"
    >
      <FileText className="h-4 w-4 text-green-600" />
      <span className="text-sm text-foreground group-hover:text-primary">
        Document #{documentId}
      </span>
      <ExternalLink className="h-3 w-3 text-muted-foreground ml-auto opacity-0 group-hover:opacity-100" />
    </Link>
  );
}

function WorkflowRunDetailPage() {
  const { runId } = useParams();
  const navigate = useNavigate();
  const [run, setRun] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (runId) {
      fetchRun();
    }
  }, [runId]);

  const fetchRun = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.fetchEventTriggerRun(runId);
      setRun(data);
    } catch (err) {
      console.error('Failed to fetch workflow run:', err);
      setError(err.message || 'Failed to load workflow run');
    } finally {
      setLoading(false);
    }
  };

  const actions = (
    <button
      type="button"
      onClick={() => navigate('/workflows')}
      className="inline-flex items-center gap-2 px-3 py-2 text-sm text-muted-foreground hover:text-foreground transition-colors"
    >
      <ArrowLeft className="h-4 w-4" />
      Back to Workflows
    </button>
  );

  if (loading) {
    return (
      <LayoutFrame title="Workflow Run" actions={actions} variant="content-centered">
        <div className="text-center py-8">
          <Loader2 className="animate-spin h-8 w-8 text-primary mx-auto" />
          <p className="text-gray-500 mt-2">Loading workflow run...</p>
        </div>
      </LayoutFrame>
    );
  }

  if (error) {
    return (
      <LayoutFrame title="Workflow Run" actions={actions} variant="content-centered">
        <div className="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded" role="alert">
          {error}
        </div>
      </LayoutFrame>
    );
  }

  if (!run) {
    return (
      <LayoutFrame title="Workflow Run" actions={actions} variant="content-centered">
        <div className="text-center py-12">
          <Zap size={48} className="mx-auto text-gray-300 mb-4" />
          <h5 className="text-gray-600">Workflow run not found</h5>
        </div>
      </LayoutFrame>
    );
  }

  const documents = run.inputs?.documents || [];
  const createdDocumentIds = run.outputs?.created_document_ids || [];
  const hasOutputs = run.outputs && Object.keys(run.outputs).length > 0;
  const hasTelemetry = run.telemetry && Object.keys(run.telemetry).length > 0;

  return (
    <LayoutFrame
      title={run.trigger_name}
      actions={actions}
      variant="content-centered"
    >
      <div className="space-y-6">
        {/* Header section */}
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-4">
            <div className="h-12 w-12 rounded-full bg-primary/10 flex items-center justify-center">
              <Zap className="h-6 w-6 text-primary" />
            </div>
            <div>
              <h2 className="text-xl font-semibold text-foreground">{run.trigger_name}</h2>
              <div className="flex items-center gap-2 mt-1">
                <span className="text-sm text-muted-foreground font-mono">
                  {run.run_id}
                </span>
                <CopyButton text={run.run_id} />
              </div>
            </div>
          </div>
          <StatusBadge status={run.status} />
        </div>

        {/* Timing section */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 p-4 bg-muted/30 rounded-lg">
          <div>
            <div className="text-xs text-muted-foreground uppercase tracking-wide mb-1">Created</div>
            <div className="text-sm font-medium">{formatDateTime(run.created_at)}</div>
          </div>
          <div>
            <div className="text-xs text-muted-foreground uppercase tracking-wide mb-1">Started</div>
            <div className="text-sm font-medium">{formatDateTime(run.started_at)}</div>
          </div>
          <div>
            <div className="text-xs text-muted-foreground uppercase tracking-wide mb-1">Completed</div>
            <div className="text-sm font-medium">{formatDateTime(run.completed_at)}</div>
          </div>
          <div>
            <div className="text-xs text-muted-foreground uppercase tracking-wide mb-1">Duration</div>
            <div className="text-sm font-medium">{formatDuration(run.duration_seconds)}</div>
          </div>
        </div>

        {/* Error section */}
        {run.error && (
          <div className="p-4 bg-red-50 border border-red-200 rounded-lg">
            <div className="flex items-center gap-2 mb-2">
              <XCircle className="h-5 w-5 text-red-600" />
              <span className="font-medium text-red-800">Error</span>
            </div>
            <pre className="text-sm text-red-700 whitespace-pre-wrap font-mono overflow-x-auto">
              {run.error}
            </pre>
          </div>
        )}

        {/* Inputs section */}
        <CollapsibleSection title={`Inputs (${documents.length} documents)`} defaultOpen={true}>
          {documents.length > 0 ? (
            <div className="space-y-1">
              {documents.map((doc) => (
                <DocumentLink key={doc.id} doc={doc} />
              ))}
            </div>
          ) : (
            <p className="text-sm text-muted-foreground">No input documents</p>
          )}
        </CollapsibleSection>

        {/* Created Documents section */}
        {createdDocumentIds.length > 0 && (
          <CollapsibleSection title={`Created Documents (${createdDocumentIds.length})`} defaultOpen={true}>
            <div className="space-y-1">
              {createdDocumentIds.map((docId) => (
                <CreatedDocumentLink key={docId} documentId={docId} />
              ))}
            </div>
          </CollapsibleSection>
        )}

        {/* Outputs section */}
        {hasOutputs && (
          <CollapsibleSection title="Outputs (Raw)" defaultOpen={false}>
            <pre className="text-sm text-foreground bg-muted/50 p-3 rounded-md overflow-x-auto font-mono">
              {JSON.stringify(run.outputs, null, 2)}
            </pre>
          </CollapsibleSection>
        )}

        {/* Telemetry section */}
        {hasTelemetry && (
          <CollapsibleSection title="Telemetry" defaultOpen={false}>
            <pre className="text-sm text-foreground bg-muted/50 p-3 rounded-md overflow-x-auto font-mono">
              {JSON.stringify(run.telemetry, null, 2)}
            </pre>
          </CollapsibleSection>
        )}

        {/* Metadata section */}
        <CollapsibleSection title="Details" defaultOpen={false}>
          <div className="grid grid-cols-2 gap-4 text-sm">
            <div>
              <span className="text-muted-foreground">Run ID:</span>
              <span className="ml-2 font-mono">{run.run_id}</span>
            </div>
            <div>
              <span className="text-muted-foreground">Trigger ID:</span>
              <span className="ml-2">{run.trigger_id}</span>
            </div>
            <div>
              <span className="text-muted-foreground">Source Type:</span>
              <span className="ml-2">{run.source_type}</span>
            </div>
            <div>
              <span className="text-muted-foreground">Source ID:</span>
              <span className="ml-2">{run.source_id}</span>
            </div>
          </div>
        </CollapsibleSection>
      </div>
    </LayoutFrame>
  );
}

export default WorkflowRunDetailPage;
