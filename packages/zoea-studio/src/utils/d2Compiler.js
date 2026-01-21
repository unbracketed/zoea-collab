/**
 * D2 Compiler Utility
 *
 * Wraps @terrastruct/d2 WASM library for compiling D2 diagram code directly in the browser.
 * Provides geometry-complete graph data (positions, dimensions, routes) without needing a backend.
 *
 * @module d2Compiler
 */

import { D2 } from '@terrastruct/d2';

/**
 * @typedef {Object} D2CompileOptions
 * @property {'dagre' | 'elk'} [layout] - Layout engine to use (default: 'dagre')
 * @property {number} [themeID] - D2 theme id (e.g., 200 = Dark Mauve)
 */

/**
 * Compile D2 diagram code into a geometry-complete graph.
 *
 * Uses @terrastruct/d2 WASM library to run the full D2 compilation pipeline:
 * 1. Parse DSL → AST
 * 2. AST → IR normalization
 * 3. IR → Graph objects
 * 4. Measure text & shapes
 * 5. Layout orchestration (Dagre by default)
 * 6. Return complete geometry
 *
 * All nodes have absolute positions and dimensions.
 * All edges have routes (arrays of points).
 *
 * @param {string} diagramText - D2 diagram code as string
 * @param {D2CompileOptions} [options={}] - Compilation options (layout engine, etc.)
 * @returns {Promise<Object>} Promise resolving to compiled graph with geometry (CompileResponse from @terrastruct/d2)
 * @throws {Error} If compilation fails or input is invalid
 *
 * @example
 * const result = await compileD2('a -> b');
 * const graph = result.graph;
 */
export async function compileD2(diagramText, options = {}) {
  // Validate input
  if (typeof diagramText !== 'string') {
    throw new Error('diagramText must be a string');
  }

  // Empty diagram - return empty response
  if (!diagramText.trim()) {
    throw new Error('Empty D2 code provided');
  }

  try {
    // Initialize D2 compiler
    const d2 = new D2();

    // Compile with D2
    // The API accepts either:
    // 1. A string (input) with optional options
    // 2. A CompileRequest object
    const result = await d2.compile({
      fs: { index: diagramText },
      options: {
        layout: options.layout || 'dagre',
        themeID: options.themeID ?? 200,
      },
    });

    return result;
  } catch (error) {
    // Re-throw with more context
    throw new Error(
      `D2 compilation failed: ${error instanceof Error ? error.message : String(error)}`
    );
  }
}
