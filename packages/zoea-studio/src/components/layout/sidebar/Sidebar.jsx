function Sidebar({
  viewSectionContent = null,
  viewSectionTitle = 'View',
}) {
  const hasViewSection = Boolean(viewSectionContent)

  return (
    <aside className="w-[290px] min-w-[290px] bg-sidebar border-r border-sidebar-border flex flex-col min-h-0">
      <div className="flex-1 overflow-y-auto px-2 py-3 space-y-3">
        {hasViewSection && (
          <div>
            <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2 px-1">
              {viewSectionTitle}
            </h3>
            {viewSectionContent}
          </div>
        )}
      </div>
    </aside>
  )
}

export default Sidebar
