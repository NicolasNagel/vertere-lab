import type { ReactNode } from 'react'

import { BrandPanel } from './brand-panel'
import './auth-layout.css'

export function AuthLayout({ children }: { children: ReactNode }) {
  return (
    <main className="auth-layout">
      <div className="auth-layout__card">
        <BrandPanel />
        <div className="auth-layout__form-panel">{children}</div>
      </div>
    </main>
  )
}
