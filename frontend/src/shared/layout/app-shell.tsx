import { useState } from 'react'
import { Outlet } from 'react-router'

import { Sidebar } from './sidebar'
import './app-shell.css'

export function AppShell() {
  const [navigationOpen, setNavigationOpen] = useState(false)
  return (
    <div className="app-shell">
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
        <span className="app-shell__mobile-brand">VERTERE LAB</span>
      </header>
      {navigationOpen && (
        <button
          type="button"
          className="app-shell__backdrop"
          aria-label="Fechar navegação"
          onClick={() => setNavigationOpen(false)}
        />
      )}
      <Sidebar mobileOpen={navigationOpen} onNavigate={() => setNavigationOpen(false)} />
      <main className="app-shell__content">
        <Outlet />
      </main>
    </div>
  )
}
