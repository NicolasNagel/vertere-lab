import { pluralize } from '../lib/formatters'
import './pagination.css'

interface PaginationProps {
  itemLabel: [singular: string, plural: string]
  page: number
  pageSize: number
  total: number
  onPageChange: (page: number) => void
}

export function Pagination({
  itemLabel,
  page,
  pageSize,
  total,
  onPageChange,
}: PaginationProps) {
  const totalPages = Math.max(1, Math.ceil(total / pageSize))
  const rangeStart = total === 0 ? 0 : (page - 1) * pageSize + 1
  const rangeEnd = Math.min(page * pageSize, total)

  return (
    <nav className="pagination" aria-label="Paginação">
      <span className="pagination__summary">
        {total === 0
          ? `Nenhum ${itemLabel[0]}`
          : `${rangeStart}–${rangeEnd} de ${total} ${pluralize(total, ...itemLabel)}`}
      </span>
      <div className="pagination__controls">
        <button
          type="button"
          className="pagination__button"
          disabled={page <= 1}
          onClick={() => onPageChange(page - 1)}
          aria-label="Página anterior"
        >
          ‹
        </button>
        <span className="pagination__current" aria-live="polite">
          {page} / {totalPages}
        </span>
        <button
          type="button"
          className="pagination__button"
          disabled={page >= totalPages}
          onClick={() => onPageChange(page + 1)}
          aria-label="Próxima página"
        >
          ›
        </button>
      </div>
    </nav>
  )
}
