import type { AttendanceStatus, AttendanceStatusCounts } from '../api/attendances-api'
import './attendance-status-tabs.css'

const STATUS_TAB_LABELS: Record<AttendanceStatus, string> = {
  DRAFT: 'Rascunho',
  CONFIRMED: 'Confirmado',
  IN_PROGRESS: 'Em andamento',
  COMPLETED: 'Concluído',
  CANCELLED: 'Cancelado',
  ON_HOLD: 'Em espera',
}

const STATUS_TAB_ORDER: AttendanceStatus[] = [
  'DRAFT',
  'CONFIRMED',
  'IN_PROGRESS',
  'COMPLETED',
  'ON_HOLD',
  'CANCELLED',
]

interface AttendanceStatusTabsProps {
  counts: AttendanceStatusCounts | undefined
  value: AttendanceStatus | ''
  onChange: (status: AttendanceStatus | '') => void
}

export function AttendanceStatusTabs({ counts, value, onChange }: AttendanceStatusTabsProps) {
  return (
    <div className="attendance-status-tabs" role="tablist" aria-label="Filtrar por status">
      <button
        type="button"
        role="tab"
        aria-selected={value === ''}
        className="attendance-status-tabs__tab"
        data-active={value === ''}
        onClick={() => onChange('')}
      >
        Todos{counts ? <b>{counts.total}</b> : null}
      </button>
      {STATUS_TAB_ORDER.map((status) => {
        const count = counts?.byStatus[status] ?? 0
        if (counts && count === 0) return null
        return (
          <button
            key={status}
            type="button"
            role="tab"
            aria-selected={value === status}
            className="attendance-status-tabs__tab"
            data-active={value === status}
            onClick={() => onChange(status)}
          >
            {STATUS_TAB_LABELS[status]}
            {counts ? <b>{count}</b> : null}
          </button>
        )
      })}
    </div>
  )
}
