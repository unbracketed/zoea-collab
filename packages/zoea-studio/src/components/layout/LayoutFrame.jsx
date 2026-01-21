import { useEffect, useMemo } from 'react'
import { useLocation, useNavigate, useSearchParams } from 'react-router-dom'
import { useShallow } from 'zustand/react/shallow'
import { AppContainer } from './app'
import { ContentCenteredView, FullContentView, TwoPaneView, ViewSidebarProvider } from './view'
import {
  useConversationStore,
  useWorkspaceStore,
} from '../../stores'

const NAV_ITEMS = [
  { id: 'dashboard', label: 'Home', icon: 'home', path: '/dashboard' },
  { id: 'chat', label: 'Chat', icon: 'chat', path: '/chat' },
  { id: 'documents', label: 'Files', icon: 'documents', path: '/documents' },
  { id: 'notepad', label: 'Notebook', icon: 'clipboards', path: '/notepad' },
  { id: 'canvas', label: 'Canvas', icon: 'canvas', path: '/canvas' },
  { id: 'workflows', label: 'Workflows', icon: 'workflows', path: '/workflows' },
]

function LayoutFrame({
  title,
  actions,
  sidebar,
  variant = 'full',
  children,
  leftSlot,
  rightSlot,
  safeAreaBottom,
  maxWidth,
  viewSidebarTitle,
  noPadding = false,
  hideHeader = false,
}) {
  const location = useLocation()
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const projectIdParam = searchParams.get('project')
  const workspaceIdParam = searchParams.get('workspace')

  const {
    projects,
    currentProjectId,
    currentWorkspaceId,
    initializeFromUrl,
  } = useWorkspaceStore(
    useShallow((state) => ({
      projects: state.projects,
      currentProjectId: state.currentProjectId,
      currentWorkspaceId: state.currentWorkspaceId,
      initializeFromUrl: state.initializeFromUrl,
    }))
  )

  const loadConversations = useConversationStore((state) => state.loadConversations)

  const resolvedProjectId = projectIdParam ? Number(projectIdParam) : currentProjectId
  const resolvedWorkspaceId = workspaceIdParam ? Number(workspaceIdParam) : currentWorkspaceId

  useEffect(() => {
    initializeFromUrl(projectIdParam ? Number(projectIdParam) : null, workspaceIdParam ? Number(workspaceIdParam) : null)
  }, [initializeFromUrl, projectIdParam, workspaceIdParam])

  useEffect(() => {
    loadConversations({ project_id: resolvedProjectId, workspace_id: resolvedWorkspaceId })
  }, [loadConversations, resolvedProjectId, resolvedWorkspaceId])

  const navItems = useMemo(() => {
    return NAV_ITEMS.map((item) => {
      // Special case: Home nav item is active for both /dashboard and /home
      const isActive = item.id === 'dashboard'
        ? location.pathname.startsWith('/dashboard') || location.pathname.startsWith('/home')
        : location.pathname.startsWith(item.path);
      return {
        ...item,
        active: isActive,
      };
    })
  }, [location.pathname])

  const viewNode = useMemo(() => {
    if (variant === 'two-pane') {
      return (
        <TwoPaneView
          title={title}
          actions={actions}
          sidebar={sidebar}
          left={leftSlot}
          right={rightSlot}
          safeAreaBottom={safeAreaBottom}
        />
      )
    }
    if (variant === 'content-centered') {
      return (
        <ContentCenteredView
          title={title}
          actions={actions}
          sidebar={sidebar}
          safeAreaBottom={safeAreaBottom}
          maxWidth={maxWidth}
          noPadding={noPadding}
        >
          {children}
        </ContentCenteredView>
      )
    }
    return (
      <FullContentView title={title} actions={actions} sidebar={sidebar} safeAreaBottom={safeAreaBottom} noPadding={noPadding} hideHeader={hideHeader}>
        {children}
      </FullContentView>
    )
  }, [variant, title, actions, sidebar, children, leftSlot, rightSlot, safeAreaBottom, maxWidth, noPadding, hideHeader])

  return (
    <ViewSidebarProvider sidebar={sidebar}>
      <AppContainer
        projects={projects}
        navigationItems={navItems}
        viewHeaderTitle={title}
        viewActions={actions}
        safeAreaBottom={safeAreaBottom}
        view={viewNode}
        viewSidebarTitle={viewSidebarTitle}
        onNavigate={(path) => navigate(path)}
      />
    </ViewSidebarProvider>
  )
}

export default LayoutFrame
