/**
 * Projects Page (FullContent View)
 * Uses LayoutFrame to render within the new Slack-inspired shell.
 */

import { useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { FolderKanban, Calendar, MapPin } from 'lucide-react'
import LayoutFrame from '../components/layout/LayoutFrame'
import { useWorkspaceStore } from '../stores'

function ProjectsPage() {
  const navigate = useNavigate()

  const projects = useWorkspaceStore((state) => state.projects)
  const loading = useWorkspaceStore((state) => state.loading)
  const error = useWorkspaceStore((state) => state.error)
  const loadProjects = useWorkspaceStore((state) => state.loadProjects)
  const switchProject = useWorkspaceStore((state) => state.switchProject)

  useEffect(() => {
    loadProjects()
  }, [loadProjects])

  const handleProjectClick = async (projectId) => {
    await switchProject(projectId)
    navigate(`/chat?project=${projectId}`)
  }

  const formatDate = (dateString) => {
    const date = new Date(dateString)
    return date.toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    })
  }

  const renderState = () => {
    if (loading) {
      return (
        <div className="placeholder-page">
          <div className="placeholder-content">
            <FolderKanban size={64} className="placeholder-icon" />
            <h1>Loading Projects</h1>
            <p className="placeholder-text">Please wait while we fetch your projects.</p>
            <div className="placeholder-description">Fetching workspace data…</div>
          </div>
        </div>
      )
    }

    if (error) {
      return (
        <div className="placeholder-page">
          <div className="placeholder-content">
            <FolderKanban size={64} className="placeholder-icon" />
            <h1>Error Loading Projects</h1>
            <p className="placeholder-description">{error}</p>
          </div>
        </div>
      )
    }

    if (projects.length === 0) {
      return (
        <div className="placeholder-page">
          <div className="placeholder-content">
            <FolderKanban size={64} className="placeholder-icon" />
            <h1>No Projects</h1>
            <p className="placeholder-text">No projects found</p>
            <p className="placeholder-description">Contact your administrator to create a project.</p>
          </div>
        </div>
      )
    }

    return (
      <div className="projects-page" style={{ padding: '2rem' }}>
        <div style={{ maxWidth: '1200px', margin: '0 auto' }}>
          <div style={{ marginBottom: '2rem' }}>
            <h1 style={{ fontSize: '2rem', fontWeight: '700', marginBottom: '0.5rem' }}>
              Projects
            </h1>
            <p style={{ color: 'var(--text-secondary)' }}>Manage your AI projects and workspaces</p>
          </div>

          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fill, minmax(350px, 1fr))',
              gap: '1.5rem',
            }}
          >
            {projects.map((project) => (
              <div
                key={project.id}
                onClick={() => handleProjectClick(project.id)}
                style={{
                  backgroundColor: 'var(--surface)',
                  border: '1px solid var(--border)',
                  borderRadius: '12px',
                  padding: '1.5rem',
                  cursor: 'pointer',
                  transition: 'all 0.2s ease',
                  boxShadow: 'var(--shadow)',
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.borderColor = 'var(--primary)'
                  e.currentTarget.style.transform = 'translateY(-2px)'
                  e.currentTarget.style.boxShadow =
                    '0 4px 6px -1px rgb(0 0 0 / 0.1), 0 2px 4px -2px rgb(0 0 0 / 0.1)'
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.borderColor = 'var(--border)'
                  e.currentTarget.style.transform = 'translateY(0)'
                  e.currentTarget.style.boxShadow = 'var(--shadow)'
                }}
              >
                <div style={{ display: 'flex', alignItems: 'flex-start', gap: '1rem' }}>
                  <div
                    style={{
                      width: '48px',
                      height: '48px',
                      borderRadius: '8px',
                      backgroundColor: 'var(--primary)',
                      color: 'white',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      flexShrink: 0,
                    }}
                  >
                    <FolderKanban size={24} />
                  </div>

                  <div style={{ flex: 1, overflow: 'hidden' }}>
                    <h3
                      style={{
                        fontSize: '1.25rem',
                        fontWeight: '600',
                        marginBottom: '0.5rem',
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                        whiteSpace: 'nowrap',
                      }}
                    >
                      {project.name}
                    </h3>

                    {project.description && (
                      <p
                        style={{
                          color: 'var(--text-secondary)',
                          marginBottom: '0.5rem',
                          overflow: 'hidden',
                          textOverflow: 'ellipsis',
                          display: '-webkit-box',
                          WebkitLineClamp: 2,
                          WebkitBoxOrient: 'vertical',
                        }}
                      >
                        {project.description}
                      </p>
                    )}

                    <div
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: '0.75rem',
                        color: 'var(--text-secondary)',
                        fontSize: '0.9rem',
                      }}
                    >
                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
                        <Calendar size={16} />
                        <span>Created {formatDate(project.created_at)}</span>
                      </div>
                      {project.organization?.name && (
                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
                          <MapPin size={16} />
                          <span>{project.organization.name}</span>
                        </div>
                      )}
                    </div>
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
    <LayoutFrame title="Projects" variant="full">
      {renderState()}
    </LayoutFrame>
  )
}

export default ProjectsPage
