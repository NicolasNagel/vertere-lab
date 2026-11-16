import type { ReactNode } from 'react'

import './page-header.css'

interface PageHeaderProps {
  title: string
  /** Linha pequena acima do título (data, contexto). O caminho já aparece no breadcrumb. */
  subtitle?: ReactNode
  actions?: ReactNode
}

export function PageHeader({ title, subtitle, actions }: PageHeaderProps) {
  return (
    <header className="page-header">
      <div className="page-header__text">
        {subtitle && <div className="page-header__subtitle">{subtitle}</div>}
        <h1 className="page-header__title">{title}</h1>
      </div>
      {actions && <div className="page-header__actions">{actions}</div>}
    </header>
  )
}
