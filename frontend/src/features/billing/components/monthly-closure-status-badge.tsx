import type { MonthlyClosureStatus } from '../api/closures-api'
import './monthly-closure-status-badge.css'

const STATUS_LABELS: Record<MonthlyClosureStatus, string> = {
  CLOSED: 'Fechado',
  REOPENED: 'Reaberto',
}

interface MonthlyClosureStatusBadgeProps {
  status: MonthlyClosureStatus
}

export function MonthlyClosureStatusBadge({ status }: MonthlyClosureStatusBadgeProps) {
  return (
    <span className="monthly-closure-status-badge" data-status={status}>
      <span className="monthly-closure-status-badge__dot" />
      {STATUS_LABELS[status]}
    </span>
  )
}
