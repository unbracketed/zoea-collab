/**
 * D2DiagramDisplay Component
 *
 * Container component that handles D2 compilation and prepares data for visualization.
 * Compiles D2 source code, converts to React Flow format, and renders using DiagramPreview.
 */

import React, { useState, useEffect, useMemo } from 'react';
import DiagramPreview from './DiagramPreview';
import { compileD2 } from '../utils/d2Compiler';
import { convertD2ToReactFlow, convertDiagramToReactFlow } from '../utils/d2ToReactFlow';

/**
 * D2DiagramDisplay component
 *
 * Handles the complete pipeline:
 * 1. D2 source code → Compilation (d2Compiler)
 * 2. Compiled graph → React Flow format (d2ToReactFlow)
 * 3. React Flow data → Visualization (DiagramPreview)
 *
 * @param {Object} props
 * @param {string} props.d2Source - D2 diagram source code
 * @param {Object} [props.compileOptions={}] - D2 compilation options (layout: 'dagre' | 'elk')
 */
export default function D2DiagramDisplay({ d2Source, compileOptions }) {
  const [nodes, setNodes] = useState([]);
  const [edges, setEdges] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);

  // Stabilize options so useEffect doesn't retrigger on every render
  const stableOptions = useMemo(() => compileOptions || {}, [compileOptions]);

  useEffect(() => {
    // Handle empty source
    if (!d2Source) {
      setNodes([]);
      setEdges([]);
      setError(null);
      return;
    }

    /**
     * Compile D2 source and convert to React Flow format
     */
    const compileDiagram = async () => {
      setIsLoading(true);
      setError(null);

      try {
        // Step 1: Compile D2 source to graph
        const compiled = await compileD2(d2Source, stableOptions);

        console.log('Compiled D2:', {
          hasDiagram: !!compiled.diagram,
          hasGraph: !!compiled.graph,
          diagramShapes: compiled.diagram?.shapes?.length,
          diagramConnections: compiled.diagram?.connections?.length,
          graphEdges: compiled.graph?.edges?.length,
          diagram: compiled.diagram,
          graph: compiled.graph
        });

        // Step 2: Convert to React Flow format - prefer diagram for better edge support
        let flowNodes, flowEdges;

        if (compiled.diagram) {
          console.log('Using convertDiagramToReactFlow with diagram:', compiled.diagram);
          const result = convertDiagramToReactFlow(compiled.diagram);
          flowNodes = result.nodes;
          flowEdges = result.edges;
          console.log('convertDiagramToReactFlow returned:', { nodes: flowNodes.length, edges: flowEdges.length });
        } else {
          console.log('Using convertD2ToReactFlow with graph:', compiled.graph);
          const result = convertD2ToReactFlow(compiled.graph);
          flowNodes = result.nodes;
          flowEdges = result.edges;
          console.log('convertD2ToReactFlow returned:', { nodes: flowNodes.length, edges: flowEdges.length });
        }

        console.log('Final converted to ReactFlow:', {
          nodes: flowNodes.length,
          edges: flowEdges.length,
          edgeDetails: flowEdges
        });

        setNodes(flowNodes);
        setEdges(flowEdges);
      } catch (err) {
        console.error('D2 compilation error:', err);
        setError(err.message || 'Failed to compile diagram');
        setNodes([]);
        setEdges([]);
      } finally {
        setIsLoading(false);
      }
    };

    compileDiagram();
  }, [d2Source, stableOptions]);

  // Error state
  if (error) {
    return (
      <div className="d2-diagram-error">
        <strong>Error compiling diagram:</strong>
        <p>{error}</p>
      </div>
    );
  }

  // Render diagram preview
  return (
    <DiagramPreview
      nodes={nodes}
      edges={edges}
      isLoading={isLoading}
    />
  );
}
