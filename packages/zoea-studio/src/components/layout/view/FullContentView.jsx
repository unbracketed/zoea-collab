import ViewContainer from './ViewContainer'
import { ViewSidebarProvider } from './ViewContext'

function FullContentView({ title, actions, sidebar, children, noPadding = false, hideHeader = false }) {
  return (
    <ViewSidebarProvider sidebar={sidebar}>
      <ViewContainer title={title} actions={actions} noPadding={noPadding} hideHeader={hideHeader}>
        <div className={noPadding ? "flex flex-col flex-1 w-full min-h-0" : "w-full"}>{children}</div>
      </ViewContainer>
    </ViewSidebarProvider>
  )
}

export default FullContentView
