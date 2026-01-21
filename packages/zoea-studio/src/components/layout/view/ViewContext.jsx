import { createContext, useContext, useMemo } from 'react'

const ViewSidebarContext = createContext(undefined)

export function ViewSidebarProvider({ sidebar, children }) {
  const value = useMemo(() => ({ sidebar }), [sidebar])
  return <ViewSidebarContext.Provider value={value}>{children}</ViewSidebarContext.Provider>
}

export function useViewSidebar() {
  return useContext(ViewSidebarContext)
}
