import { Badge, type BadgeTone } from '../../../shared/ui/badge'
import type { MonthlyClosureStatus } from '../api/closures-api'

const STATUS_BADGE: Record<MonthlyClosureStatus, { label: string; tone: BadgeTone }> = {
  CLOSED: { label: 'Fechado', tone: 'success' },
  REOPENED: { label: 'Reaberto', tone: 'warning' },
}

interface MonthlyClosureStatusBadgeProps {
  status: MonthlyClosureStatus
}

export function MonthlyClosureStatusBadge({ status }: MonthlyClosureStatusBadgeProps) {
  const { label, tone } = STATUS_BADGE[status]
  return (
    <Badge tone={tone} data-status={status}>
      {label}
    </Badge>
  )
}
