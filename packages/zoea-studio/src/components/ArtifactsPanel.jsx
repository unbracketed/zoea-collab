import { useState, useEffect, useCallback } from 'react';
import { Code, Copy, Download, Check, ChevronDown, ChevronRight, FileCode, Image, FileText } from 'lucide-react';
import api from '../services/api';

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
    const filename = `code_block_${artifact.id}.${extension}`;
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
    <div className="w-full border border-border rounded-lg mb-2 overflow-hidden">
      <div
        className="flex items-center justify-between px-3 py-2 bg-muted/50 cursor-pointer hover:bg-muted/70 transition-colors"
        onClick={onToggle}
      >
        <div className="flex items-center gap-2 min-w-0 flex-1">
          <button
            type="button"
            className="p-0 bg-transparent border-none flex-shrink-0"
            aria-label={isExpanded ? 'Collapse' : 'Expand'}
          >
            {isExpanded ? (
              <ChevronDown size={16} className="text-muted-foreground" />
            ) : (
              <ChevronRight size={16} className="text-muted-foreground" />
            )}
          </button>
          <FileCode size={16} className="text-muted-foreground flex-shrink-0" />
          <span className="text-sm font-medium text-foreground truncate">
            {getLanguageDisplay(language)}
          </span>
          <span className="text-xs text-muted-foreground flex-shrink-0">
            ({code?.split('\n').length || 0} lines)
          </span>
        </div>
        <div className="flex items-center gap-1 flex-shrink-0">
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

function ToolArtifact({ artifact, isExpanded, onToggle }) {
  const { type, path, mime_type, title, content } = artifact.source_metadata || {};

  // Build URL for file-based artifacts
  const getArtifactUrl = () => {
    if (!path || path.startsWith('_inline')) return null;
    // Extract relative path from absolute path (after /media/)
    const mediaIndex = path.indexOf('/media/');
    if (mediaIndex >= 0) {
      return path.substring(mediaIndex);
    }
    // Try to extract from generated_images path
    const genIndex = path.indexOf('/generated_images/');
    if (genIndex >= 0) {
      return `/media${path.substring(genIndex)}`;
    }
    return `/media/${path.split('/').pop()}`;
  };

  const artifactUrl = getArtifactUrl();
  const isImage = type === 'image' || mime_type?.startsWith('image/');
  const isMarkdown = type === 'markdown' || mime_type === 'text/markdown';

  const getIcon = () => {
    if (isImage) return <Image size={16} className="text-muted-foreground" />;
    if (isMarkdown) return <FileText size={16} className="text-muted-foreground" />;
    return <FileCode size={16} className="text-muted-foreground" />;
  };

  const getDisplayTitle = () => {
    if (title) return title.length > 40 ? title.substring(0, 40) + '...' : title;
    if (isImage) return 'Generated Image';
    if (isMarkdown) return 'Markdown Content';
    return 'Tool Output';
  };

  return (
    <div className="w-full border border-border rounded-lg mb-2 overflow-hidden">
      <div
        className="flex items-center justify-between px-3 py-2 bg-muted/50 cursor-pointer hover:bg-muted/70 transition-colors"
        onClick={onToggle}
      >
        <div className="flex items-center gap-2 min-w-0 flex-1">
          <button
            type="button"
            className="p-0 bg-transparent border-none flex-shrink-0"
            aria-label={isExpanded ? 'Collapse' : 'Expand'}
          >
            {isExpanded ? (
              <ChevronDown size={16} className="text-muted-foreground" />
            ) : (
              <ChevronRight size={16} className="text-muted-foreground" />
            )}
          </button>
          <span className="flex-shrink-0">{getIcon()}</span>
          <span className="text-sm font-medium text-foreground truncate">
            {getDisplayTitle()}
          </span>
        </div>
        {artifactUrl && (
          <a
            href={artifactUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="p-1.5 text-muted-foreground hover:text-foreground hover:bg-muted rounded transition-colors flex-shrink-0"
            onClick={(e) => e.stopPropagation()}
            title="Open in new tab"
          >
            <Download size={14} />
          </a>
        )}
      </div>
      {isExpanded && (
        <div className="p-3 bg-zinc-900">
          {isImage && artifactUrl && (
            <img
              src={artifactUrl}
              alt={title || 'Generated image'}
              className="max-w-full max-h-64 object-contain rounded"
            />
          )}
          {isMarkdown && content && (
            <pre className="text-sm text-zinc-100 whitespace-pre-wrap m-0 overflow-x-auto">
              {content}
            </pre>
          )}
          {!isImage && !isMarkdown && (
            <p className="text-sm text-muted-foreground">
              {type} artifact: {path}
            </p>
          )}
        </div>
      )}
    </div>
  );
}

function ArtifactsPanel({ conversationId, refreshKey = 0 }) {
  const [artifacts, setArtifacts] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [expandedIds, setExpandedIds] = useState(new Set());

  const loadArtifacts = useCallback(async () => {
    if (!conversationId) {
      setArtifacts([]);
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const data = await api.fetchConversationArtifacts(conversationId);
      setArtifacts(data.items || []);
    } catch (err) {
      console.error('Failed to load artifacts:', err);
      setError(err.message);
      setArtifacts([]);
    } finally {
      setLoading(false);
    }
  }, [conversationId]);

  // Load artifacts when conversation changes or refreshKey changes
  useEffect(() => {
    loadArtifacts();
  }, [loadArtifacts, refreshKey]);

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

  if (!conversationId) {
    return (
      <aside className="p-4 bg-background h-full">
        <div className="flex items-center gap-2 mb-4 text-muted-foreground">
          <Code size={18} />
          <span className="font-medium">Artifacts</span>
        </div>
        <p className="text-sm text-muted-foreground">
          Start a conversation to see code artifacts.
        </p>
      </aside>
    );
  }

  if (loading) {
    return (
      <aside className="p-4 bg-background h-full">
        <div className="flex items-center gap-2 mb-4 text-foreground">
          <Code size={18} />
          <span className="font-medium">Artifacts</span>
        </div>
        <div className="flex items-center justify-center py-8">
          <div className="animate-spin h-5 w-5 border-2 border-primary border-t-transparent rounded-full" />
        </div>
      </aside>
    );
  }

  if (error) {
    return (
      <aside className="p-4 bg-background h-full">
        <div className="flex items-center gap-2 mb-4 text-foreground">
          <Code size={18} />
          <span className="font-medium">Artifacts</span>
        </div>
        <div className="p-3 bg-destructive/10 border border-destructive/20 rounded-lg text-sm text-destructive">
          {error}
        </div>
      </aside>
    );
  }

  const codeArtifacts = artifacts.filter((a) => a.source_channel === 'code');
  const toolArtifacts = artifacts.filter((a) => a.source_channel === 'tool');
  const totalCount = codeArtifacts.length + toolArtifacts.length;

  return (
    <aside className="p-4 bg-background h-full overflow-y-auto">
      <div className="flex items-center gap-2 mb-4 text-foreground">
        <Code size={18} />
        <span className="font-medium">Artifacts</span>
        {totalCount > 0 && (
          <span className="ml-auto text-xs text-muted-foreground bg-muted px-2 py-0.5 rounded-full">
            {totalCount}
          </span>
        )}
      </div>

      {totalCount === 0 ? (
        <p className="text-sm text-muted-foreground">
          No artifacts yet. Code blocks and generated content will appear here.
        </p>
      ) : (
        <div className="space-y-2">
          {/* Tool artifacts (images, etc.) */}
          {toolArtifacts.map((artifact) => (
            <ToolArtifact
              key={artifact.id}
              artifact={artifact}
              isExpanded={expandedIds.has(artifact.id)}
              onToggle={() => toggleExpanded(artifact.id)}
            />
          ))}
          {/* Code block artifacts */}
          {codeArtifacts.map((artifact) => (
            <CodeBlockArtifact
              key={artifact.id}
              artifact={artifact}
              isExpanded={expandedIds.has(artifact.id)}
              onToggle={() => toggleExpanded(artifact.id)}
            />
          ))}
        </div>
      )}
    </aside>
  );
}

export default ArtifactsPanel;
