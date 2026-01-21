/**
 * AI Response to Canvas Elements Converter
 *
 * Parses AI chat responses and converts them to appropriate
 * Excalidraw elements that can be inserted onto the canvas.
 */

import { convertToExcalidrawElements } from '@excalidraw/excalidraw';
import { parseMermaidToExcalidraw } from '@excalidraw/mermaid-to-excalidraw';

/**
 * Extract Mermaid code blocks from content
 */
function extractMermaidBlocks(content) {
  const regex = /```mermaid\n([\s\S]*?)```/g;
  const blocks = [];
  let match;

  while ((match = regex.exec(content)) !== null) {
    blocks.push(match[1].trim());
  }

  return blocks;
}

/**
 * Extract generic code blocks from content
 */
function extractCodeBlocks(content) {
  const regex = /```(?!mermaid)(\w*)\n([\s\S]*?)```/g;
  const blocks = [];
  let match;

  while ((match = regex.exec(content)) !== null) {
    blocks.push({
      language: match[1] || 'text',
      code: match[2].trim(),
    });
  }

  return blocks;
}

/**
 * Extract plain text content (removing code blocks)
 */
function extractPlainText(content) {
  let text = content.replace(/```[\s\S]*?```/g, '');
  text = text.replace(/\n{3,}/g, '\n\n').trim();
  return text;
}

/**
 * Convert Mermaid diagram to Excalidraw elements
 */
async function convertMermaidToElements(mermaidCode, basePosition) {
  try {
    const { elements, files } = await parseMermaidToExcalidraw(mermaidCode, {
      fontSize: 14,
    });

    const offsetElements = elements.map((el) => ({
      ...el,
      x: (el.x || 0) + basePosition.x,
      y: (el.y || 0) + basePosition.y,
    }));

    return { elements: offsetElements, files: files || {} };
  } catch (error) {
    console.error('Failed to convert Mermaid to Excalidraw:', error);
    return {
      elements: [
        {
          type: 'text',
          x: basePosition.x,
          y: basePosition.y,
          text: `Failed to render diagram:\n${error.message}`,
          fontSize: 12,
          strokeColor: '#e03131',
        },
      ],
      files: {},
    };
  }
}

/**
 * Create text element from plain text
 */
function createTextElement(text, position, options = {}) {
  return {
    type: 'text',
    x: position.x,
    y: position.y,
    text: text.substring(0, 2000),
    fontSize: options.fontSize || 16,
    fontFamily: options.fontFamily || 1,
    ...options,
  };
}

/**
 * Create code block element
 */
function createCodeBlockElement(code, language, position) {
  const padding = 16;
  const lineHeight = 18;
  const lines = code.split('\n');
  const maxLineLength = Math.max(...lines.map((l) => l.length));

  const width = Math.max(200, maxLineLength * 8 + padding * 2);
  const height = lines.length * lineHeight + padding * 2;

  return [
    {
      type: 'rectangle',
      x: position.x,
      y: position.y,
      width,
      height,
      backgroundColor: '#f8f9fa',
      strokeColor: '#dee2e6',
      fillStyle: 'solid',
      roughness: 0,
      roundness: { type: 3, value: 4 },
    },
    {
      type: 'text',
      x: position.x + padding,
      y: position.y + padding,
      text: code.substring(0, 1000),
      fontSize: 12,
      fontFamily: 3,
    },
  ];
}

/**
 * Main conversion function
 */
export async function convertAIResponseToElements(response, basePosition, metadata = {}) {
  const content = response.content || response.message || '';
  const allElements = [];
  const allFiles = {};

  let currentY = basePosition.y;
  const spacing = 40;

  const mermaidBlocks = extractMermaidBlocks(content);
  for (const mermaid of mermaidBlocks) {
    const { elements, files } = await convertMermaidToElements(mermaid, {
      x: basePosition.x,
      y: currentY,
    });

    elements.forEach((el) => {
      el.customData = {
        ...el.customData,
        aiGenerated: true,
        sourceType: 'mermaid',
        ...metadata,
      };
    });

    allElements.push(...elements);
    Object.assign(allFiles, files);

    if (elements.length > 0) {
      const maxY = Math.max(...elements.map((el) => (el.y || 0) + (el.height || 50)));
      currentY = maxY + spacing;
    }
  }

  const codeBlocks = extractCodeBlocks(content);
  for (const { language, code } of codeBlocks) {
    const codeElements = createCodeBlockElement(code, language, {
      x: basePosition.x,
      y: currentY,
    });

    codeElements.forEach((el) => {
      el.customData = {
        aiGenerated: true,
        sourceType: 'code',
        language,
        ...metadata,
      };
    });

    allElements.push(...codeElements);
    const height = codeElements[0]?.height || 100;
    currentY += height + spacing;
  }

  const plainText = extractPlainText(content);
  if (plainText) {
    const paragraphs = plainText.split('\n\n').filter((p) => p.trim());

    for (const para of paragraphs) {
      const textEl = createTextElement(para, {
        x: basePosition.x,
        y: currentY,
      });

      textEl.customData = {
        aiGenerated: true,
        sourceType: 'text',
        ...metadata,
      };

      allElements.push(textEl);
      const lines = Math.ceil(para.length / 60);
      currentY += lines * 24 + spacing;
    }
  }

  const convertedElements = convertToExcalidrawElements(allElements);

  return {
    elements: convertedElements,
    files: allFiles,
  };
}

/**
 * Quick text insertion
 */
export function createQuickTextElement(text, position, metadata = {}) {
  const elements = convertToExcalidrawElements([
    {
      type: 'text',
      x: position.x,
      y: position.y,
      text: text.substring(0, 2000),
      fontSize: 16,
      customData: {
        aiGenerated: true,
        ...metadata,
      },
    },
  ]);

  return elements;
}

/**
 * Detect content types in response
 */
export function detectContentTypes(content) {
  const types = [];

  if (extractMermaidBlocks(content).length > 0) {
    types.push('mermaid');
  }

  if (extractCodeBlocks(content).length > 0) {
    types.push('code');
  }

  const plainText = extractPlainText(content);
  if (plainText && plainText.length > 10) {
    types.push('text');
  }

  return types;
}
