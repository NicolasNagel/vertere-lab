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
  // Sem itens (carregando, vazio ou erro) não há o que paginar: a lista já diz o que houve, e o
  // rodapé "Nenhum … ‹ 1 / 1 ›" só repetia isso.
  if (total === 0) return null

  const totalPages = Math.max(1, Math.ceil(total / pageSize))
  const rangeStart = (page - 1) * pageSize + 1
  const rangeEnd = Math.min(page * pageSize, total)

  return (
    <div className="attendance-list-pagination">
      <span className="attendance-list-pagination__summary">
        Mostrando {rangeStart}–{rangeEnd} de {total} {pluralize(total, itemLabel[0], itemLabel[1])}
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
