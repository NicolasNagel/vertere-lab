import { SearchIcon } from '../../../shared/ui/icons'
import { pluralize } from '../../../shared/lib/formatters'
import type { Exam } from '../api/catalog-api'
import './exam-list.css'

const STATUS_LABELS: Record<Exam['status'], string> = {
  ACTIVE: 'Ativo',
  INACTIVE: 'Inativo',
}

interface ExamListProps {
  exams: Exam[]
  activeCount: number
  selectedId: string | null
  search: string
  isLoading: boolean
  onSearchChange: (value: string) => void
  onSelect: (id: string) => void
}

export function ExamList({
  exams,
  activeCount,
  selectedId,
  search,
  isLoading,
  onSearchChange,
  onSelect,
}: ExamListProps) {
  return (
    <div className="exam-list">
      <div className="exam-list__search">
        <SearchIcon className="exam-list__search-icon" />
        <input
          type="search"
          className="exam-list__search-input"
          placeholder="Buscar por nome ou código..."
          aria-label="Buscar exame"
          value={search}
          onChange={(event) => onSearchChange(event.target.value)}
        />
        <span className="exam-list__count">
          {activeCount} {pluralize(activeCount, 'ativo', 'ativos')}
        </span>
      </div>

      <div className="exam-list__rows" role="list">
        {isLoading && <p className="exam-list__empty">Carregando…</p>}
        {!isLoading && exams.length === 0 && (
          <p className="exam-list__empty">Nenhum exame encontrado.</p>
        )}
        {exams.map((exam) => (
          <button
            key={exam.id}
            type="button"
            role="listitem"
            className="exam-list__row"
            data-selected={exam.id === selectedId}
            onClick={() => onSelect(exam.id)}
          >
            <div className="exam-list__row-header">
              <span className="exam-list__row-name">{exam.name}</span>
              <span className="exam-list__row-status" data-status={exam.status}>
                {STATUS_LABELS[exam.status]}
              </span>
            </div>
            <div className="exam-list__row-code">{exam.code}</div>
          </button>
        ))}
      </div>
    </div>
  )
}
