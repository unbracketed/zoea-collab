/**
 * Project Settings Page
 *
 * Dedicated page for editing project settings with tabbed navigation.
 * Settings are organized into: General, Appearance, Email, AI Configuration, and Agent Tools.
 */

import { useEffect, useRef, useState } from 'react'
import { useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { ArrowLeft, CheckCircle } from 'lucide-react'
import LayoutFrame from '../components/layout/LayoutFrame'
import {
  ProjectSettingsNav,
  GeneralSettingsTab,
  AppearanceSettingsTab,
  EmailSettingsTab,
  AIConfigurationTab,
  AgentToolsTab,
} from '../components/project-settings'
import { useWorkspaceStore } from '../stores/workspaceStore'
import { useThemeStore } from '../stores/themeStore'
import api from '../services/api'

const VALID_TABS = ['general', 'appearance', 'email', 'ai', 'tools']

function ProjectSettingsPage() {
  const navigate = useNavigate()
  const { id } = useParams()
  const [searchParams, setSearchParams] = useSearchParams()
  const projectId = Number(id)
  const fileInputRef = useRef(null)

  // Tab navigation
  const tabParam = searchParams.get('tab')
  const activeTab = VALID_TABS.includes(tabParam) ? tabParam : 'general'

  const handleTabChange = (tabId) => {
    setSearchParams({ tab: tabId })
  }

  // Get project from store
  const projects = useWorkspaceStore((state) => state.projects)
  const project = projects.find((p) => p.id === projectId)
  const loadProjects = useWorkspaceStore((state) => state.loadProjects)
  const updateProjectInState = useWorkspaceStore((state) => state.updateProjectInState)
  const setActiveProjectTheme = useThemeStore((state) => state.setActiveProjectTheme)

  // Form state
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [colorTheme, setColorTheme] = useState(null)
  const [usePrimaryHeader, setUsePrimaryHeader] = useState(false)
  const [avatarPreview, setAvatarPreview] = useState(null)
  const [avatarFile, setAvatarFile] = useState(null)
  const [removeAvatar, setRemoveAvatar] = useState(false)
  const [emailAlias, setEmailAlias] = useState('')

  // LLM config state
  const [llmConfig, setLlmConfig] = useState(null)

  // UI state
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState(null)
  const [success, setSuccess] = useState(false)
  const [copiedEmail, setCopiedEmail] = useState(null)

  // Load projects if not already loaded
  useEffect(() => {
    if (projects.length === 0) {
      loadProjects()
    }
  }, [projects.length, loadProjects])

  // Initialize form when project changes
  useEffect(() => {
    if (project) {
      setName(project.name || '')
      setDescription(project.description || '')
      setColorTheme(project.color_theme || null)
      setUsePrimaryHeader(project.use_primary_header || false)
      setAvatarPreview(project.avatar_url || null)
      setAvatarFile(null)
      setRemoveAvatar(false)
      setEmailAlias(project.email_alias || '')
      setError(null)
      setSuccess(false)
    }
  }, [project])

  // Handle avatar file selection
  const handleAvatarSelect = (event) => {
    const file = event.target.files?.[0]
    if (!file) return

    // Validate file type
    const allowedTypes = ['image/jpeg', 'image/png', 'image/gif', 'image/webp']
    if (!allowedTypes.includes(file.type)) {
      setError('Please select a valid image file (JPEG, PNG, GIF, or WebP)')
      return
    }

    // Validate file size (5MB max)
    if (file.size > 5 * 1024 * 1024) {
      setError('Image must be smaller than 5MB')
      return
    }

    setAvatarFile(file)
    setRemoveAvatar(false)
    setError(null)

    // Create preview
    const reader = new FileReader()
    reader.onload = (e) => setAvatarPreview(e.target.result)
    reader.readAsDataURL(file)
  }

  // Handle avatar removal
  const handleRemoveAvatar = () => {
    setAvatarFile(null)
    setAvatarPreview(null)
    setRemoveAvatar(true)
    if (fileInputRef.current) {
      fileInputRef.current.value = ''
    }
  }

  // Handle LLM config changes from ModelPicker
  const handleLlmConfigChange = (config) => {
    setLlmConfig(config)
  }

  // Copy email to clipboard
  const handleCopyEmail = async (email, type) => {
    try {
      await navigator.clipboard.writeText(email)
      setCopiedEmail(type)
      setTimeout(() => setCopiedEmail(null), 2000)
    } catch (err) {
      console.error('Failed to copy email:', err)
    }
  }

  // Save changes
  const handleSave = async () => {
    if (!project) return

    setSaving(true)
    setError(null)
    setSuccess(false)

    try {
      // Update project settings (name, description, color_theme, use_primary_header, email_alias)
      const payload = {}
      if (name !== project.name) payload.name = name
      if (description !== project.description) payload.description = description
      if (colorTheme !== project.color_theme) payload.color_theme = colorTheme
      if (usePrimaryHeader !== project.use_primary_header) payload.use_primary_header = usePrimaryHeader
      if (emailAlias !== (project.email_alias || '')) {
        payload.email_alias = emailAlias || ''
      }

      let updatedProject = project

      // Only call update if there are changes
      if (Object.keys(payload).length > 0) {
        updatedProject = await api.updateProject(project.id, payload)
      }

      // Handle avatar changes
      if (avatarFile) {
        const avatarResult = await api.uploadProjectAvatar(project.id, avatarFile)
        updatedProject = { ...updatedProject, avatar_url: avatarResult.avatar_url }
      } else if (removeAvatar && project.avatar_url) {
        await api.deleteProjectAvatar(project.id)
        updatedProject = { ...updatedProject, avatar_url: null }
      }

      // Save LLM configuration if changed
      if (llmConfig) {
        const llmPayload = {}
        if (llmConfig.provider !== undefined) llmPayload.llm_provider = llmConfig.provider || null
        if (llmConfig.model !== undefined) llmPayload.llm_model_id = llmConfig.model || null
        if (llmConfig.openaiKey) llmPayload.openai_api_key = llmConfig.openaiKey
        if (llmConfig.geminiKey) llmPayload.gemini_api_key = llmConfig.geminiKey
        if (llmConfig.localEndpoint !== undefined) llmPayload.local_model_endpoint = llmConfig.localEndpoint || null

        if (Object.keys(llmPayload).length > 0) {
          await api.updateProjectLLMConfig(project.id, llmPayload)
        }
      }

      // Update project in local state
      updateProjectInState(updatedProject)

      // Update the active project theme if this is the current project
      if (colorTheme !== project.color_theme) {
        setActiveProjectTheme(colorTheme)
      }

      setSuccess(true)
      setTimeout(() => setSuccess(false), 3000)
    } catch (err) {
      console.error('Failed to save project settings:', err)
      setError(err.message || 'Failed to save settings')
    } finally {
      setSaving(false)
    }
  }

  // Render active tab content
  const renderTabContent = () => {
    switch (activeTab) {
      case 'general':
        return (
          <GeneralSettingsTab
            name={name}
            setName={setName}
            description={description}
            setDescription={setDescription}
            colorTheme={colorTheme}
            avatarPreview={avatarPreview}
            fileInputRef={fileInputRef}
            handleAvatarSelect={handleAvatarSelect}
            handleRemoveAvatar={handleRemoveAvatar}
            hasExistingAvatar={!!project?.avatar_url}
          />
        )
      case 'appearance':
        return (
          <AppearanceSettingsTab
            colorTheme={colorTheme}
            setColorTheme={setColorTheme}
            usePrimaryHeader={usePrimaryHeader}
            setUsePrimaryHeader={setUsePrimaryHeader}
          />
        )
      case 'email':
        return (
          <EmailSettingsTab
            canonicalEmail={project?.canonical_email}
            emailAlias={emailAlias}
            setEmailAlias={setEmailAlias}
            organizationSlug={project?.organization?.slug}
            copiedEmail={copiedEmail}
            handleCopyEmail={handleCopyEmail}
          />
        )
      case 'ai':
        return (
          <AIConfigurationTab
            projectId={project?.id}
            onConfigChange={handleLlmConfigChange}
          />
        )
      case 'tools':
        return <AgentToolsTab projectId={project?.id} />
      default:
        return null
    }
  }

  // Sidebar content
  const sidebarContent = (
    <div className="pt-4">
      <ProjectSettingsNav activeTab={activeTab} onTabChange={handleTabChange} />
    </div>
  )

  // Loading state
  if (!project) {
    return (
      <LayoutFrame title="Project Settings" variant="full" sidebar={sidebarContent}>
        <div className="flex items-center justify-center h-64">
          <div className="text-muted-foreground">Loading project...</div>
        </div>
      </LayoutFrame>
    )
  }

  return (
    <LayoutFrame title="Project Settings" variant="full" sidebar={sidebarContent}>
      <div className="flex flex-col h-full">
        {/* Header with back button */}
        <div className="flex items-center gap-4 p-6 border-b border-border">
          <button
            type="button"
            onClick={() => navigate('/projects')}
            className="p-2 rounded-lg hover:bg-muted text-muted-foreground hover:text-foreground transition-colors"
            aria-label="Back to projects"
          >
            <ArrowLeft className="h-5 w-5" />
          </button>
          <div>
            <h1 className="text-2xl font-bold">Project Settings</h1>
            <p className="text-muted-foreground">{project.name}</p>
          </div>
        </div>

        {/* Status messages */}
        <div className="px-6">
          {error && (
            <div className="mt-6 p-4 rounded-lg bg-destructive/10 text-destructive border border-destructive/20">
              {error}
            </div>
          )}
          {success && (
            <div className="mt-6 p-4 rounded-lg bg-green-500/10 text-green-600 dark:text-green-400 border border-green-500/20 flex items-center gap-2">
              <CheckCircle className="h-5 w-5" />
              Settings saved successfully
            </div>
          )}
        </div>

        {/* Tab content */}
        <div className="flex-1 overflow-auto p-6">
          <div className="max-w-2xl">{renderTabContent()}</div>
        </div>

        {/* Save/Cancel buttons - sticky footer */}
        <div className="border-t border-border p-4 flex justify-end gap-3">
          <button
            type="button"
            onClick={() => navigate('/projects')}
            disabled={saving}
            className="px-4 py-2 text-sm font-medium rounded-lg border border-border hover:bg-muted transition-colors disabled:opacity-50"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={handleSave}
            disabled={saving || !name.trim()}
            className="px-4 py-2 text-sm font-medium rounded-lg bg-primary text-primary-foreground hover:bg-primary/90 transition-colors disabled:opacity-50"
          >
            {saving ? 'Saving...' : 'Save Changes'}
          </button>
        </div>
      </div>
    </LayoutFrame>
  )
}

export default ProjectSettingsPage
