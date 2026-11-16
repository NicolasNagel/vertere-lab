import { useState } from 'react'
import { Outlet } from 'react-router'

import { Sidebar } from './sidebar'
import { Topbar } from './topbar'
import './app-shell.css'

const COLLAPSED_KEY = 'vertere.sidebar.collapsed'

function readCollapsed(): boolean {
  try {
    return localStorage.getItem(COLLAPSED_KEY) === '1'
  } catch {
    return false
  }
}

function writeCollapsed(value: boolean): void {
  try {
    localStorage.setItem(COLLAPSED_KEY, value ? '1' : '0')
  } catch {
    // Armazenamento bloqueado: a preferência dura só a sessão.
  }
}

export function AppShell() {
  const [navigationOpen, setNavigationOpen] = useState(false)
  const [collapsed, setCollapsed] = useState(readCollapsed)

  function toggleCollapsed() {
    const next = !collapsed
    writeCollapsed(next)
    setCollapsed(next)
  }

  return (
    <div className={`app-shell${collapsed ? ' app-shell--collapsed' : ''}`}>
      <header className="app-shell__mobile-header">
        <button
          type="button"
          className="app-shell__menu-button"
          aria-label="Abrir navegação"
          aria-expanded={navigationOpen}
          onClick={() => setNavigationOpen(true)}
        >
          <span />
          <span />
          <span />
        </button>
        <span className="app-shell__mobile-brand">Vertere</span>
      </header>
      {navigationOpen && (
        <button
          type="button"
          className="app-shell__backdrop"
          aria-label="Fechar navegação"
          onClick={() => setNavigationOpen(false)}
        />
      )}
      <Sidebar
        mobileOpen={navigationOpen}
        collapsed={collapsed}
        onToggleCollapsed={toggleCollapsed}
        onNavigate={() => setNavigationOpen(false)}
      />
      <div className="app-shell__content">
        <Topbar />
        <main className="app-shell__main">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
