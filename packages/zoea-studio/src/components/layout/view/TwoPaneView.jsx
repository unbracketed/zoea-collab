import ViewContainer from './ViewContainer'
import { ViewSidebarProvider } from './ViewContext'

function TwoPaneView({
  title,
  actions,
  sidebar,
  left,
  right,
  minLeftWidth = 320,
  minRightWidth = 320,
  safeAreaBottom,
}) {
  return (
    <ViewSidebarProvider sidebar={sidebar}>
      <ViewContainer title={title} actions={actions} safeAreaBottom={safeAreaBottom}>
        <div className="flex gap-4 w-full items-stretch min-h-0">
          <div
            className="bg-surface border border-border rounded-lg shadow-soft flex-1 min-h-0 overflow-auto"
            style={{ minWidth: minLeftWidth }}
          >
            {left}
          </div>
          <div
            className="bg-surface border border-border rounded-lg shadow-soft flex-1 min-h-0 overflow-auto"
            style={{ minWidth: minRightWidth }}
          >
            {right}
          </div>
        </div>
      </ViewContainer>
    </ViewSidebarProvider>
  )
}

export default TwoPaneView
