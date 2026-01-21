import { describe, it, expect } from 'vitest'
import { useLayoutStore } from './layoutStore'

describe('layoutStore', () => {
  it('toggles ProjectsBar open state', () => {
    const initial = useLayoutStore.getState().projectsBarOpen
    useLayoutStore.getState().toggleProjectsBar()
    expect(useLayoutStore.getState().projectsBarOpen).toBe(!initial)
  })

  it('sets and toggles sidebar sections', () => {
    useLayoutStore.getState().setSidebarSectionCollapsed('workspaces', true)
    expect(useLayoutStore.getState().sidebarSections.workspaces.collapsed).toBe(true)
    useLayoutStore.getState().toggleSidebarSection('workspaces')
    expect(useLayoutStore.getState().sidebarSections.workspaces.collapsed).toBe(false)
  })

  it('resets layout preferences', () => {
    useLayoutStore.setState({ projectsBarOpen: false })
    useLayoutStore.getState().resetLayoutPreferences()
    expect(useLayoutStore.getState().projectsBarOpen).toBe(true)
  })
})
