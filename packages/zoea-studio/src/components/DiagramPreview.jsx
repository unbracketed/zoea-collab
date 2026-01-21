/**
 * DiagramPreview Component
 *
 * Pure presentational component for displaying D2 diagrams using React Flow v12.
 * Receives pre-compiled nodes and edges and handles visualization.
 */

import React, { useCallback } from 'react';
import { ReactFlow, Background, Controls } from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import { ContainerNode, DefaultNode } from '../utils/d2CustomNodes.jsx';
import './DiagramPreview.css';

// Register custom node types
const nodeTypes = {
  group: ContainerNode,
  default: DefaultNode,
};

/**
 * DiagramPreview component
 *
 * @param {Object} props
 * @param {Array} props.nodes - React Flow nodes with positions and data
 * @param {Array} props.edges - React Flow edges connecting nodes
 * @param {boolean} [props.isLoading=false] - Loading state indicator
 */
export default function DiagramPreview({ nodes, edges, isLoading = false }) {
  /**
   * Callback fired when ReactFlow instance is initialized
   * Fits the view to show all nodes with padding
   */
  const onInit = useCallback((reactFlowInstance) => {
    // Fit view with padding on initial load
    reactFlowInstance.fitView({ padding: 0.1 });
  }, []);

  // Loading state
  if (isLoading) {
    return (
      <div className="diagram-preview-loading">
        <svg className="animate-spin h-8 w-8 text-primary" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
        </svg>
        <span className="sr-only">Loading diagram...</span>
      </div>
    );
  }

  // Empty state
  if (!nodes || nodes.length === 0) {
    return (
      <div className="diagram-preview-empty">
        <p className="text-text-secondary">No diagram to display</p>
      </div>
    );
  }

  // Main diagram render
  return (
    <div className="diagram-preview-container">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        onInit={onInit}
        fitView
        attributionPosition="bottom-left"
        nodesDraggable={true}
        nodesConnectable={false}
        elementsSelectable={true}
        defaultNodesSelectable={true}
      >
        <Background />
        <Controls />
      </ReactFlow>
    </div>
  );
}
