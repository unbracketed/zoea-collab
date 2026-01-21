#!/usr/bin/env node
/**
 * Export Excalidraw JSON to SVG
 *
 * Usage:
 *   node export-excalidraw.mjs <input.json> <output.svg>
 *   echo '{"elements":[],"appState":{}}' | node export-excalidraw.mjs - output.svg
 *
 * Requires: @excalidraw/utils, jsdom
 */

import { readFileSync, writeFileSync } from 'fs';
import { JSDOM } from 'jsdom';

// Set up browser globals BEFORE importing @excalidraw/utils
const dom = new JSDOM('<!DOCTYPE html><html><body></body></html>', {
  url: 'http://localhost',
  pretendToBeVisual: true,
});

// Define browser globals on globalThis
Object.defineProperties(globalThis, {
  window: { value: dom.window, writable: true, configurable: true },
  document: { value: dom.window.document, writable: true, configurable: true },
  navigator: { value: dom.window.navigator, writable: true, configurable: true },
  DOMParser: { value: dom.window.DOMParser, writable: true, configurable: true },
  Element: { value: dom.window.Element, writable: true, configurable: true },
  HTMLElement: { value: dom.window.HTMLElement, writable: true, configurable: true },
  SVGElement: { value: dom.window.SVGElement, writable: true, configurable: true },
  Image: { value: dom.window.Image, writable: true, configurable: true },
  XMLSerializer: { value: dom.window.XMLSerializer, writable: true, configurable: true },
  getComputedStyle: { value: dom.window.getComputedStyle, writable: true, configurable: true },
  requestAnimationFrame: { value: (cb) => setTimeout(cb, 16), writable: true, configurable: true },
  cancelAnimationFrame: { value: clearTimeout, writable: true, configurable: true },
  devicePixelRatio: { value: 1, writable: true, configurable: true },
});

// Mock ResizeObserver
globalThis.ResizeObserver = class ResizeObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
};

// Mock FontFace
globalThis.FontFace = class FontFace {
  constructor(family, source) {
    this.family = family;
    this.status = 'loaded';
  }
  load() {
    return Promise.resolve(this);
  }
};

// Mock matchMedia
globalThis.matchMedia = () => ({
  matches: false,
  addListener: () => {},
  removeListener: () => {},
  addEventListener: () => {},
  removeEventListener: () => {},
});

// Now import @excalidraw/utils
const { exportToSvg } = await import('@excalidraw/utils');

async function main() {
  const args = process.argv.slice(2);

  if (args.length < 2) {
    console.error('Usage: export-excalidraw.mjs <input.json|-|-> <output.svg>');
    process.exit(1);
  }

  const [inputPath, outputPath] = args;

  // Read input JSON
  let jsonData;
  if (inputPath === '-') {
    // Read from stdin
    jsonData = readFileSync(0, 'utf-8');
  } else {
    jsonData = readFileSync(inputPath, 'utf-8');
  }

  let data;
  try {
    data = JSON.parse(jsonData);
  } catch (e) {
    console.error('Failed to parse JSON:', e.message);
    process.exit(1);
  }

  // Extract elements, appState, and files from the Excalidraw data
  const elements = data.elements || [];
  const appState = data.appState || {};
  const files = data.files || {};

  if (elements.length === 0) {
    console.error('No elements in diagram');
    process.exit(1);
  }

  try {
    // Export to SVG
    const svg = await exportToSvg({
      elements,
      appState: {
        ...appState,
        exportWithDarkMode: false,
        exportBackground: true,
        viewBackgroundColor: appState.viewBackgroundColor || '#ffffff',
      },
      files,
    });

    // Get the SVG string
    const serializer = new XMLSerializer();
    const svgString = serializer.serializeToString(svg);

    // Write output
    if (outputPath === '-') {
      process.stdout.write(svgString);
    } else {
      writeFileSync(outputPath, svgString);
    }

    console.error(`Exported ${elements.length} elements to ${outputPath}`);
  } catch (e) {
    console.error('Export failed:', e.message);
    if (e.stack) {
      console.error(e.stack);
    }
    process.exit(1);
  }
}

main();
