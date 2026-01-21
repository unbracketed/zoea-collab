import clsx from 'clsx'
import { useState } from 'react'
import { useNavigate, useSearchParams, useLocation } from 'react-router-dom'
import { Plus, Settings } from 'lucide-react'
import { useLayoutStore } from '../../../stores/layoutStore'
import { useWorkspaceStore, useSessionStore } from '../../../stores'
import AddProjectModal from '../../AddProjectModal'

function ProjectsBar({ projects = [] }) {
  // All hooks must be called before any conditional returns
  const [showAddProject, setShowAddProject] = useState(false)
  const navigate = useNavigate()
  const location = useLocation()
  const [searchParams] = useSearchParams()
  const projectsBarOpen = useLayoutStore((state) => state.projectsBarOpen)
  const currentProjectId = useWorkspaceStore((state) => state.currentProjectId)
  const currentWorkspaceId = useWorkspaceStore((state) => state.currentWorkspaceId)
  const switchProject = useWorkspaceStore((state) => state.switchProject)
  const getCurrentProject = useWorkspaceStore((state) => state.getCurrentProject)
  const saveProjectRoute = useSessionStore((state) => state.saveProjectRoute)
  const getProjectRoute = useSessionStore((state) => state.getProjectRoute)

  // Get current project for primary header styling
  const currentProject = getCurrentProject()
  const usePrimaryHeader = currentProject?.use_primary_header ?? false

  // When closed, completely hide the bar
  if (!projectsBarOpen) {
    return null
  }

  const handleSelectProject = async (projectId) => {
    if (projectId === currentProjectId) return

    // Save current route for the project we're leaving
    if (currentProjectId) {
      const currentPath = location.pathname + location.search
      saveProjectRoute(currentProjectId, {
        path: currentPath,
        workspaceId: currentWorkspaceId,
      })
    }

    // Switch project in store (this will also load workspaces)
    await switchProject(projectId)

    // Check for saved route for the project we're switching to
    const savedRoute = getProjectRoute(projectId)

    if (savedRoute && savedRoute.path) {
      // Navigate to saved path for this project
      navigate(savedRoute.path, { replace: true })
    } else {
      // No saved route - stay on current view but update project param
      const params = new URLSearchParams(searchParams)
      params.set('project', projectId.toString())
      params.delete('workspace') // Clear workspace, will be auto-selected
      navigate(`${location.pathname}?${params.toString()}`, { replace: true })
    }
  }

  return (
    <aside
      className={clsx(
        'w-60 flex flex-col min-h-0 overflow-hidden',
        usePrimaryHeader
          ? 'bg-primary border-r border-primary/20'
          : 'bg-sidebar border-r border-sidebar-border'
      )}
      aria-label="Projects bar"
    >
      <div className="flex-1 overflow-y-auto py-3">
        <div className="flex flex-col gap-2">
          {projects.map((project) => {
            const isActive = project.id === currentProjectId
            return (
              <div
                key={project.id}
                className="group relative"
              >
                <button
                  type="button"
                  onClick={() => handleSelectProject(project.id)}
                  className={clsx(
                    'w-full flex items-center gap-3 px-3 py-2 rounded-lg transition-colors justify-start',
                    usePrimaryHeader
                      ? isActive
                        ? 'bg-primary-foreground/20 ring-2 ring-primary-foreground/30 ring-inset'
                        : 'hover:bg-primary-foreground/10'
                      : isActive
                        ? 'bg-sidebar-primary ring-2 ring-sidebar-primary-foreground/30 ring-inset'
                        : 'hover:bg-sidebar-accent'
                  )}
                  aria-label={project.name}
                  aria-current={isActive ? 'true' : undefined}
                >
                  {project.avatar_url ? (
                    <img
                      src={project.avatar_url}
                      alt={project.name}
                      className={clsx(
                        'h-8 w-8 rounded-lg object-cover flex-shrink-0',
                        isActive && (usePrimaryHeader ? 'ring-2 ring-primary-foreground/50' : 'ring-2 ring-sidebar-primary-foreground/50')
                      )}
                    />
                  ) : (
                    <span
                      className={clsx(
                        'h-8 w-8 rounded-lg flex items-center justify-center text-sm font-semibold text-white flex-shrink-0',
                        isActive && (usePrimaryHeader ? 'ring-2 ring-primary-foreground/50' : 'ring-2 ring-sidebar-primary-foreground/50')
                      )}
                      style={{ backgroundColor: project.color || '#2563eb' }}
                    >
                      {project.name?.[0]?.toUpperCase() || '?'}
                    </span>
                  )}
                  <span className={clsx(
                    'text-sm font-medium truncate flex-1 text-left',
                    usePrimaryHeader
                      ? isActive ? 'text-primary-foreground' : 'text-primary-foreground/80'
                      : isActive ? 'text-sidebar-primary-foreground' : 'text-sidebar-foreground'
                  )}>
                    {project.name}
                  </span>
                </button>
                {/* Settings button - visible on hover */}
                <button
                  type="button"
                  onClick={(e) => {
                    e.stopPropagation()
                    navigate(`/projects/${project.id}/settings`)
                  }}
                  className={clsx(
                    'absolute right-2 top-1/2 -translate-y-1/2 opacity-0 group-hover:opacity-100 transition-opacity p-1 rounded-md',
                    usePrimaryHeader
                      ? 'bg-primary-foreground/20 hover:bg-primary-foreground/30 text-primary-foreground'
                      : 'bg-sidebar-accent/80 hover:bg-sidebar-accent text-sidebar-foreground hover:text-sidebar-primary-foreground'
                  )}
                  aria-label={`Settings for ${project.name}`}
                >
                  <Settings className="h-4 w-4" />
                </button>
              </div>
            )
          })}

          {/* Add Project button */}
          <button
            type="button"
            onClick={() => setShowAddProject(true)}
            className={clsx(
              'w-full flex items-center gap-3 px-3 py-2 rounded-lg transition-colors justify-start',
              usePrimaryHeader
                ? 'hover:bg-primary-foreground/10 text-primary-foreground/60 hover:text-primary-foreground'
                : 'hover:bg-sidebar-accent text-sidebar-foreground/60 hover:text-sidebar-foreground'
            )}
            aria-label="Add new project"
          >
            <span className={clsx(
              'h-8 w-8 rounded-lg flex items-center justify-center border border-dashed',
              usePrimaryHeader ? 'border-primary-foreground/30' : 'border-sidebar-foreground/30'
            )}>
              <Plus className="h-4 w-4" />
            </span>
            <span className="text-sm font-medium">
              Add Project
            </span>
          </button>
        </div>
      </div>

      {/* Add Project Modal */}
      <AddProjectModal
        isOpen={showAddProject}
        onClose={() => setShowAddProject(false)}
        onProjectCreated={(newProject) => {
          // Optionally switch to the new project
          handleSelectProject(newProject.id)
        }}
      />
    </aside>
  )
}

export default ProjectsBar
