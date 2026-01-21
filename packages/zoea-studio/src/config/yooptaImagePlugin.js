/**
 * Custom Yoopta Image Plugin Configuration
 *
 * Extends the default @yoopta/image plugin to integrate with
 * the project/workspace document library for image storage.
 */

import Image, { ImageCommands } from '@yoopta/image';
import api from '../services/api';

/**
 * Create a project-aware Image plugin instance.
 *
 * @param {Object} options
 * @param {number} options.projectId - Current project ID
 * @param {number} options.workspaceId - Current workspace ID
 * @returns {YooptaPlugin} Configured Image plugin
 */
export function createProjectImagePlugin({ projectId, workspaceId }) {
  // If no project/workspace context, return default plugin with no upload
  if (!projectId || !workspaceId) {
    return Image.extend({
      options: {
        onUpload: async () => {
          throw new Error('Project and workspace required to upload images');
        },
      },
    });
  }

  return Image.extend({
    options: {
      /**
       * Handle image file upload - saves to backend as Image document
       */
      onUpload: async (file) => {
        try {
          const response = await api.createImageDocument({
            name: file.name,
            description: '',
            project_id: projectId,
            workspace_id: workspaceId,
            file,
          });

          // Return in Yoopta's expected ImageUploadResponse format
          return {
            src: response.image_file,
            alt: response.name || file.name,
            fit: 'contain',
            sizes:
              response?.width && response?.height
                ? { width: response.width, height: response.height }
                : undefined,
          };
        } catch (error) {
          console.error('Failed to upload image:', error);
          throw error;
        }
      },

      /**
       * Handle upload errors
       */
      onError: (error) => {
        console.error('Image upload error:', error);
      },

      /**
       * Accept common image formats
       */
      accept: 'image/jpeg,image/png,image/gif,image/webp,image/svg+xml',
    },
  });
}

/**
 * Insert an image from the library into the Yoopta editor.
 *
 * @param {YooptaEditor} editor - The Yoopta editor instance
 * @param {Object} imageData - Image data from library
 * @param {string} imageData.src - Image URL
 * @param {string} imageData.alt - Image alt text
 * @param {number} [imageData.width] - Image width in pixels
 * @param {number} [imageData.height] - Image height in pixels
 */
export function insertImageFromLibrary(editor, { src, alt, width, height } = {}) {
  if (!editor || !src) {
    console.error('Editor and image source are required');
    return null;
  }

  const sizes = width && height ? { width, height } : { width: 650, height: 500 };
  const imageElement = ImageCommands.buildImageElements(editor, {
    props: {
      src,
      alt: alt || '',
      fit: 'contain',
      sizes,
    },
  });

  // Avoid focusing the void Image node directly (it can interfere with scrolling in some layouts).
  // Insert the image, then place the caret in a following Paragraph block.
  const blockId = editor.insertBlock('Image', {
    focus: false,
    blockData: {
      value: [imageElement],
      meta: { align: 'center', depth: 0 },
    },
  });

  try {
    const inserted = editor.getBlock({ id: blockId });
    const nextAt = inserted?.meta?.order;
    if (typeof nextAt === 'number') {
      editor.insertBlock('Paragraph', { at: nextAt + 1, focus: true });
    } else {
      editor.insertBlock('Paragraph', { focus: true });
    }
  } catch (error) {
    console.warn('[Yoopta] Failed to move cursor after image insert:', error);
  }

  return blockId;
}

export default createProjectImagePlugin;
