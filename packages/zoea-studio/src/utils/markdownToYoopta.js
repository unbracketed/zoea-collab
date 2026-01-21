/**
 * Markdown to Yoopta JSON Conversion Utility
 *
 * Converts Markdown content to Yoopta-Editor JSON format
 * using @yoopta/exports deserializer.
 *
 * @see https://yoopta.dev/
 */

import { createYooptaEditor } from '@yoopta/editor';
import { markdown } from '@yoopta/exports';
import { plugins } from '../config/yooptaPlugins';

/**
 * Convert a markdown string to Yoopta JSON content.
 *
 * @param {string} markdownContent - The markdown string to convert
 * @returns {Object} The Yoopta JSON content
 * @throws {Error} If conversion fails
 */
export function markdownToYoopta(markdownContent) {
  if (!markdownContent || typeof markdownContent !== 'string') {
    throw new Error('Invalid markdown content: must be a non-empty string');
  }

  // Create a temporary editor instance with plugins
  const editor = createYooptaEditor();

  // Initialize the editor with plugins (required for deserialize)
  // We need to manually set up the plugin configuration
  const pluginInstances = plugins.reduce((acc, plugin) => {
    if (plugin && plugin.type) {
      acc[plugin.type] = plugin;
    } else if (plugin && typeof plugin === 'function') {
      // Handle function-style plugins
      const instance = plugin;
      if (instance.type) {
        acc[instance.type] = instance;
      }
    }
    return acc;
  }, {});

  // Set plugins on the editor
  editor.plugins = pluginInstances;

  try {
    // Deserialize markdown to Yoopta content
    const yooptaContent = markdown.deserialize(editor, markdownContent);

    if (!yooptaContent || Object.keys(yooptaContent).length === 0) {
      // If deserialize returns empty, create a minimal paragraph
      return createEmptyContent();
    }

    return yooptaContent;
  } catch (error) {
    console.error('Markdown to Yoopta conversion failed:', error);
    throw new Error(`Failed to convert markdown: ${error.message}`);
  }
}

/**
 * Create minimal empty Yoopta content with a single paragraph.
 */
function createEmptyContent() {
  const blockId = `block-${Date.now()}`;
  const elemId = `elem-${Date.now()}`;

  return {
    [blockId]: {
      id: blockId,
      meta: { order: 0 },
      type: 'Paragraph',
      value: [
        {
          id: elemId,
          type: 'paragraph',
          children: [{ text: '' }],
        },
      ],
    },
  };
}

export default markdownToYoopta;
