import { Outlet } from 'react-router'

import { Sidebar } from './sidebar'
import './app-shell.css'

export function AppShell() {
  return (
    <div className="app-shell">
      <Sidebar />
      <main className="app-shell__content">
        <Outlet />
      </main>
    </div>
  )
}
