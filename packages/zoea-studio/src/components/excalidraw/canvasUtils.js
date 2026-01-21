/**
 * Canvas Utilities for Excalidraw
 *
 * Helper functions for programmatically inserting elements
 * onto the Excalidraw canvas.
 */

import { convertToExcalidrawElements } from '@excalidraw/excalidraw';

/**
 * Convert a blob to a data URL
 */
async function blobToDataUrl(blob) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onloadend = () => resolve(reader.result);
    reader.onerror = reject;
    reader.readAsDataURL(blob);
  });
}

/**
 * Get the center position of the current viewport
 */
function getViewportCenter(excalidrawAPI) {
  const appState = excalidrawAPI.getAppState();
  const { width, height, scrollX, scrollY, zoom } = appState;

  return {
    x: (-scrollX + width / 2) / zoom.value,
    y: (-scrollY + height / 2) / zoom.value,
  };
}

/**
 * Insert an image document onto the canvas
 *
 * @param {Object} excalidrawAPI - The Excalidraw API instance
 * @param {Object} imageDocument - The image document from the project
 * @param {Object} position - Optional {x, y} position, defaults to viewport center
 */
export async function insertImageOnCanvas(excalidrawAPI, imageDocument, position = null) {
  if (!excalidrawAPI) {
    throw new Error('Excalidraw API not available');
  }

  // Get image URL
  const imageUrl = imageDocument.image_file;
  if (!imageUrl) {
    throw new Error('Document has no image file');
  }

  // Fetch image and convert to data URL
  const response = await fetch(imageUrl);
  const blob = await response.blob();
  const dataUrl = await blobToDataUrl(blob);

  // Generate unique file ID
  const fileId = crypto.randomUUID();

  // Add file to Excalidraw's file cache
  excalidrawAPI.addFiles([
    {
      id: fileId,
      dataURL: dataUrl,
      mimeType: blob.type || 'image/png',
      created: Date.now(),
    },
  ]);

  // Calculate position
  const pos = position || getViewportCenter(excalidrawAPI);

  // Calculate dimensions (preserve aspect ratio, max 400px)
  const maxSize = 400;
  let width = imageDocument.width || 200;
  let height = imageDocument.height || 150;

  if (width > maxSize || height > maxSize) {
    const ratio = Math.min(maxSize / width, maxSize / height);
    width = width * ratio;
    height = height * ratio;
  }

  // Center the image at position
  const x = pos.x - width / 2;
  const y = pos.y - height / 2;

  // Create image element
  const elements = convertToExcalidrawElements([
    {
      type: 'image',
      x,
      y,
      width,
      height,
      fileId,
      customData: {
        projectDocumentId: imageDocument.id,
        projectDocumentName: imageDocument.name,
        documentType: 'Image',
      },
    },
  ]);

  // Add to scene
  const currentElements = excalidrawAPI.getSceneElements();
  excalidrawAPI.updateScene({
    elements: [...currentElements, ...elements],
  });

  // Select the new element
  const newElement = elements[0];
  if (newElement) {
    excalidrawAPI.updateScene({
      appState: {
        selectedElementIds: { [newElement.id]: true },
      },
    });
  }

  return elements;
}

/**
 * Insert a text document as a text element or linked frame
 *
 * @param {Object} excalidrawAPI - The Excalidraw API instance
 * @param {Object} document - The document from the project
 * @param {Object} position - Optional {x, y} position
 * @param {string} mode - 'text' for text element, 'frame' for linked frame
 */
export function insertTextDocumentOnCanvas(
  excalidrawAPI,
  document,
  position = null,
  mode = 'frame'
) {
  if (!excalidrawAPI) {
    throw new Error('Excalidraw API not available');
  }

  const pos = position || getViewportCenter(excalidrawAPI);

  let elements;

  if (mode === 'text' && document.content) {
    // Truncate content for canvas display
    const maxLength = 500;
    const truncatedContent =
      document.content.length > maxLength
        ? document.content.substring(0, maxLength) + '...'
        : document.content;

    elements = convertToExcalidrawElements([
      {
        type: 'text',
        x: pos.x,
        y: pos.y,
        text: truncatedContent,
        fontSize: 14,
        customData: {
          projectDocumentId: document.id,
          projectDocumentName: document.name,
          documentType: document.document_type,
          isTruncated: document.content.length > maxLength,
          isDocumentLink: true,
        },
      },
    ]);
  } else {
    // Create a frame as a document link placeholder
    elements = convertToExcalidrawElements([
      {
        type: 'frame',
        x: pos.x - 100,
        y: pos.y - 50,
        width: 200,
        height: 100,
        name: document.name,
        customData: {
          projectDocumentId: document.id,
          projectDocumentName: document.name,
          documentType: document.document_type,
          isDocumentLink: true,
        },
      },
    ]);
  }

  // Add to scene
  const currentElements = excalidrawAPI.getSceneElements();
  excalidrawAPI.updateScene({
    elements: [...currentElements, ...elements],
  });

  return elements;
}

/**
 * Insert AI-generated elements onto the canvas
 *
 * @param {Object} excalidrawAPI - The Excalidraw API instance
 * @param {Array} elements - Array of element skeletons to insert
 * @param {Object} position - Base position for elements
 * @param {Object} metadata - AI metadata to attach to elements
 */
export function insertAIGeneratedElements(
  excalidrawAPI,
  elementSkeletons,
  position = null,
  metadata = {}
) {
  if (!excalidrawAPI || !elementSkeletons?.length) {
    return [];
  }

  const pos = position || getViewportCenter(excalidrawAPI);

  // Add position offset and metadata to each element
  const adjustedSkeletons = elementSkeletons.map((el, index) => ({
    ...el,
    x: (el.x || 0) + pos.x,
    y: (el.y || 0) + pos.y + index * 20, // Stack vertically if no position
    customData: {
      ...el.customData,
      aiGenerated: true,
      ...metadata,
    },
  }));

  const elements = convertToExcalidrawElements(adjustedSkeletons);

  // Add to scene
  const currentElements = excalidrawAPI.getSceneElements();
  excalidrawAPI.updateScene({
    elements: [...currentElements, ...elements],
  });

  return elements;
}

/**
 * Create an AI prompt frame on the canvas
 *
 * @param {Object} excalidrawAPI - The Excalidraw API instance
 * @param {Object} position - Position for the frame
 * @param {string} initialPrompt - Optional initial prompt text
 */
export function createAIPromptFrame(excalidrawAPI, position = null, initialPrompt = '') {
  if (!excalidrawAPI) {
    throw new Error('Excalidraw API not available');
  }

  const pos = position || getViewportCenter(excalidrawAPI);

  const elements = convertToExcalidrawElements([
    {
      type: 'frame',
      x: pos.x - 200,
      y: pos.y - 150,
      width: 400,
      height: 300,
      name: 'AI Prompt',
      customData: {
        isAIPromptFrame: true,
        prompt: initialPrompt,
        status: 'idle', // idle, pending, complete, error
        conversationId: null,
      },
    },
  ]);

  // Add to scene
  const currentElements = excalidrawAPI.getSceneElements();
  excalidrawAPI.updateScene({
    elements: [...currentElements, ...elements],
  });

  // Select the new frame
  const newFrame = elements[0];
  if (newFrame) {
    excalidrawAPI.updateScene({
      appState: {
        selectedElementIds: { [newFrame.id]: true },
      },
    });
  }

  return elements[0];
}

/**
 * Update an AI prompt frame's status and optionally add child elements
 *
 * @param {Object} excalidrawAPI - The Excalidraw API instance
 * @param {string} frameId - The frame element ID
 * @param {Object} updates - Updates to apply { status, prompt, childElements }
 */
export function updateAIPromptFrame(excalidrawAPI, frameId, updates) {
  if (!excalidrawAPI) return;

  const elements = excalidrawAPI.getSceneElements();
  const frameIndex = elements.findIndex((el) => el.id === frameId);

  if (frameIndex === -1) return;

  const frame = elements[frameIndex];

  // Update frame customData
  const updatedFrame = {
    ...frame,
    customData: {
      ...frame.customData,
      ...updates,
    },
  };

  const newElements = [...elements];
  newElements[frameIndex] = updatedFrame;

  excalidrawAPI.updateScene({ elements: newElements });
}

/**
 * Find element at a given position (for click handling)
 *
 * @param {Object} excalidrawAPI - The Excalidraw API instance
 * @param {Object} position - {x, y} position in canvas coordinates
 */
export function getElementAtPosition(excalidrawAPI, position) {
  if (!excalidrawAPI) return null;

  const elements = excalidrawAPI.getSceneElements();
  const { x, y } = position;

  // Simple bounding box check (reverse order to get topmost element)
  for (let i = elements.length - 1; i >= 0; i--) {
    const el = elements[i];
    if (el.isDeleted) continue;

    const elX = el.x;
    const elY = el.y;
    const elWidth = el.width || 0;
    const elHeight = el.height || 0;

    if (x >= elX && x <= elX + elWidth && y >= elY && y <= elY + elHeight) {
      return el;
    }
  }

  return null;
}
