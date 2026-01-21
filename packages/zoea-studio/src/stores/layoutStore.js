/**
 * Layout Store
 *
 * Manages layout state (ProjectsBar collapse, sidebar sections).
 * Uses Zustand persist to survive StrictMode remounts and browser reloads.
 */

import { create } from 'zustand'
import { persist } from 'zustand/middleware'

const defaultSidebarSections = () => ({
  workspaces: { collapsed: false },
  clipboard: { collapsed: false },
  view: { collapsed: false },
})

export const useLayoutStore = create(
  persist(
    (set, get) => ({
      projectsBarOpen: false,
      sidebarSections: defaultSidebarSections(),

      setProjectsBarOpen: (open) => set({ projectsBarOpen: open }),
      toggleProjectsBar: () => set((state) => ({ projectsBarOpen: !state.projectsBarOpen })),

      setSidebarSectionCollapsed: (sectionKey, collapsed) =>
        set((state) => {
          const next = state.sidebarSections[sectionKey]
            ? { ...state.sidebarSections }
            : { ...state.sidebarSections, [sectionKey]: { collapsed: false } }
          next[sectionKey] = { collapsed }
          return { sidebarSections: next }
        }),

      toggleSidebarSection: (sectionKey) =>
        set((state) => {
          const current = state.sidebarSections[sectionKey]?.collapsed ?? false
          return {
            sidebarSections: {
              ...state.sidebarSections,
              [sectionKey]: { collapsed: !current },
            },
          }
        }),

      resetLayoutPreferences: () =>
        set({
          projectsBarOpen: false,
          sidebarSections: defaultSidebarSections(),
        }),
    }),
    {
      name: 'layout-preferences',
      partialize: (state) => ({
        projectsBarOpen: state.projectsBarOpen,
        sidebarSections: state.sidebarSections,
      }),
    }
  )
)
