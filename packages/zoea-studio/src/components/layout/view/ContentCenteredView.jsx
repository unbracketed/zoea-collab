import ViewContainer from './ViewContainer'
import { ViewSidebarProvider } from './ViewContext'

function ContentCenteredView({
  title,
  actions,
  sidebar,
  children,
  maxWidth = 'max-w-4xl',
  safeAreaBottom,
  noPadding = false,
}) {
  // When noPadding is true and no maxWidth constraint, fill the container completely
  const fillContainer = noPadding && !maxWidth

  return (
    <ViewSidebarProvider sidebar={sidebar}>
      <ViewContainer title={title} actions={actions} safeAreaBottom={safeAreaBottom} noPadding={noPadding}>
        {fillContainer ? (
          <div className="w-full h-full flex flex-col">{children}</div>
        ) : (
          <div className={`flex justify-center w-full ${noPadding ? 'h-full' : ''}`}>
            <div className={`w-full ${maxWidth} ${noPadding ? 'h-full flex flex-col' : 'space-y-4'}`}>{children}</div>
          </div>
        )}
      </ViewContainer>
    </ViewSidebarProvider>
  )
}

export default ContentCenteredView
