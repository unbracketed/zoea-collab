import { useState, useEffect, useCallback } from 'react';
import {
  Code,
  Copy,
  Download,
  Check,
  ChevronDown,
  ChevronRight,
  FileCode,
  FileText,
  Image,
  File,
} from 'lucide-react';
import api from '../services/api';

function getArtifactIcon(sourceChannel) {
  switch (sourceChannel) {
    case 'code':
      return FileCode;
    case 'document':
      return FileText;
    case 'image':
      return Image;
    default:
      return File;
  }
}

function CodeBlockArtifact({ artifact, isExpanded, onToggle }) {
  const [copied, setCopied] = useState(false);
  const { language, code } = artifact.source_metadata || {};

  const handleCopy = async (e) => {
    e.stopPropagation();
    try {
      await navigator.clipboard.writeText(code || '');
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error('Failed to copy:', err);
    }
  };

  const handleDownload = (e) => {
    e.stopPropagation();
    const extension = getFileExtension(language);
    const filename = `artifact_${artifact.id}.${extension}`;
    const blob = new Blob([code || ''], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  const getFileExtension = (lang) => {
    const extensions = {
      python: 'py',
      javascript: 'js',
      typescript: 'ts',
      java: 'java',
      go: 'go',
      rust: 'rs',
      cpp: 'cpp',
      c: 'c',
      ruby: 'rb',
      php: 'php',
      swift: 'swift',
      kotlin: 'kt',
      sql: 'sql',
      shell: 'sh',
      bash: 'sh',
      html: 'html',
      css: 'css',
      json: 'json',
      yaml: 'yaml',
      xml: 'xml',
      markdown: 'md',
    };
    return extensions[lang?.toLowerCase()] || 'txt';
  };

  const getLanguageDisplay = (lang) => {
    if (!lang || lang === 'text') return 'Plain text';
    return lang.charAt(0).toUpperCase() + lang.slice(1);
  };

  const truncateCode = (code, maxLines = 3) => {
    if (!code) return '';
    const lines = code.split('\n');
    if (lines.length <= maxLines) return code;
    return lines.slice(0, maxLines).join('\n') + '\n...';
  };

  return (
    <div className="border border-border rounded-lg mb-2 overflow-hidden">
      <div
        className="flex items-center justify-between px-3 py-2 bg-muted/50 cursor-pointer hover:bg-muted/70 transition-colors"
        onClick={onToggle}
      >
        <div className="flex items-center gap-2">
          <button
            type="button"
            className="p-0 bg-transparent border-none"
            aria-label={isExpanded ? 'Collapse' : 'Expand'}
          >
            {isExpanded ? (
              <ChevronDown size={16} className="text-muted-foreground" />
            ) : (
              <ChevronRight size={16} className="text-muted-foreground" />
            )}
          </button>
          <FileCode size={16} className="text-muted-foreground" />
          <span className="text-sm font-medium text-foreground">
            {getLanguageDisplay(language)}
          </span>
          <span className="text-xs text-muted-foreground">
            ({code?.split('\n').length || 0} lines)
          </span>
        </div>
        <div className="flex items-center gap-1">
          <button
            type="button"
            className="p-1.5 text-muted-foreground hover:text-foreground hover:bg-muted rounded transition-colors"
            onClick={handleCopy}
            title="Copy code"
          >
            {copied ? <Check size={14} /> : <Copy size={14} />}
          </button>
          <button
            type="button"
            className="p-1.5 text-muted-foreground hover:text-foreground hover:bg-muted rounded transition-colors"
            onClick={handleDownload}
            title="Download"
          >
            <Download size={14} />
          </button>
        </div>
      </div>
      {isExpanded && (
        <div className="p-3 bg-zinc-900 text-zinc-100 overflow-x-auto">
          <pre className="text-sm font-mono whitespace-pre-wrap m-0">
            <code>{code}</code>
          </pre>
        </div>
      )}
      {!isExpanded && code && (
        <div className="px-3 py-2 bg-zinc-900 text-zinc-400 text-xs font-mono overflow-hidden">
          <pre className="whitespace-pre-wrap m-0 line-clamp-2">
            {truncateCode(code, 2)}
          </pre>
        </div>
      )}
    </div>
  );
}

function GenericArtifact({ artifact }) {
  const IconComponent = getArtifactIcon(artifact.source_channel);
  const { source_metadata: metadata = {} } = artifact;

  const getTitle = () => {
    if (metadata.document_name) return metadata.document_name;
    if (metadata.filename) return metadata.filename;
    if (metadata.title) return metadata.title;
    return `Artifact #${artifact.id}`;
  };

  return (
    <div className="border border-border rounded-lg mb-2 p-3 bg-muted/30">
      <div className="flex items-center gap-2">
        <IconComponent size={16} className="text-muted-foreground" />
        <span className="text-sm font-medium text-foreground">{getTitle()}</span>
        <span className="ml-auto text-xs px-2 py-0.5 bg-muted rounded text-muted-foreground">
          {artifact.source_channel}
        </span>
      </div>
      {metadata.description && (
        <p className="text-xs text-muted-foreground mt-2">{metadata.description}</p>
      )}
    </div>
  );
}

function WorkflowArtifactsPanel({ runId }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [expandedIds, setExpandedIds] = useState(new Set());

  const loadArtifacts = useCallback(async () => {
    if (!runId) {
      setData(null);
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const response = await api.fetchWorkflowRunArtifacts(runId);
      setData(response);
    } catch (err) {
      console.error('Failed to load workflow artifacts:', err);
      setError(err.message);
      setData(null);
    } finally {
      setLoading(false);
    }
  }, [runId]);

  useEffect(() => {
    loadArtifacts();
  }, [loadArtifacts]);

  const toggleExpanded = (id) => {
    setExpandedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  };

  if (!runId) {
    return (
      <aside className="p-4 border-l border-border bg-background h-full">
        <div className="flex items-center gap-2 mb-4 text-muted-foreground">
          <Code size={18} />
          <span className="font-medium">Workflow Artifacts</span>
        </div>
        <p className="text-sm text-muted-foreground">
          Select a workflow run to see its artifacts.
        </p>
      </aside>
    );
  }

  if (loading) {
    return (
      <aside className="p-4 border-l border-border bg-background h-full">
        <div className="flex items-center gap-2 mb-4 text-foreground">
          <Code size={18} />
          <span className="font-medium">Workflow Artifacts</span>
        </div>
        <div className="flex items-center justify-center py-8">
          <div className="animate-spin h-5 w-5 border-2 border-primary border-t-transparent rounded-full" />
        </div>
      </aside>
    );
  }

  if (error) {
    return (
      <aside className="p-4 border-l border-border bg-background h-full">
        <div className="flex items-center gap-2 mb-4 text-foreground">
          <Code size={18} />
          <span className="font-medium">Workflow Artifacts</span>
        </div>
        <div className="p-3 bg-destructive/10 border border-destructive/20 rounded-lg text-sm text-destructive">
          {error}
        </div>
      </aside>
    );
  }

  const artifacts = data?.items || [];

  return (
    <aside className="p-4 border-l border-border bg-background h-full overflow-y-auto">
      <div className="flex items-center gap-2 mb-4 text-foreground">
        <Code size={18} />
        <span className="font-medium">Workflow Artifacts</span>
        {artifacts.length > 0 && (
          <span className="ml-auto text-xs text-muted-foreground bg-muted px-2 py-0.5 rounded-full">
            {artifacts.length}
          </span>
        )}
      </div>

      {data && (
        <div className="mb-4 p-2 bg-muted/30 rounded-lg text-xs">
          <div className="flex justify-between text-muted-foreground">
            <span>Workflow:</span>
            <span className="font-medium text-foreground">{data.workflow_slug}</span>
          </div>
          <div className="flex justify-between text-muted-foreground mt-1">
            <span>Status:</span>
            <span
              className={`font-medium ${
                data.status === 'completed'
                  ? 'text-green-600'
                  : data.status === 'failed'
                  ? 'text-red-600'
                  : 'text-yellow-600'
              }`}
            >
              {data.status}
            </span>
          </div>
        </div>
      )}

      {artifacts.length === 0 ? (
        <p className="text-sm text-muted-foreground">
          No artifacts yet. Workflow outputs will appear here once generated.
        </p>
      ) : (
        <div className="space-y-2">
          {artifacts.map((artifact) =>
            artifact.source_channel === 'code' ? (
              <CodeBlockArtifact
                key={artifact.id}
                artifact={artifact}
                isExpanded={expandedIds.has(artifact.id)}
                onToggle={() => toggleExpanded(artifact.id)}
              />
            ) : (
              <GenericArtifact key={artifact.id} artifact={artifact} />
            )
          )}
        </div>
      )}
    </aside>
  );
}

export default WorkflowArtifactsPanel;
