import { useEffect, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import clsx from 'clsx'
import { PanelLeftClose, PanelRightOpen, Search } from 'lucide-react'
import { useLayoutStore } from '../../../stores/layoutStore'
import { useWorkspaceStore } from '../../../stores/workspaceStore'
import ThemeSelector from '../../ThemeSelector'

function AppHeader() {
  const projectsBarOpen = useLayoutStore((state) => state.projectsBarOpen)
  const toggleProjectsBar = useLayoutStore((state) => state.toggleProjectsBar)
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const currentProjectId = useWorkspaceStore((state) => state.currentProjectId)
  const currentWorkspaceId = useWorkspaceStore((state) => state.currentWorkspaceId)
  const getCurrentProject = useWorkspaceStore((state) => state.getCurrentProject)

  // Get current project for primary header styling and name display
  const currentProject = getCurrentProject()
  const usePrimaryHeader = currentProject?.use_primary_header ?? false
  const projectName = currentProject?.name || 'Zoea Studio'

  const [query, setQuery] = useState(() => searchParams.get('q') || '')

  useEffect(() => {
    setQuery(searchParams.get('q') || '')
  }, [searchParams])

  const handleSearchSubmit = (event) => {
    event.preventDefault()
    const projectParam = searchParams.get('project') || (currentProjectId ? String(currentProjectId) : null)
    const workspaceParam = searchParams.get('workspace') || (currentWorkspaceId ? String(currentWorkspaceId) : null)
    const trimmed = query.trim()

    const params = new URLSearchParams()
    if (trimmed) {
      params.set('q', trimmed)
    }
    if (projectParam) {
      params.set('project', projectParam)
    }
    if (workspaceParam) {
      params.set('workspace', workspaceParam)
    }

    const target = params.toString()
    navigate(target ? `/search?${target}` : '/search')
  }

  return (
    <header
      className={clsx(
        'h-16 min-h-16 flex items-center px-4 gap-4 shadow-sm',
        usePrimaryHeader
          ? 'bg-primary text-primary-foreground border-b border-primary/20'
          : 'bg-sidebar border-b border-sidebar-border'
      )}
    >
      <div className="flex items-center gap-3 flex-shrink-0">
        <button
          type="button"
          onClick={toggleProjectsBar}
          className={clsx(
            'inline-flex items-center justify-center h-10 w-10 rounded-md transition-colors',
            usePrimaryHeader
              ? 'border border-primary-foreground/20 bg-primary-foreground/10 hover:bg-primary-foreground/20 text-primary-foreground'
              : 'border border-sidebar-border bg-sidebar hover:bg-sidebar-accent text-sidebar-foreground'
          )}
          aria-label={projectsBarOpen ? 'Collapse projects bar' : 'Expand projects bar'}
        >
          {projectsBarOpen ? (
            <PanelLeftClose className="h-4 w-4" />
          ) : (
            <PanelRightOpen className="h-4 w-4" />
          )}
        </button>
        <div className="flex flex-col">
          <span className={clsx(
            'text-base font-semibold',
            usePrimaryHeader ? 'text-primary-foreground' : 'text-sidebar-foreground'
          )}>{projectName}</span>
        </div>
      </div>

      <div className="flex-1 flex justify-center">
        <form
          onSubmit={handleSearchSubmit}
          className={clsx(
            'flex items-center gap-2 rounded-md px-3 py-2 w-full max-w-xl',
            usePrimaryHeader
              ? 'bg-primary-foreground/10 border border-primary-foreground/20'
              : 'bg-sidebar-accent border border-sidebar-border'
          )}
          role="search"
        >
          <Search className={clsx(
            'h-4 w-4',
            usePrimaryHeader ? 'text-primary-foreground/70' : 'text-muted-foreground'
          )} />
          <input
            className={clsx(
              'bg-transparent border-none outline-none text-sm w-full',
              usePrimaryHeader
                ? 'text-primary-foreground placeholder:text-primary-foreground/50'
                : 'text-sidebar-foreground placeholder:text-muted-foreground'
            )}
            placeholder="Search project files with Gemini..."
            type="search"
            aria-label="Search"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
          />
        </form>
      </div>

      <div className="flex items-center gap-3 flex-shrink-0">
        <ThemeSelector />
      </div>
    </header>
  )
}

export default AppHeader
