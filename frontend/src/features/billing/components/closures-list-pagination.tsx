import { pluralize } from '../../../shared/lib/formatters'
import './closures-list-pagination.css'

interface ClosuresListPaginationProps {
  page: number
  pageSize: number
  total: number
  onPageChange: (page: number) => void
}

export function ClosuresListPagination({
  page,
  pageSize,
  total,
  onPageChange,
}: ClosuresListPaginationProps) {
  const totalPages = Math.max(1, Math.ceil(total / pageSize))
  const rangeStart = total === 0 ? 0 : (page - 1) * pageSize + 1
  const rangeEnd = Math.min(page * pageSize, total)

  return (
    <div className="closures-list-pagination">
      <span className="closures-list-pagination__summary">
        {total === 0
          ? 'Nenhum fechamento'
          : `Mostrando ${rangeStart}–${rangeEnd} de ${total} ${pluralize(total, 'fechamento', 'fechamentos')}`}
      </span>
      <div className="closures-list-pagination__controls">
        <button
          type="button"
          className="closures-list-pagination__button"
          disabled={page <= 1}
          onClick={() => onPageChange(page - 1)}
          aria-label="Página anterior"
        >
          ‹
        </button>
        <span className="closures-list-pagination__current">
          {page} / {totalPages}
        </span>
        <button
          type="button"
          className="closures-list-pagination__button"
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
