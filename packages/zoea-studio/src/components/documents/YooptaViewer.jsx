/**
 * YooptaViewer Component
 *
 * Read-only Yoopta content renderer.
 * Uses YooptaEditor in readOnly mode for consistent rendering.
 *
 * @see https://yoopta.dev/
 */

import YooptaEditor from './YooptaEditor';

/**
 * YooptaViewer - Read-only viewer for Yoopta content
 *
 * @param {Object} props
 * @param {Object|string} props.value - Yoopta JSON content (object or JSON string)
 * @param {string} props.className - Additional CSS classes
 */
export default function YooptaViewer({ value = null, className = '' }) {
  if (!value) {
    return (
      <div className={`text-text-secondary ${className}`}>
        No content available.
      </div>
    );
  }

  return (
    <YooptaEditor
      value={value}
      readOnly={true}
      className={className}
    />
  );
}
