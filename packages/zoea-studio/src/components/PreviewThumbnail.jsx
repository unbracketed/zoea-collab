const SIZE_MAP = {
  xs: { width: 72, height: 56 },
  sm: { width: 112, height: 84 },
  md: { width: 160, height: 120 },
};

// Chat bubble preview component using safe SVG rendering
function ChatBubblePreview({ role, snippet, width, height, size }) {
  const isUser = role === 'user';
  const borderColor = isUser ? '#6366f1' : '#14b8a6'; // user: indigo, assistant: teal

  // Truncate snippet safely
  const maxLength = size === 'xs' ? 30 : size === 'sm' ? 50 : 80;
  const displayText = snippet && snippet.length > maxLength
    ? snippet.substring(0, maxLength) + '...'
    : snippet || 'Message';

  return (
    <svg width={width} height={height} xmlns="http://www.w3.org/2000/svg">
      <defs>
        <style>{`
          .chat-bubble-rect {
            fill: transparent;
            stroke: ${borderColor};
            stroke-width: 2;
          }
          .chat-bubble-text {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            font-size: ${size === 'xs' ? '9px' : '10px'};
            fill: currentColor;
          }
          .chat-bubble-icon {
            fill: ${borderColor};
          }
        `}</style>
      </defs>

      {/* Chat bubble background */}
      <rect className="chat-bubble-rect" x="4" y="8" width={width - 8} height={height - 16} rx="12" />

      {/* Message lines icon */}
      <g transform={`translate(12, ${height / 2 - 8})`} opacity="0.3">
        <rect className="chat-bubble-icon" x="0" y="0" width="20" height="2" rx="1" />
        <rect className="chat-bubble-icon" x="0" y="5" width="16" height="2" rx="1" />
        <rect className="chat-bubble-icon" x="0" y="10" width="18" height="2" rx="1" />
      </g>

      {/* Text snippet */}
      <foreignObject x="8" y="16" width={width - 16} height={height - 32}>
        <div
          xmlns="http://www.w3.org/1999/xhtml"
          style={{
            fontSize: size === 'xs' ? '9px' : '10px',
            lineHeight: '1.3',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            display: '-webkit-box',
            WebkitLineClamp: size === 'xs' ? 2 : 3,
            WebkitBoxOrient: 'vertical',
            color: 'var(--text-primary)',
            padding: '2px',
          }}
        >
          {displayText}
        </div>
      </foreignObject>
    </svg>
  );
}

function PreviewThumbnail({ preview, size = 'sm' }) {
  const { width, height } = SIZE_MAP[size] || SIZE_MAP.sm;

  if (!preview) {
    return <div className="preview-thumb preview-thumb-empty" style={{ width, height }} />;
  }

  // Handle chat bubble preview for conversation messages
  if (preview.type === 'chat_bubble') {
    const role = preview.metadata?.role || 'user';
    const snippet = preview.metadata?.text_snippet || preview.metadata?.preview || '';

    return (
      <div className="preview-thumb preview-thumb-chat" style={{ width, height }}>
        <ChatBubblePreview role={role} snippet={snippet} width={width} height={height} size={size} />
      </div>
    );
  }

  if (preview.url) {
    return (
      <div className="preview-thumb" style={{ width, height }}>
        <img
          src={preview.url}
          alt="Preview"
          loading="lazy"
          style={{ width: '100%', height: '100%', objectFit: 'cover', borderRadius: '0.5rem' }}
        />
      </div>
    );
  }

  if (preview.html) {
    return (
      <div
        className="preview-thumb preview-thumb-html"
        style={{ width, height }}
        dangerouslySetInnerHTML={{ __html: preview.html }}
      />
    );
  }

  const snippet = preview.metadata?.text_snippet || preview.metadata?.preview || 'Preview unavailable';
  return (
    <div className="preview-thumb preview-thumb-empty" style={{ width, height }}>
      <span className="text-text-secondary text-sm">{snippet}</span>
    </div>
  );
}

export default PreviewThumbnail;
