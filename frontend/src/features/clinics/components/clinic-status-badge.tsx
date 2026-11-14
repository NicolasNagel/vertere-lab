import { Badge, type BadgeTone } from '../../../shared/ui/badge'
import type { Clinic } from '../api/clinics-api'

const STATUS_BADGE: Record<Clinic['status'], { label: string; tone: BadgeTone }> = {
  ACTIVE: { label: 'Ativo', tone: 'success' },
  INACTIVE: { label: 'Inativo', tone: 'neutral' },
  DELINQUENT: { label: 'Negativado', tone: 'danger' },
  SPECIAL: { label: 'Especial', tone: 'info' },
}

export function ClinicStatusBadge({ status }: { status: Clinic['status'] }) {
  const { label, tone } = STATUS_BADGE[status]
  return (
    <Badge tone={tone} data-status={status}>
      {label}
    </Badge>
  )
}
