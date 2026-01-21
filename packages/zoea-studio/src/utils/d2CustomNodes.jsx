/**
 * Custom Node Types for ReactFlow
 *
 * Defines custom node components for D2 containers and other special node types.
 * Updated for React Flow v12 (@xyflow/react)
 */

import { Handle, Position } from '@xyflow/react';

/**
 * Container node component for D2 containers
 * Displays as a styled group with title and children area
 *
 * @param {Object} props - Node props from ReactFlow
 * @param {Object} props.data - Node data with label and other properties
 * @param {boolean} props.selected - Whether node is selected
 */
export function ContainerNode({ data, selected }) {
  const glowColor = '#5d7cfa';
  return (
    <div
      style={{
        backgroundColor: 'var(--surface)',
        border: selected ? `2px solid ${glowColor}` : '2px solid var(--border)',
        borderRadius: '8px',
        padding: '10px',
        boxSizing: 'border-box',
        minWidth: '200px',
        minHeight: '150px',
        width: '100%',
        height: '100%',
        position: 'relative',
        boxShadow: selected ? `0 0 12px ${glowColor}` : '0 2px 6px rgba(0,0,0,0.15)',
      }}
    >
      {/* Connection handles for edges */}
      <Handle type="target" position={Position.Top} />
      <Handle type="source" position={Position.Bottom} />

      {/* Container title */}
      <div
        style={{
          fontWeight: 'bold',
          fontSize: '16px',
          color: 'var(--text-primary)',
          marginBottom: '6px',
          borderBottom: '1px solid var(--border)',
          paddingBottom: '6px',
        }}
      >
        {data.label}
      </div>
    </div>
  );
}

/**
 * Default node component for regular D2 nodes
 *
 * @param {Object} props - Node props from ReactFlow
 * @param {Object} props.data - Node data with label and other properties
 * @param {boolean} props.selected - Whether node is selected
 */
export function DefaultNode({ data, selected }) {
  const glowColor = '#5d7cfa';
  return (
    <div
      style={{
        width: '100%',
        height: '100%',
        padding: '8px 10px',
        boxSizing: 'border-box',
        background: 'var(--surface)',
        border: `2px solid ${glowColor}`,
        borderRadius: '4px',
        fontSize: '16px',
        fontWeight: 600,
        color: 'var(--text-primary)',
        textAlign: 'center',
        boxShadow: selected
          ? `0 0 16px ${glowColor}`
          : `0 0 10px ${glowColor}55`,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
      }}
    >
      {/* Connection handles for edges */}
      <Handle type="target" position={Position.Top} />
      <Handle type="source" position={Position.Bottom} />

      {data.label}
    </div>
  );
}

/**
 * Node type mapping for ReactFlow
 * Maps type strings to their corresponding component
 */
export const nodeTypes = {
  group: ContainerNode,
  default: DefaultNode,
};
