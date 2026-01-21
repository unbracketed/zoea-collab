import { useEffect } from 'react'
import AppHeader from './AppHeader'
import NavigationBar from './NavigationBar'
import ProjectsBar from './ProjectsBar'
import Sidebar from '../sidebar/Sidebar'
import ViewContainer from '../view/ViewContainer'
import { useViewSidebar } from '../view/ViewContext'
import { useWorkspaceStore } from '../../../stores'
import { useThemeStore } from '../../../stores/themeStore'

const fallbackProjects = [
  { id: 'alpha', name: 'Alpha Project', color: '#0d4f5c', color_theme: 'ocean' },
  { id: 'bravo', name: 'Bravo', color: '#7a4a00', color_theme: 'sunrise' },
  { id: 'charlie', name: 'Charlie', color: '#1a3d2e', color_theme: 'forest' },
]

const fallbackNav = [
  { id: 'dashboard', label: 'Dashboard', icon: 'layout-dashboard' },
  { id: 'chat', label: 'Chat', icon: 'message-square' },
  { id: 'documents', label: 'Documents', icon: 'file-text' },
  { id: 'clipboards', label: 'Notebook', icon: 'clipboard-list' },
  { id: 'canvas', label: 'Canvas', icon: 'shape' },
  { id: 'workflows', label: 'Workflows', icon: 'workflow' },
  { id: 'settings', label: 'Settings', icon: 'settings' },
]

function AppContainer({
  projects = fallbackProjects,
  navigationItems = fallbackNav,
  viewHeaderTitle = 'View Title',
  viewActions,
  viewContent,
  viewSidebarSection,
  safeAreaBottom,
  view,
  onNavigate,
  viewSidebarTitle = 'View',
}) {
  const viewSidebar = useViewSidebar()
  const currentProjectId = useWorkspaceStore((state) => state.currentProjectId)
  const currentProject = projects.find((p) => p.id === currentProjectId) || projects[0]
  const setActiveProjectTheme = useThemeStore((state) => state.setActiveProjectTheme)

  // Apply project color theme when project changes
  useEffect(() => {
    setActiveProjectTheme(currentProject?.color_theme || null)
  }, [currentProject?.color_theme, setActiveProjectTheme])

  const renderedView =
    view ||
    (
      <ViewContainer title={viewHeaderTitle} actions={viewActions} safeAreaBottom={safeAreaBottom}>
        {viewContent || (
          <div className="text-sm text-text-secondary">
            Replace this placeholder with view content.
          </div>
        )}
      </ViewContainer>
    )

  return (
    <div className="h-screen bg-background text-text-primary flex flex-col">
      <AppHeader />
      <div className="flex flex-1 min-h-0">
        <ProjectsBar projects={projects} />
        <NavigationBar items={navigationItems} onNavigate={onNavigate} />
        <Sidebar
          viewSectionContent={viewSidebar?.sidebar || viewSidebarSection}
          viewSectionTitle={viewSidebar?.title || viewSidebarTitle}
        />
        {renderedView}
      </div>
    </div>
  )
}

export default AppContainer
