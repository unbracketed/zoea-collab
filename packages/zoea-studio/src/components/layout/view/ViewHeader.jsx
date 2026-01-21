function ViewHeader({ title, actions }) {
  return (
    <div className="h-20 min-h-20 flex items-center justify-between border-b border-border bg-surface px-6">
      <div className="flex flex-col leading-tight">
        <span className="text-lg font-semibold">{title}</span>
      </div>
      {actions && <div className="flex items-center gap-2">{actions}</div>}
    </div>
  )
}

export default ViewHeader
