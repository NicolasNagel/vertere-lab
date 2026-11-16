import { Badge, type BadgeTone } from '../../../shared/ui/badge'
import type { AttendanceStatus } from '../api/attendances-api'

/** Labels reais do domínio — não são os rótulos do mockup (`3-operacoes-lista.html` mostra
 * "Aguardando coleta"/"Em análise"/"Laudo pendente", fluxo laboratorial que ainda não existe no
 * backend). `AttendanceStatus` hoje só cobre o ciclo de vida do registro em si. */
const STATUS_BADGE: Record<AttendanceStatus, { label: string; tone: BadgeTone }> = {
  DRAFT: { label: 'Rascunho', tone: 'neutral' },
  CONFIRMED: { label: 'Confirmado', tone: 'success' },
  IN_PROGRESS: { label: 'Em andamento', tone: 'warning' },
  COMPLETED: { label: 'Concluído', tone: 'info' },
  CANCELLED: { label: 'Cancelado', tone: 'danger' },
  ON_HOLD: { label: 'Em espera', tone: 'warning' },
}

interface AttendanceStatusBadgeProps {
  status: AttendanceStatus
}

export function AttendanceStatusBadge({ status }: AttendanceStatusBadgeProps) {
  const { label, tone } = STATUS_BADGE[status]
  return (
    <Badge tone={tone} data-status={status}>
      {label}
    </Badge>
  )
}
