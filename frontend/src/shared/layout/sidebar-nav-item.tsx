import type { ReactNode } from 'react'
import { NavLink } from 'react-router'

export interface SidebarNavItemProps {
  icon: ReactNode
  label: string
  to: string | null
  badgeCount?: number
  /** Tooltip used while the sidebar is collapsed to icons only. */
  title?: string
}

export function SidebarNavItem({ icon, label, to, badgeCount, title }: SidebarNavItemProps) {
  const content = (
    <>
      {icon}
      <span className="sidebar-nav-item__label">{label}</span>
      {badgeCount !== undefined && <span className="sidebar-nav-item__badge">{badgeCount}</span>}
    </>
  )

  if (to === null) {
    return (
      <span
        className="sidebar-nav-item sidebar-nav-item--disabled"
        aria-disabled="true"
        tabIndex={-1}
        title={title}
      >
        {content}
      </span>
    )
  }

  return (
    <NavLink
      to={to}
      title={title}
      end={to === '/'}
      className={({ isActive }) =>
        isActive ? 'sidebar-nav-item sidebar-nav-item--active' : 'sidebar-nav-item'
      }
    >
      {content}
    </NavLink>
  )
}
