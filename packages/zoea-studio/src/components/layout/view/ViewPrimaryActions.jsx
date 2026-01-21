/**
 * ViewPrimaryActions - Compact action buttons for view-level operations
 *
 * Used in ViewHeader to display primary actions for the current view.
 * Uses minimal, compact styling for a clean interface.
 */
function ViewPrimaryActions({ children }) {
  return (
    <div className="flex items-center gap-2">
      {children}
    </div>
  )
}

/**
 * ViewPrimaryActions.Button - Minimal, compact button for primary actions
 */
ViewPrimaryActions.Button = function ViewPrimaryActionButton({
  children,
  onClick,
  variant = 'default',
  title,
  disabled = false,
}) {
  const baseClasses = "px-3 py-1.5 text-sm font-medium rounded-md transition-colors duration-200"

  const variantClasses = {
    default: "bg-primary text-white hover:bg-primary/90 disabled:bg-primary/50",
    outline: "border border-border text-text-primary hover:bg-surface-hover disabled:opacity-50",
    ghost: "text-text-secondary hover:bg-surface-hover hover:text-text-primary disabled:opacity-50",
  }

  return (
    <button
      className={`${baseClasses} ${variantClasses[variant]}`}
      onClick={onClick}
      title={title}
      disabled={disabled}
    >
      {children}
    </button>
  )
}

export default ViewPrimaryActions
