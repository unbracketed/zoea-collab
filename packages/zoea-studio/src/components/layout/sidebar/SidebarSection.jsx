import * as Collapsible from '@radix-ui/react-collapsible'
import { ChevronDown, ChevronRight } from 'lucide-react'
import clsx from 'clsx'

function SidebarSection({ id, title, open, onOpenChange, children, showDefaultTitle = true }) {
  return (
    <Collapsible.Root open={open} onOpenChange={(nextOpen) => onOpenChange?.(id, nextOpen)}>
      <div className="flex items-center justify-between text-sm font-semibold text-sidebar-foreground select-none">
        <div className="flex items-center gap-2">
          <Collapsible.Trigger asChild>
            <button
              type="button"
              className="inline-flex items-center justify-center h-8 w-8 rounded-md border border-sidebar-border bg-sidebar hover:bg-sidebar-accent text-sidebar-foreground transition-colors"
              aria-label={`${open ? 'Collapse' : 'Expand'} ${title}`}
            >
              {open ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
            </button>
          </Collapsible.Trigger>
          {showDefaultTitle && <span>{title}</span>}
        </div>
      </div>
      <Collapsible.Content
        className={clsx(
          'mt-2 space-y-2 overflow-hidden transition-all',
          open ? 'opacity-100' : 'opacity-0'
        )}
      >
        {children}
      </Collapsible.Content>
    </Collapsible.Root>
  )
}

export default SidebarSection
