import { Outlet } from 'react-router-dom'

import { Sidebar } from './sidebar'
import './app-shell.css'

export function AppShell() {
  return (
    <div className="app-shell">
      <Sidebar />
      <div className="app-shell__content">
        <Outlet />
      </div>
    </div>
  )
}
