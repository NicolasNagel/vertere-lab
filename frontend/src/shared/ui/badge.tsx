import type { ReactNode } from 'react'

import './badge.css'

export type BadgeTone = 'neutral' | 'info' | 'success' | 'warning' | 'danger'

interface BadgeProps {
  tone?: BadgeTone
  /** Estado nunca depende só da cor: o texto do status é sempre o filho. */
  children: ReactNode
  'data-status'?: string
}

export function Badge({ tone = 'neutral', children, ...rest }: BadgeProps) {
  return (
    <span className="badge" data-tone={tone} data-status={rest['data-status']}>
      <span className="badge__dot" aria-hidden="true" />
      {children}
    </span>
  )
}
