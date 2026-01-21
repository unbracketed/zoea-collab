/**
 * Agent Tools Tab
 *
 * Wrapper for ToolSettings component.
 */

import ToolSettings from '../ToolSettings'

function AgentToolsTab({ projectId }) {
  return (
    <section className="bg-card rounded-xl border border-border p-6">
      <h2 className="text-lg font-semibold mb-6">Agent Tools</h2>
      <ToolSettings projectId={projectId} />
    </section>
  )
}

export default AgentToolsTab
