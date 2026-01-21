/**
 * Model Picker Component
 *
 * Allows users to select an LLM provider and model for their project.
 * Optionally allows entering API keys for providers that require them.
 */

import { useCallback, useEffect, useState } from 'react'
import { ChevronDown, Key, Check, AlertCircle, Server, Cpu, Sparkles } from 'lucide-react'
import api from '../services/api'

// Provider icons by name
const PROVIDER_ICONS = {
  openai: Sparkles,
  gemini: Sparkles,
  local: Server,
}

// Provider display names
const PROVIDER_DISPLAY_NAMES = {
  openai: 'OpenAI',
  gemini: 'Google Gemini',
  local: 'Local Model',
}

function ModelPicker({
  projectId,
  initialConfig = null,
  onConfigChange = () => {},
  showApiKeyInputs = true,
  compact = false,
}) {
  // Provider and model state
  const [providers, setProviders] = useState([])
  const [models, setModels] = useState([])
  const [selectedProvider, setSelectedProvider] = useState('')
  const [selectedModel, setSelectedModel] = useState('')
  const [defaultProvider, setDefaultProvider] = useState(null)

  // API key state
  const [openaiKey, setOpenaiKey] = useState('')
  const [geminiKey, setGeminiKey] = useState('')
  const [localEndpoint, setLocalEndpoint] = useState('')
  const [hasOpenaiKey, setHasOpenaiKey] = useState(false)
  const [hasGeminiKey, setHasGeminiKey] = useState(false)

  // Effective values (what will actually be used)
  const [effectiveProvider, setEffectiveProvider] = useState('')
  const [effectiveModel, setEffectiveModel] = useState('')

  // UI state
  const [loading, setLoading] = useState(true)
  const [loadingModels, setLoadingModels] = useState(false)
  const [error, setError] = useState(null)
  const [validatingKey, setValidatingKey] = useState(null)
  const [keyValidation, setKeyValidation] = useState({})

  // Load providers on mount
  useEffect(() => {
    loadProviders()
  }, [])

  // Load project config when projectId changes
  useEffect(() => {
    if (projectId) {
      loadProjectConfig()
    }
  }, [projectId])

  // Load models when provider changes
  useEffect(() => {
    if (selectedProvider) {
      loadModels(selectedProvider)
    } else {
      setModels([])
    }
  }, [selectedProvider])

  // Notify parent of changes
  useEffect(() => {
    onConfigChange({
      provider: selectedProvider,
      model: selectedModel,
      openaiKey: openaiKey || undefined,
      geminiKey: geminiKey || undefined,
      localEndpoint: localEndpoint || undefined,
      effectiveProvider,
      effectiveModel,
    })
  }, [selectedProvider, selectedModel, openaiKey, geminiKey, localEndpoint, effectiveProvider, effectiveModel])

  const loadProviders = async () => {
    try {
      const data = await api.fetchLLMProviders()
      setProviders(data.providers || [])
      setDefaultProvider(data.default_provider)
    } catch (err) {
      console.error('Failed to load providers:', err)
      setError('Failed to load AI providers')
    } finally {
      setLoading(false)
    }
  }

  const loadProjectConfig = async () => {
    try {
      const config = await api.fetchProjectLLMConfig(projectId)
      setSelectedProvider(config.llm_provider || '')
      setSelectedModel(config.llm_model_id || '')
      setLocalEndpoint(config.local_model_endpoint || '')
      setHasOpenaiKey(config.has_openai_key || false)
      setHasGeminiKey(config.has_gemini_key || false)
      setEffectiveProvider(config.effective_provider || '')
      setEffectiveModel(config.effective_model || '')
    } catch (err) {
      console.error('Failed to load project LLM config:', err)
    }
  }

  const loadModels = async (providerName) => {
    setLoadingModels(true)
    try {
      const data = await api.fetchProviderModels(providerName)
      setModels(data.models || [])
    } catch (err) {
      console.error(`Failed to load models for ${providerName}:`, err)
      setModels([])
    } finally {
      setLoadingModels(false)
    }
  }

  const handleProviderChange = useCallback((e) => {
    const provider = e.target.value
    setSelectedProvider(provider)
    setSelectedModel('') // Reset model when provider changes
  }, [])

  const handleModelChange = useCallback((e) => {
    setSelectedModel(e.target.value)
  }, [])

  const validateApiKey = async (provider, apiKey) => {
    if (!apiKey) {
      setKeyValidation((prev) => ({ ...prev, [provider]: null }))
      return
    }

    setValidatingKey(provider)
    try {
      const result = await api.validateLLMCredentials({ provider, api_key: apiKey })
      setKeyValidation((prev) => ({
        ...prev,
        [provider]: result.valid ? 'valid' : 'invalid',
      }))
    } catch (err) {
      setKeyValidation((prev) => ({ ...prev, [provider]: 'error' }))
    } finally {
      setValidatingKey(null)
    }
  }

  const handleOpenaiKeyBlur = () => {
    if (openaiKey) {
      validateApiKey('openai', openaiKey)
    }
  }

  const handleGeminiKeyBlur = () => {
    if (geminiKey) {
      validateApiKey('gemini', geminiKey)
    }
  }

  const getProviderIcon = (providerName) => {
    const Icon = PROVIDER_ICONS[providerName] || Cpu
    return <Icon className="h-4 w-4" />
  }

  const getProviderDisplayName = (providerName) => {
    return PROVIDER_DISPLAY_NAMES[providerName] || providerName
  }

  const renderKeyValidationIcon = (provider) => {
    const status = keyValidation[provider]
    if (validatingKey === provider) {
      return <span className="text-text-secondary text-sm">Validating...</span>
    }
    if (status === 'valid') {
      return <Check className="h-4 w-4 text-green-500" />
    }
    if (status === 'invalid' || status === 'error') {
      return <AlertCircle className="h-4 w-4 text-red-500" />
    }
    return null
  }

  if (loading) {
    return (
      <div className="animate-pulse space-y-3">
        <div className="h-10 bg-background rounded-lg" />
        <div className="h-10 bg-background rounded-lg" />
      </div>
    )
  }

  if (error) {
    return (
      <div className="p-3 rounded-lg bg-red-500/10 text-red-500 text-sm">
        {error}
      </div>
    )
  }

  return (
    <div className={`space-y-4 ${compact ? 'space-y-3' : ''}`}>
      {/* Provider Selection */}
      <div>
        <label className="block text-sm font-medium mb-2">
          AI Provider
        </label>
        <div className="relative">
          <select
            value={selectedProvider}
            onChange={handleProviderChange}
            className="w-full appearance-none px-3 py-2 pl-9 pr-10 rounded-lg border border-border bg-background focus:ring-2 focus:ring-primary/50 focus:border-primary outline-none transition-colors"
          >
            <option value="">Use default ({getProviderDisplayName(defaultProvider)})</option>
            {providers.map((provider) => (
              <option key={provider.name} value={provider.name}>
                {provider.display_name}
              </option>
            ))}
          </select>
          <div className="absolute left-3 top-1/2 -translate-y-1/2 text-text-secondary">
            {selectedProvider ? getProviderIcon(selectedProvider) : <Cpu className="h-4 w-4" />}
          </div>
          <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 h-4 w-4 text-text-secondary pointer-events-none" />
        </div>
        {!selectedProvider && effectiveProvider && (
          <p className="mt-1 text-xs text-text-secondary">
            Currently using: {getProviderDisplayName(effectiveProvider)}
          </p>
        )}
      </div>

      {/* Model Selection */}
      <div>
        <label className="block text-sm font-medium mb-2">
          Model
        </label>
        <div className="relative">
          <select
            value={selectedModel}
            onChange={handleModelChange}
            disabled={loadingModels}
            className="w-full appearance-none px-3 py-2 pr-10 rounded-lg border border-border bg-background focus:ring-2 focus:ring-primary/50 focus:border-primary outline-none transition-colors disabled:opacity-50"
          >
            <option value="">
              {loadingModels ? 'Loading models...' : `Use default (${effectiveModel || 'auto'})`}
            </option>
            {models.map((model) => (
              <option key={model.model_id} value={model.model_id}>
                {model.display_name}
                {model.description ? ` - ${model.description}` : ''}
              </option>
            ))}
          </select>
          <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 h-4 w-4 text-text-secondary pointer-events-none" />
        </div>
        {!selectedModel && effectiveModel && (
          <p className="mt-1 text-xs text-text-secondary">
            Currently using: {effectiveModel}
          </p>
        )}
      </div>

      {/* API Key Inputs */}
      {showApiKeyInputs && (
        <>
          {/* OpenAI API Key */}
          {(selectedProvider === 'openai' || (!selectedProvider && effectiveProvider === 'openai')) && (
            <div>
              <label className="block text-sm font-medium mb-2">
                <div className="flex items-center gap-2">
                  <Key className="h-4 w-4" />
                  OpenAI API Key
                  {hasOpenaiKey && !openaiKey && (
                    <span className="text-xs text-green-500">(configured)</span>
                  )}
                </div>
              </label>
              <div className="relative">
                <input
                  type="password"
                  value={openaiKey}
                  onChange={(e) => setOpenaiKey(e.target.value)}
                  onBlur={handleOpenaiKeyBlur}
                  placeholder={hasOpenaiKey ? '••••••••••••••••' : 'sk-...'}
                  className="w-full px-3 py-2 pr-10 rounded-lg border border-border bg-background focus:ring-2 focus:ring-primary/50 focus:border-primary outline-none transition-colors"
                />
                <div className="absolute right-3 top-1/2 -translate-y-1/2">
                  {renderKeyValidationIcon('openai')}
                </div>
              </div>
              <p className="mt-1 text-xs text-text-secondary">
                {hasOpenaiKey
                  ? 'Enter a new key to replace the existing one'
                  : 'Leave empty to use the app default key'}
              </p>
            </div>
          )}

          {/* Gemini API Key */}
          {(selectedProvider === 'gemini' || (!selectedProvider && effectiveProvider === 'gemini')) && (
            <div>
              <label className="block text-sm font-medium mb-2">
                <div className="flex items-center gap-2">
                  <Key className="h-4 w-4" />
                  Gemini API Key
                  {hasGeminiKey && !geminiKey && (
                    <span className="text-xs text-green-500">(configured)</span>
                  )}
                </div>
              </label>
              <div className="relative">
                <input
                  type="password"
                  value={geminiKey}
                  onChange={(e) => setGeminiKey(e.target.value)}
                  onBlur={handleGeminiKeyBlur}
                  placeholder={hasGeminiKey ? '••••••••••••••••' : 'AIza...'}
                  className="w-full px-3 py-2 pr-10 rounded-lg border border-border bg-background focus:ring-2 focus:ring-primary/50 focus:border-primary outline-none transition-colors"
                />
                <div className="absolute right-3 top-1/2 -translate-y-1/2">
                  {renderKeyValidationIcon('gemini')}
                </div>
              </div>
              <p className="mt-1 text-xs text-text-secondary">
                {hasGeminiKey
                  ? 'Enter a new key to replace the existing one'
                  : 'Leave empty to use the app default key'}
              </p>
            </div>
          )}

          {/* Local Model Endpoint */}
          {selectedProvider === 'local' && (
            <div>
              <label className="block text-sm font-medium mb-2">
                <div className="flex items-center gap-2">
                  <Server className="h-4 w-4" />
                  Local Model Endpoint
                </div>
              </label>
              <input
                type="url"
                value={localEndpoint}
                onChange={(e) => setLocalEndpoint(e.target.value)}
                placeholder="http://localhost:11434"
                className="w-full px-3 py-2 rounded-lg border border-border bg-background focus:ring-2 focus:ring-primary/50 focus:border-primary outline-none transition-colors"
              />
              <p className="mt-1 text-xs text-text-secondary">
                Ollama, LM Studio, or any OpenAI-compatible endpoint
              </p>
            </div>
          )}
        </>
      )}
    </div>
  )
}

export default ModelPicker
