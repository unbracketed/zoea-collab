/**
 * D2-to-ReactFlow Converter
 *
 * Converts d2lib.Compile output (from @terrastruct/d2) to ReactFlow-compatible data structures.
 * All geometry (positions, dimensions, routes) comes directly from D2's layout engine.
 *
 * Based on the approach documented in d2-parsing-to-geometry-generation.md:
 * - Use graph.objects for nodes with obj.box.topLeft for positions
 * - Use graph.edges for edges with edge.route for polylines
 *
 * @module d2ToReactFlow
 * @version 3.0.0 (adapted for React Flow v12)
 */

import { MarkerType } from '@xyflow/react';

// ============================================================================
// TYPE DEFINITIONS (JSDoc)
// ============================================================================

/**
 * @typedef {Object} ReactFlowData
 * @property {Array<Object>} nodes - ReactFlow nodes
 * @property {Array<Object>} edges - ReactFlow edges
 */

/**
 * @typedef {Object} ReactFlowNodeData
 * @property {string} label - Node label text
 * @property {string} d2Id - Original D2 node ID
 * @property {string} shape - D2 shape type
 * @property {boolean} [isContainer] - Whether node is a container/group
 */

// ============================================================================
// MAIN CONVERTER FUNCTIONS
// ============================================================================

/**
 * Convert D2 graph to ReactFlow data using graph.objects.
 *
 * This follows the approach from d2-parsing-to-geometry-generation.md:
 * graph.objects contains fully positioned nodes with box.topLeft coordinates.
 *
 * @param {Object} graph - D2 graph from compile response
 * @returns {ReactFlowData} ReactFlow-compatible nodes and edges
 * @throws {Error} If graph is invalid or missing objects
 */
export function convertD2ToReactFlow(graph) {
  // Validate input
  if (!graph || !graph.objects) {
    throw new Error('Invalid D2 graph: missing objects array');
  }

  // Convert using graph.objects (has geometry)
  const nodes = convertGraphObjects(graph.objects);
  const edges = convertGraphEdges(graph.edges || []);

  return { nodes, edges };
}

/**
 * Convert D2 diagram to ReactFlow data using diagram.shapes.
 *
 * Alternative approach using the rendered diagram output.
 * diagram.shapes contains positioned shapes with pos.x, pos.y.
 *
 * @param {Object} diagram - D2 diagram from compile response
 * @returns {ReactFlowData} ReactFlow-compatible nodes and edges
 * @throws {Error} If diagram is invalid or missing shapes
 */
export function convertDiagramToReactFlow(diagram) {
  // Validate input
  if (!diagram || !diagram.shapes) {
    throw new Error('Invalid D2 diagram: missing shapes array');
  }

  // Convert using diagram.shapes (render-ready positions)
  const nodes = convertDiagramShapes(diagram.shapes);
  const edges = convertDiagramConnections(diagram.connections || []);

  return { nodes, edges };
}

// ============================================================================
// GRAPH.OBJECTS CONVERSION (Preferred)
// ============================================================================

/**
 * Convert graph.objects to ReactFlow nodes.
 *
 * Uses geometry from D2's layout engine:
 * - obj.box.TopLeft.x, obj.box.TopLeft.y for position
 * - obj.box.Width, obj.box.Height for dimensions
 * - obj.parent for hierarchy
 *
 * @param {Array<Object>} objects - D2 graph objects array
 * @returns {Array<Object>} ReactFlow nodes
 */
function convertGraphObjects(objects) {
  const nodes = [];

  for (const obj of objects) {
    if (!obj) continue;

    // Skip root container (empty ID or "root")
    if (!obj.id || obj.id === '' || obj.id === 'root') {
      continue;
    }

    // Skip objects without geometry
    if (!obj.box?.TopLeft || obj.box.Width === undefined || obj.box.Height === undefined) {
      continue;
    }

    // Determine if this is a container (has children)
    const isContainer = objects.some(child => {
      return child?.parent?.id === obj.id;
    });

    const node = {
      id: obj.id,
      type: isContainer ? 'group' : 'default',
      data: {
        label: obj.attributes?.label?.value || obj.id,
        d2Id: obj.id,
        shape: obj.attributes?.shape?.value || 'rectangle',
        isContainer,
      },
      position: {
        x: obj.box.TopLeft.x,
        y: obj.box.TopLeft.y,
      },
      // React Flow v12: Use measured instead of width/height props
      measured: {
        width: obj.box.Width,
        height: obj.box.Height,
      },
      style: {
        width: obj.box.Width,
        height: obj.box.Height,
      },
    };

    // Set parent relationship if parent exists
    if (obj.parent?.id) {
      node.parentId = obj.parent.id;
      node.extent = 'parent';
    }

    // Z-index: containers below (0), regular nodes above (1)
    node.zIndex = isContainer ? 0 : 1;

    nodes.push(node);
  }

  return nodes;
}

/**
 * Convert graph.edges to ReactFlow edges.
 *
 * @param {Array<Object>} edges - D2 graph edges array
 * @returns {Array<Object>} ReactFlow edges
 */
function convertGraphEdges(edges) {
  const reactFlowEdges = [];

  for (const edge of edges) {
    if (!edge) continue;

    // D2 graph edges don't have src/dst directly - they're in references
    // Extract source and target from edge references
    let sourceId, targetId;

    if (edge.references && edge.references.length > 0) {
      const ref = edge.references[0];
      // The reference contains the edge connection info
      if (ref.src_arrow !== undefined || ref.dst_arrow !== undefined) {
        // This reference has the connection, but we need to find src/dst from the graph
        // For now, we'll use the edge index to derive IDs from the graph objects
        console.warn('Edge references found but missing src/dst mapping:', edge);
      }

      // Try to get edge ID from reference
      if (ref.edge?.src && ref.edge?.dst) {
        sourceId = ref.edge.src;
        targetId = ref.edge.dst;
      } else if (ref.map_key_edge_index !== undefined) {
        // Edge is defined by map key, we need to look at the parent graph
        // This is a limitation - we can't easily resolve without the full graph context
        console.warn('Edge defined by map_key_edge_index, cannot resolve without graph context');
        continue;
      }
    }

    // Fallback: try direct src/dst properties
    if (!sourceId && edge.src?.id) {
      sourceId = edge.src.id;
    }
    if (!targetId && edge.dst?.id) {
      targetId = edge.dst.id;
    }

    // Skip edges we couldn't resolve
    if (!sourceId || !targetId) {
      console.warn('Skipping edge - could not determine source/target:', edge);
      continue;
    }

    // Generate edge ID from references or fallback
    const edgeId = edge.references?.[0]?.edge?.id || `${sourceId}-${targetId}`;

    const reactFlowEdge = {
      id: edgeId,
      source: sourceId,
      target: targetId,
      label: edge.attributes?.label?.value,
      // Store D2 route for potential custom edge rendering
      data: {
        route: edge.route,
        isCurve: edge.isCurve,
      },
    };

    // Add arrow markers based on D2 edge direction
    if (edge.dst_arrow) {
      reactFlowEdge.markerEnd = {
        type: MarkerType.ArrowClosed,
      };
    }

    if (edge.src_arrow) {
      reactFlowEdge.markerStart = {
        type: MarkerType.ArrowClosed,
      };
    }

    reactFlowEdges.push(reactFlowEdge);
  }

  return reactFlowEdges;
}

// ============================================================================
// DIAGRAM.SHAPES CONVERSION (Alternative)
// ============================================================================

/**
 * Convert diagram.shapes to ReactFlow nodes.
 *
 * Uses rendered shape positions from diagram:
 * - shape.pos.x, shape.pos.y for position
 * - shape.width, shape.height for dimensions
 *
 * @param {Array<Object>} shapes - D2 diagram shapes array
 * @returns {Array<Object>} ReactFlow nodes
 */
function convertDiagramShapes(shapes) {
  const nodes = [];

  for (const shape of shapes) {
    if (!shape || !shape.id) continue;

    // Skip root shape if it exists
    if (shape.id === 'root') continue;

    // Extract label from Shape
    const label = shape.label || shape.id;

    const node = {
      id: shape.id,
      type: shape.type === 'group' ? 'group' : 'default',
      data: {
        label,
        d2Id: shape.id,
        shape: shape.type,
        isContainer: shape.type === 'group',
      },
      position: {
        x: shape.pos.x,
        y: shape.pos.y,
      },
      // React Flow v12: Use measured instead of width/height props
      measured: {
        width: shape.width,
        height: shape.height,
      },
      style: {
        width: shape.width,
        height: shape.height,
      },
      zIndex: shape.zIndex,
    };

    nodes.push(node);
  }

  return nodes;
}

/**
 * Convert diagram.connections to ReactFlow edges.
 *
 * @param {Array<Object>} connections - D2 diagram connections array
 * @returns {Array<Object>} ReactFlow edges
 */
function convertDiagramConnections(connections) {
  const reactFlowEdges = [];

  for (const connection of connections) {
    if (!connection || !connection.id) continue;

    const reactFlowEdge = {
      id: connection.id,
      source: connection.src,
      target: connection.dst,
      label: connection.label,
      data: {
        route: connection.route,
        isCurve: connection.isCurve,
      },
    };

    // Add arrow markers
    if (connection.dstArrow && connection.dstArrow !== 'none') {
      reactFlowEdge.markerEnd = {
        type: MarkerType.ArrowClosed,
      };
    }

    if (connection.srcArrow && connection.srcArrow !== 'none') {
      reactFlowEdge.markerStart = {
        type: MarkerType.ArrowClosed,
      };
    }

    reactFlowEdges.push(reactFlowEdge);
  }

  return reactFlowEdges;
}

// ============================================================================
// EXPORTS
// ============================================================================

export default convertD2ToReactFlow;
