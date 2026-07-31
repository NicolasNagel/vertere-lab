import type { AttendanceStatus } from '../api/attendances-api'
import './attendance-status-badge.css'

/** Labels reais do domínio — não são os mesmos rótulos do mockup
 * (`3-operacoes-lista.html` mostra "Aguardando coleta"/"Em análise"/"Laudo
 * pendente", que descrevem um fluxo laboratorial que ainda não existe no
 * backend). `AttendanceStatus` hoje só cobre o ciclo de vida do registro
 * em si. */
const STATUS_LABELS: Record<AttendanceStatus, string> = {
  DRAFT: 'Rascunho',
  CONFIRMED: 'Confirmado',
  IN_PROGRESS: 'Em andamento',
  COMPLETED: 'Concluído',
  CANCELLED: 'Cancelado',
  ON_HOLD: 'Em espera',
}

interface AttendanceStatusBadgeProps {
  status: AttendanceStatus
}

export function AttendanceStatusBadge({ status }: AttendanceStatusBadgeProps) {
  return (
    <span className="attendance-status-badge" data-status={status}>
      <span className="attendance-status-badge__dot" />
      {STATUS_LABELS[status]}
    </span>
  )
}
