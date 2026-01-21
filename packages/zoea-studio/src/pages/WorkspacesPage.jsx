import { useEffect } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { Briefcase, FolderTree, Folder } from 'lucide-react'
import LayoutFrame from '../components/layout/LayoutFrame'
import { useWorkspaceStore } from '../stores'

function WorkspacesPage() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()

  const projectId = searchParams.get('project') ? parseInt(searchParams.get('project'), 10) : null
  const currentProjectId = useWorkspaceStore((state) => state.currentProjectId)
  const workspaces = useWorkspaceStore((state) => state.workspaces)
  const projects = useWorkspaceStore((state) => state.projects)
  const loading = useWorkspaceStore((state) => state.loading)
  const error = useWorkspaceStore((state) => state.error)
  const loadProjects = useWorkspaceStore((state) => state.loadProjects)
  const loadWorkspaces = useWorkspaceStore((state) => state.loadWorkspaces)
  const setCurrentWorkspace = useWorkspaceStore((state) => state.setCurrentWorkspace)

  useEffect(() => {
    if (projects.length === 0) {
      loadProjects()
    }
  }, [loadProjects, projects.length])

  useEffect(() => {
    const effectiveProjectId = projectId || currentProjectId
    if (effectiveProjectId) {
      loadWorkspaces(effectiveProjectId)
    }
  }, [projectId, currentProjectId, loadWorkspaces])

  const handleWorkspaceClick = (workspaceId) => {
    const effectiveProjectId = projectId || currentProjectId
    setCurrentWorkspace(workspaceId)
    navigate(`/chat?project=${effectiveProjectId}&workspace=${workspaceId}`)
  }

  const currentProject = projects.find((p) => p.id === (projectId || currentProjectId))

  const renderPlaceholder = (icon, title, text, description) => (
    <div className="placeholder-page">
      <div className="placeholder-content">
        {icon}
        <h1>{title}</h1>
        {text && <p className="placeholder-text">{text}</p>}
        {description && <p className="placeholder-description">{description}</p>}
      </div>
    </div>
  )

  const renderState = () => {
    if (loading && workspaces.length === 0) {
      return renderPlaceholder(
        <Briefcase size={64} className="placeholder-icon" />,
        'Loading workspaces...',
        null,
        'Fetching workspace data…'
      )
    }

    if (error) {
      return renderPlaceholder(
        <Briefcase size={64} className="placeholder-icon" />,
        'Error Loading Workspaces',
        null,
        error
      )
    }

    if (!projectId && !currentProjectId) {
      return renderPlaceholder(
        <Briefcase size={64} className="placeholder-icon" />,
        'No Project Selected',
        'Please select a project first',
        'Use the project selector in the sidebar or visit the Projects page.'
      )
    }

    if (workspaces.length === 0) {
      return renderPlaceholder(
        <Briefcase size={64} className="placeholder-icon" />,
        'No Workspaces',
        'No workspaces found',
        'Contact your administrator to create a workspace.'
      )
    }

    return (
      <div className="workspaces-page" style={{ padding: '2rem' }}>
        <div style={{ maxWidth: '1200px', margin: '0 auto' }}>
          <div style={{ marginBottom: '2rem' }}>
            <h1 style={{ fontSize: '2rem', fontWeight: '700', marginBottom: '0.5rem' }}>
              Workspaces
            </h1>
            <p style={{ color: 'var(--text-secondary)' }}>
              {currentProject ? `Manage workspaces in ${currentProject.name}` : 'Manage your workspaces'}
            </p>
          </div>

          <div
            style={{
              backgroundColor: 'var(--surface)',
              border: '1px solid var(--border)',
              borderRadius: '12px',
              boxShadow: 'var(--shadow)',
            }}
          >
            {workspaces.map((workspace, index) => (
              <div
                key={workspace.id}
                onClick={() => handleWorkspaceClick(workspace.id)}
                style={{
                  padding: '1.25rem 1.5rem',
                  cursor: 'pointer',
                  transition: 'all 0.2s ease',
                  borderBottom: index < workspaces.length - 1 ? '1px solid var(--border)' : 'none',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '1rem',
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.backgroundColor = 'var(--assistant-message)'
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.backgroundColor = 'transparent'
                }}
              >
                <div style={{ width: `${workspace.level * 2}rem`, flexShrink: 0 }} />

                <div
                  style={{
                    width: '40px',
                    height: '40px',
                    borderRadius: '8px',
                    backgroundColor: workspace.level === 0 ? 'var(--primary)' : 'var(--secondary)',
                    color: 'white',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    flexShrink: 0,
                    opacity: workspace.level === 0 ? 1 : 0.8,
                  }}
                >
                  {workspace.level === 0 ? <FolderTree size={20} /> : <Folder size={20} />}
                </div>

                <div style={{ flex: 1, overflow: 'hidden' }}>
                  <div
                    style={{
                      fontSize: workspace.level === 0 ? '1.125rem' : '1rem',
                      fontWeight: workspace.level === 0 ? '600' : '500',
                      marginBottom: workspace.full_path ? '0.25rem' : 0,
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                      whiteSpace: 'nowrap',
                    }}
                  >
                    {workspace.name}
                  </div>

                  {workspace.full_path && (
                    <div
                      style={{
                        fontSize: '0.75rem',
                        color: 'var(--text-secondary)',
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                        whiteSpace: 'nowrap',
                      }}
                    >
                      {workspace.full_path}
                    </div>
                  )}

                  {workspace.description && (
                    <div
                      style={{
                        fontSize: '0.9rem',
                        color: 'var(--text-secondary)',
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                        display: '-webkit-box',
                        WebkitLineClamp: 2,
                        WebkitBoxOrient: 'vertical',
                        marginTop: '0.25rem',
                      }}
                    >
                      {workspace.description}
                    </div>
                  )}

                  <div
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '0.5rem',
                      marginTop: '0.35rem',
                      color: 'var(--text-secondary)',
                      fontSize: '0.85rem',
                    }}
                  >
                    <span>Level {workspace.level}</span>
                    {workspace.parent_id && (
                      <>
                        <span>•</span>
                        <span>Parent ID: {workspace.parent_id}</span>
                      </>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    )
  }

  return (
    <LayoutFrame title="Workspaces" variant="full">
      {renderState()}
    </LayoutFrame>
  )
}

export default WorkspacesPage
