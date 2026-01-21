/**
 * AI Configuration Tab
 *
 * Wrapper for ModelPicker component.
 */

import ModelPicker from '../ModelPicker'

function AIConfigurationTab({ projectId, onConfigChange }) {
  return (
    <section className="bg-card rounded-xl border border-border p-6">
      <h2 className="text-lg font-semibold mb-6">AI Configuration</h2>
      <ModelPicker
        projectId={projectId}
        onConfigChange={onConfigChange}
        showApiKeyInputs={true}
        compact={true}
      />
    </section>
  )
}

export default AIConfigurationTab
