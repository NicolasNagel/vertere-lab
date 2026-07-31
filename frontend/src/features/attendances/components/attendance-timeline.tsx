import { useState } from 'react'

import { formatDateTime } from '../../../shared/lib/formatters'
import { useAttendanceTimelineQuery } from '../api/use-attendance-timeline-query'
import './attendance-timeline.css'

const ACTION_LABELS: Record<string, string> = {
  'attendances.draft_created': 'Rascunho criado',
  'attendances.confirmed': 'Atendimento confirmado',
  'attendances.cancelled': 'Atendimento cancelado',
  'attendances.updated': 'Atendimento editado',
}

function describeAction(action: string): string {
  return ACTION_LABELS[action] ?? action
}

interface AttendanceTimelineProps {
  attendanceId: string
}

export function AttendanceTimeline({ attendanceId }: AttendanceTimelineProps) {
  const [expanded, setExpanded] = useState(false)
  const [page, setPage] = useState(1)
  const timelineQuery = useAttendanceTimelineQuery(attendanceId, page, expanded)

  const totalPages = timelineQuery.data ? Math.max(1, Math.ceil(timelineQuery.data.total / timelineQuery.data.pageSize)) : 1

  return (
    <div className="attendance-timeline">
      <button
        type="button"
        className="attendance-timeline__toggle"
        onClick={() => setExpanded((current) => !current)}
      >
        {expanded ? 'Ocultar histórico' : 'Ver histórico'}
      </button>

      {expanded && (
        <div className="attendance-timeline__panel">
          {timelineQuery.isLoading && <p className="attendance-timeline__hint">Carregando…</p>}

          {timelineQuery.isError && (
            <p className="attendance-timeline__hint">Não foi possível carregar o histórico.</p>
          )}

          {timelineQuery.data && timelineQuery.data.items.length === 0 && (
            <p className="attendance-timeline__hint">Nenhum evento registrado.</p>
          )}

          {timelineQuery.data && timelineQuery.data.items.length > 0 && (
            <>
              <ul className="attendance-timeline__list">
                {timelineQuery.data.items.map((entry) => (
                  <li key={entry.id} className="attendance-timeline__entry">
                    <div className="attendance-timeline__entry-header">
                      <span>{describeAction(entry.action)}</span>
                      <span className="attendance-timeline__entry-date">
                        {formatDateTime(entry.occurredAt)}
                      </span>
                    </div>
                    {entry.reason && (
                      <p className="attendance-timeline__entry-reason">Motivo: {entry.reason}</p>
                    )}
                  </li>
                ))}
              </ul>

              <div className="attendance-timeline__pagination">
                <button
                  type="button"
                  className="attendance-timeline__pagination-button"
                  disabled={page <= 1}
                  onClick={() => setPage((current) => current - 1)}
                  aria-label="Página anterior do histórico"
                >
                  ‹
                </button>
                <span className="attendance-timeline__pagination-current">
                  {page} / {totalPages}
                </span>
                <button
                  type="button"
                  className="attendance-timeline__pagination-button"
                  disabled={page >= totalPages}
                  onClick={() => setPage((current) => current + 1)}
                  aria-label="Próxima página do histórico"
                >
                  ›
                </button>
              </div>
            </>
          )}
        </div>
      )}
    </div>
  )
}
