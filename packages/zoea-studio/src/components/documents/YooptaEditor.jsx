/**
 * YooptaEditor Component
 *
 * Reusable Yoopta rich text editor component with theme support.
 * Integrates with the app's light/dark mode settings and project
 * document library for image storage.
 *
 * @see https://yoopta.dev/
 */

import { forwardRef, useCallback, useEffect, useImperativeHandle, useMemo, useRef, useState } from 'react';
import YooptaEditorCore, { createYooptaEditor } from '@yoopta/editor';
import ActionMenuList, { DefaultActionMenuRender } from '@yoopta/action-menu-list';
import Toolbar, { DefaultToolbarRender } from '@yoopta/toolbar';
import { ImageIcon } from 'lucide-react';

import { plugins, MARKS } from '../../config/yooptaPlugins';
import { createProjectImagePlugin, insertImageFromLibrary } from '../../config/yooptaImagePlugin';
import { useThemeStore } from '../../stores/themeStore';
import ImagePickerModal from './ImagePickerModal';

/**
 * Get the current system color scheme preference
 */
const getSystemPreference = () => {
  if (typeof window === 'undefined') return 'light';
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
};

/**
 * YooptaEditor - A wrapper component for the Yoopta-Editor
 *
 * @param {Object} props
 * @param {Object} props.value - Initial/controlled Yoopta JSON content
 * @param {Function} props.onChange - Callback when content changes
 * @param {boolean} props.readOnly - Whether the editor is read-only
 * @param {string} props.placeholder - Placeholder text when empty
 * @param {string} props.className - Additional CSS classes
 * @param {boolean} props.autoFocus - Auto-focus on mount
 * @param {number} props.projectId - Current project ID (for image uploads)
 * @param {number} props.workspaceId - Current workspace ID (for image uploads)
 * @param {Array} props.extraPlugins - Additional Yoopta plugins to include
 * @param {boolean} props.hideImageLibraryButton - Hide the internal image library button (use ref.openImagePicker() instead)
 * @param {React.Ref} ref - Ref exposing { openImagePicker } method
 */
const YooptaEditor = forwardRef(function YooptaEditor({
  value = null,
  onChange = null,
  readOnly = false,
  placeholder = 'Start writing...',
  className = '',
  autoFocus = false,
  projectId = null,
  workspaceId = null,
  extraPlugins = [],
  hideImageLibraryButton = false,
}, ref) {

  const mode = useThemeStore((state) => state.mode);
  const [systemPreference, setSystemPreference] = useState(getSystemPreference);
  const [imagePickerOpen, setImagePickerOpen] = useState(false);
  const editorRef = useRef(null);
  const scrollRef = useRef(null);

  // Expose openImagePicker method to parent via ref
  useImperativeHandle(ref, () => ({
    openImagePicker: () => setImagePickerOpen(true),
  }), []);

  // Create editor instance
  const editor = useMemo(() => createYooptaEditor(), []);

  // Create plugins with project-aware image plugin
  const editorPlugins = useMemo(() => {
    // Replace the default Image plugin with our project-aware version
    const projectImagePlugin = createProjectImagePlugin({
      projectId,
      workspaceId,
    });

    // Filter out the default Image plugin and add our custom one
    const basePlugins = plugins.map((plugin) => {
      // Check if this is the Image plugin by its type
      if (plugin.type === 'Image') {
        return projectImagePlugin;
      }
      return plugin;
    });

    return [...basePlugins, ...extraPlugins];
  }, [projectId, workspaceId, extraPlugins]);

  // Listen for system preference changes when mode is 'auto'
  useEffect(() => {
    if (typeof window === 'undefined') return;
    const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');
    const handler = (e) => setSystemPreference(e.matches ? 'dark' : 'light');
    mediaQuery.addEventListener('change', handler);
    return () => mediaQuery.removeEventListener('change', handler);
  }, []);

  // Get the resolved theme mode (light/dark)
  const theme = mode === 'auto' ? systemPreference : mode;

  // Handle content changes
  const handleChange = useCallback(
    (newValue, options) => {
      if (!onChange) return;

      const operations = options?.operations || [];
      const isOnlySetEditorValue =
        operations.length > 0 && operations.every((op) => op.type === 'set_editor_value');

      // Ignore controlled value sync to avoid loops.
      if (isOnlySetEditorValue) return;

      // Ignore selection-only changes (prevents re-renders that can interfere with scrolling).
      const isSelectionOnly = (op) => {
        if (op.type === 'set_block_path' || op.type === 'validate_block_paths') return true;
        if (op.type !== 'set_slate') return false;

        const slateOps = op?.properties?.slateOps || [];
        return slateOps.length === 0 || slateOps.every((slateOp) => slateOp.type === 'set_selection');
      };
      if (operations.length > 0 && operations.every(isSelectionOnly)) return;

      onChange(newValue);
    },
    [onChange]
  );

  // Parse initial value if it's a string
  // Yoopta expects undefined for empty state, not empty objects
  const initialValue = useMemo(() => {
    if (!value) return undefined;
    if (typeof value === 'string') {
      try {
        const parsed = JSON.parse(value);
        // Empty object should be treated as undefined
        if (typeof parsed === 'object' && Object.keys(parsed).length === 0) {
          return undefined;
        }
        return parsed;
      } catch {
        return undefined;
      }
    }
    // Empty object should be treated as undefined
    if (typeof value === 'object' && Object.keys(value).length === 0) {
      return undefined;
    }
    return value;
  }, [value]);

  // Tools configuration
  const tools = useMemo(
    () => ({
      ActionMenu: {
        render: DefaultActionMenuRender,
        tool: ActionMenuList,
      },
      Toolbar: {
        render: DefaultToolbarRender,
        tool: Toolbar,
      },
    }),
    []
  );

  // Auto-focus on mount
  useEffect(() => {
    if (autoFocus && editor && !readOnly) {
      // Slight delay to ensure editor is mounted
      const timer = setTimeout(() => {
        editor.focus();
      }, 100);
      return () => clearTimeout(timer);
    }
  }, [autoFocus, editor, readOnly]);

  // Handle image selection from library
  const handleImageSelect = useCallback(
    ({ src, alt, width, height }) => {
      setImagePickerOpen(false);
      const schedule =
        typeof window !== 'undefined' && typeof window.requestAnimationFrame === 'function'
          ? window.requestAnimationFrame
          : (fn) => setTimeout(fn, 0);
      schedule(() => {
        insertImageFromLibrary(editor, { src, alt, width, height });
      });
    },
    [editor]
  );

  return (
    <div
      ref={editorRef}
      className={`yoopta-editor-container ${theme === 'dark' ? 'yoopta-dark' : ''} ${className}`}
      style={{
        minHeight: '200px',
        width: '100%',
        display: 'flex',
        flexDirection: 'column',
      }}
    >
      {/* Image library button - only show in edit mode with project context, unless hidden */}
      {!readOnly && projectId && workspaceId && !hideImageLibraryButton && (
        <div className="yoopta-image-library-button mb-2">
          <button
            type="button"
            onClick={() => setImagePickerOpen(true)}
            className="inline-flex items-center gap-2 px-3 py-1.5 text-sm border border-border rounded-md hover:bg-background transition-colors"
            title="Insert image from library"
          >
            <ImageIcon className="h-4 w-4" />
            <span>Insert from Library</span>
          </button>
        </div>
      )}

      <div ref={scrollRef} className="flex-1 min-h-0 overflow-auto">
        <YooptaEditorCore
          editor={editor}
          plugins={editorPlugins}
          tools={!readOnly ? tools : undefined}
          marks={MARKS}
          value={initialValue}
          onChange={handleChange}
          readOnly={readOnly}
          placeholder={placeholder}
          autoFocus={autoFocus}
          selectionBoxRoot={scrollRef}
          style={{
            width: '100%',
            paddingBottom: 120,
          }}
        />
      </div>

      {/* Image picker modal */}
      <ImagePickerModal
        isOpen={imagePickerOpen}
        onClose={() => setImagePickerOpen(false)}
        onSelect={handleImageSelect}
        projectId={projectId}
        workspaceId={workspaceId}
      />

      <style>{`
        .yoopta-editor-container {
          --yoopta-bg: var(--background, #ffffff);
          --yoopta-text: var(--foreground, #000000);
        }
        .yoopta-editor-container.yoopta-dark {
          --yoopta-bg: var(--background, #1a1a1a);
          --yoopta-text: var(--foreground, #ffffff);
        }
        .yoopta-editor-container .yoopta-editor {
          background: var(--yoopta-bg);
          color: var(--yoopta-text);
        }

        /* Block action buttons (plus, drag) - dark mode styles */
        .yoopta-editor-container.yoopta-dark .yoopta-block-actions-plus,
        .yoopta-editor-container.yoopta-dark .yoopta-block-actions-drag {
          color: var(--primary, #e07a5f);
          opacity: 0.7;
          transition: opacity 0.15s ease;
        }
        .yoopta-editor-container.yoopta-dark .yoopta-block-actions-plus:hover,
        .yoopta-editor-container.yoopta-dark .yoopta-block-actions-drag:hover {
          opacity: 1;
          color: var(--primary, #e07a5f);
        }

        /* Block options menu - dark mode styles */
        .yoopta-editor-container.yoopta-dark .yoopta-block-options-menu-content {
          background: var(--popover, #2a2a2a);
          border: 1px solid var(--border, #404040);
          box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
        }
        .yoopta-editor-container.yoopta-dark .yoopta-block-options-button {
          color: var(--foreground, #ffffff);
        }
        .yoopta-editor-container.yoopta-dark .yoopta-block-options-button:hover {
          background: var(--accent, #3a3a3a);
          color: var(--primary, #e07a5f);
        }

        /* Extended block actions - dark mode styles */
        .yoopta-editor-container.yoopta-dark .yoopta-extended-block-actions {
          color: var(--primary, #e07a5f);
        }

        /* Action menu (slash commands / block selection) - dark mode styles */
        /* Note: Action menu renders via portal outside editor, so we use .dark class on body/html */

        /* Main container */
        .dark .yoopta-action-menu-list-content {
          background: var(--popover, #2a2a2a) !important;
          border: 1px solid var(--border, #404040) !important;
          box-shadow: 0 4px 12px rgba(0, 0, 0, 0.5) !important;
          border-radius: 8px !important;
        }

        /* Menu items - override Yoopta's hardcoded colors */
        .dark [data-action-menu-item] {
          color: var(--foreground, #ffffff) !important;
        }
        .dark [data-action-menu-item]:hover,
        .dark [data-action-menu-item][aria-selected="true"] {
          background: var(--accent, #3a3a3a) !important;
        }

        /* Icon containers - override yoo-action-menu-bg-[#FFFFFF] */
        .dark .yoo-action-menu-bg-\\[\\#FFFFFF\\],
        .dark [class*="yoo-action-menu-bg-"] {
          background: var(--secondary, #333) !important;
        }
        .dark .yoo-action-menu-border-\\[\\#e5e7eb\\],
        .dark [class*="yoo-action-menu-border-"] {
          border-color: var(--border, #404040) !important;
        }

        /* Text colors */
        .dark .yoo-action-menu-font-medium {
          color: var(--foreground, #ffffff) !important;
        }
        .dark .yoo-action-menu-text-muted-foreground {
          color: var(--muted-foreground, #888) !important;
        }

        /* Hover states - override hover:yoo-action-menu-bg-[#f4f4f5] */
        .dark [data-action-menu-item]:hover .yoo-action-menu-bg-\\[\\#FFFFFF\\],
        .dark [data-action-menu-item]:hover [class*="yoo-action-menu-bg-"] {
          background: var(--secondary, #444) !important;
        }

        /* Toolbar - dark mode styles */
        .yoopta-editor-container.yoopta-dark [data-yoopta-toolbar] {
          background: var(--popover, #2a2a2a);
          border: 1px solid var(--border, #404040);
          box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
        }
        .yoopta-editor-container.yoopta-dark [data-yoopta-toolbar] button {
          color: var(--foreground, #ffffff);
        }
        .yoopta-editor-container.yoopta-dark [data-yoopta-toolbar] button:hover {
          background: var(--accent, #3a3a3a);
          color: var(--primary, #e07a5f);
        }
        .yoopta-editor-container.yoopta-dark [data-yoopta-toolbar] button[data-active="true"] {
          background: var(--primary, #e07a5f);
          color: var(--primary-foreground, #ffffff);
        }
      `}</style>
    </div>
  );
});

export default YooptaEditor;
