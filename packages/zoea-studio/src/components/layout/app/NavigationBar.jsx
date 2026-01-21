import { useNavigate } from 'react-router-dom'
import {
  ChevronsUpDown,
  ClipboardList,
  FileText,
  Home,
  LayoutDashboard,
  LogOut,
  MessageSquare,
  Shapes,
  User,
  Workflow,
} from 'lucide-react'
import clsx from 'clsx'
import { useLayoutStore } from '../../../stores/layoutStore'
import { useWorkspaceStore } from '../../../stores/workspaceStore'
import { useAuthStore } from '../../../stores/authStore'
import { Avatar, AvatarFallback } from '@/components/ui/avatar'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'

const iconMap = {
  home: Home,
  'layout-dashboard': LayoutDashboard,
  dashboard: LayoutDashboard,
  'message-square': MessageSquare,
  chat: MessageSquare,
  documents: FileText,
  'file-text': FileText,
  clipboards: ClipboardList,
  'clipboard-list': ClipboardList,
  canvas: Shapes,
  shape: Shapes,
  workflows: Workflow,
  flows: Workflow,
}

function NavigationBar({ items = [], onNavigate }) {
  const navigate = useNavigate()
  const projectsBarOpen = useLayoutStore((state) => state.projectsBarOpen)
  const getCurrentProject = useWorkspaceStore((state) => state.getCurrentProject)
  const user = useAuthStore((state) => state.user)
  const logout = useAuthStore((state) => state.logout)

  // Get current project for primary header styling
  const currentProject = getCurrentProject()
  const usePrimaryHeader = currentProject?.use_primary_header ?? false

  // Use primary color when projects bar is collapsed and setting is enabled
  const usePrimaryNav = usePrimaryHeader && !projectsBarOpen

  // Get initials for avatar fallback
  const getInitials = (name) => {
    if (!name) return 'U'
    return name
      .split(' ')
      .map((n) => n[0])
      .join('')
      .toUpperCase()
      .slice(0, 2)
  }

  const handleLogout = () => {
    logout()
  }

  const handleAccountClick = () => {
    navigate('/account')
  }

  return (
    <nav
      className={clsx(
        'w-[72px] min-w-[72px] flex flex-col items-center py-3 gap-2',
        usePrimaryNav
          ? 'bg-primary border-r border-primary/20'
          : 'bg-sidebar border-r border-sidebar-border'
      )}
    >
      {items.map((item) => {
        const Icon = iconMap[item.icon] || LayoutDashboard
        const isActive = Boolean(item.active)
        return (
          <button
            key={item.id}
            type="button"
            onClick={() => {
              if (onNavigate && item.path) {
                onNavigate(item.path)
              }
            }}
            className={clsx(
              'w-14 py-2 px-1 rounded-lg flex flex-col items-center justify-center gap-1 transition-colors',
              usePrimaryNav
                ? isActive
                  ? 'bg-primary-foreground/20 text-primary-foreground'
                  : 'text-primary-foreground/80 hover:bg-primary-foreground/10 hover:text-primary-foreground'
                : isActive
                  ? 'bg-sidebar-primary text-sidebar-primary-foreground'
                  : 'text-sidebar-foreground/80 hover:bg-sidebar-accent hover:text-sidebar-foreground'
            )}
            aria-label={item.label}
            aria-current={isActive ? 'page' : undefined}
          >
            <Icon className="h-5 w-5" strokeWidth={isActive ? 2.5 : 2.25} aria-hidden />
            <span className="text-[10px] font-semibold leading-tight truncate max-w-full">
              {item.label}
            </span>
          </button>
        )
      })}

      {/* Spacer to push user menu to bottom */}
      <div className="flex-1" />

      {/* User Account Menu */}
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <button
            type="button"
            className={clsx(
              'w-14 py-2 px-1 rounded-lg flex flex-col items-center justify-center gap-1 transition-colors cursor-pointer',
              usePrimaryNav
                ? 'text-primary-foreground/80 hover:bg-primary-foreground/10 hover:text-primary-foreground'
                : 'text-sidebar-foreground/80 hover:bg-sidebar-accent hover:text-sidebar-foreground'
            )}
            aria-label="Account menu"
          >
            <Avatar className="h-8 w-8">
              <AvatarFallback
                className={clsx(
                  'text-xs font-semibold',
                  usePrimaryNav
                    ? 'bg-primary-foreground/20 text-primary-foreground'
                    : 'bg-sidebar-primary text-sidebar-primary-foreground'
                )}
              >
                {getInitials(user?.username)}
              </AvatarFallback>
            </Avatar>
          </button>
        </DropdownMenuTrigger>
        <DropdownMenuContent
          className="w-56"
          align="start"
          side="right"
          sideOffset={8}
        >
          <DropdownMenuLabel className="font-normal">
            <div className="flex flex-col space-y-1">
              <p className="text-sm font-medium leading-none">
                {user?.username || 'User'}
              </p>
              {user?.email && (
                <p className="text-xs leading-none text-muted-foreground">
                  {user.email}
                </p>
              )}
              {user?.organization && (
                <p className="text-xs leading-none text-muted-foreground">
                  {user.organization.name}
                </p>
              )}
            </div>
          </DropdownMenuLabel>
          <DropdownMenuSeparator />
          <DropdownMenuGroup>
            <DropdownMenuItem onClick={handleAccountClick} className="cursor-pointer">
              <User className="mr-2 h-4 w-4" />
              Account
            </DropdownMenuItem>
          </DropdownMenuGroup>
          <DropdownMenuSeparator />
          <DropdownMenuItem onClick={handleLogout} className="cursor-pointer text-destructive focus:text-destructive">
            <LogOut className="mr-2 h-4 w-4" />
            Log out
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
    </nav>
  )
}

export default NavigationBar
