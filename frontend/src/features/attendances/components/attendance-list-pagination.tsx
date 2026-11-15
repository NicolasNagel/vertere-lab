import { pluralize } from '../../../shared/lib/formatters'
import './attendance-list-pagination.css'

interface AttendanceListPaginationProps {
  page: number
  pageSize: number
  total: number
  /** Nome do item no resumo; Operação usa o padrão "atendimento". */
  itemLabel?: [singular: string, plural: string]
  onPageChange: (page: number) => void
}

export function AttendanceListPagination({
  page,
  pageSize,
  total,
  itemLabel = ['atendimento', 'atendimentos'],
  onPageChange,
}: AttendanceListPaginationProps) {
  const totalPages = Math.max(1, Math.ceil(total / pageSize))
  const rangeStart = total === 0 ? 0 : (page - 1) * pageSize + 1
  const rangeEnd = Math.min(page * pageSize, total)

  return (
    <div className="attendance-list-pagination">
      <span className="attendance-list-pagination__summary">
        {total === 0
          ? `Nenhum ${itemLabel[0]}`
          : `Mostrando ${rangeStart}–${rangeEnd} de ${total} ${pluralize(total, itemLabel[0], itemLabel[1])}`}
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
