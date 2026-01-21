import ViewHeader from './ViewHeader'

function ViewContainer({ title, actions, headerSlot, children, safeAreaBottom = 0, noPadding = false, hideHeader = false }) {
  return (
    <section className="flex flex-col flex-1 min-w-0 min-h-0 bg-background">
      {!hideHeader && (headerSlot || <ViewHeader title={title} actions={actions} />)}
      <div
        className={noPadding ? "flex flex-col flex-1 min-h-0" : "flex-1 min-h-0 overflow-auto p-6 space-y-4"}
        style={safeAreaBottom ? { paddingBottom: `calc(1.5rem + ${safeAreaBottom}px)` } : undefined}
      >
        {children}
      </div>
    </section>
  )
}

export default ViewContainer
