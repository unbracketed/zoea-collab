/**
 * Project Settings Navigation
 *
 * Sidebar navigation for project settings tabs.
 */

import clsx from 'clsx'
import { Settings, Palette, Mail, Bot, Wrench } from 'lucide-react'

const NAV_ITEMS = [
  { id: 'general', label: 'General', icon: Settings },
  { id: 'appearance', label: 'Appearance', icon: Palette },
  { id: 'email', label: 'Email', icon: Mail },
  { id: 'ai', label: 'AI Configuration', icon: Bot },
  { id: 'tools', label: 'Agent Tools', icon: Wrench },
]

function ProjectSettingsNav({ activeTab, onTabChange }) {
  return (
    <nav className="space-y-1 p-2">
      {NAV_ITEMS.map((item) => {
        const Icon = item.icon
        const isActive = activeTab === item.id
        return (
          <button
            key={item.id}
            type="button"
            onClick={() => onTabChange(item.id)}
            className={clsx(
              'w-full flex items-center gap-3 px-3 py-2 text-sm rounded-lg transition-colors',
              isActive
                ? 'bg-sidebar-primary text-sidebar-primary-foreground'
                : 'text-sidebar-foreground/80 hover:bg-sidebar-accent hover:text-sidebar-foreground'
            )}
            aria-current={isActive ? 'page' : undefined}
          >
            <Icon className="h-4 w-4" />
            {item.label}
          </button>
        )
      })}
    </nav>
  )
}

export default ProjectSettingsNav
