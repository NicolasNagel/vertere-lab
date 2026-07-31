import { pluralize } from '../../../shared/lib/formatters'
import './attendance-list-pagination.css'

interface AttendanceListPaginationProps {
  page: number
  pageSize: number
  total: number
  onPageChange: (page: number) => void
}

export function AttendanceListPagination({
  page,
  pageSize,
  total,
  onPageChange,
}: AttendanceListPaginationProps) {
  const totalPages = Math.max(1, Math.ceil(total / pageSize))
  const rangeStart = total === 0 ? 0 : (page - 1) * pageSize + 1
  const rangeEnd = Math.min(page * pageSize, total)

  return (
    <div className="attendance-list-pagination">
      <span className="attendance-list-pagination__summary">
        {total === 0
          ? 'Nenhum atendimento'
          : `Mostrando ${rangeStart}–${rangeEnd} de ${total} ${pluralize(total, 'atendimento', 'atendimentos')}`}
      </span>
      <div className="attendance-list-pagination__controls">
        <button
          type="button"
          className="attendance-list-pagination__button"
          disabled={page <= 1}
          onClick={() => onPageChange(page - 1)}
          aria-label="Página anterior"
        >
          ‹
        </button>
        <span className="attendance-list-pagination__current">
          {page} / {totalPages}
        </span>
        <button
          type="button"
          className="attendance-list-pagination__button"
          disabled={page >= totalPages}
          onClick={() => onPageChange(page + 1)}
          aria-label="Próxima página"
        >
          ›
        </button>
      </div>
    </div>
  )
}
