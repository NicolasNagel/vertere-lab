import { KebabMenu, type KebabMenuItem } from '../../../shared/ui/kebab-menu'
import { formatCurrencyBRL } from '../../../shared/lib/formatters'
import type { Species } from '../../patients/api/patients-api'
import type { Exam, ExamCategory } from '../api/catalog-api'
import './exam-table.css'

const STATUS_LABELS: Record<Exam['status'], string> = {
  ACTIVE: 'Ativo',
  INACTIVE: 'Inativo',
}

interface ExamTableProps {
  exams: Exam[]
  categories: ExamCategory[]
  species: Species[]
  isLoading: boolean
  isError: boolean
  canManage: boolean
  priceVisible: boolean
  onRowClick: (examId: string) => void
  onDeactivate: (examId: string) => void
}

export function ExamTable({
  exams,
  categories,
  species,
  isLoading,
  isError,
  canManage,
  priceVisible,
  onRowClick,
  onDeactivate,
}: ExamTableProps) {
  const categoryNameById = new Map(categories.map((category) => [category.id, category.name]))
  const speciesNameById = new Map(species.map((item) => [item.id, item.name]))

  return (
    <div className="exam-table-panel">
      <div className="exam-table">
        <div className="exam-table__header" data-price-visible={priceVisible}>
          <div>Cód.</div>
          <div>Exame</div>
          <div>Categoria</div>
          {priceVisible && <div>Preço base</div>}
          <div>Espécies</div>
          <div />
        </div>

        {isLoading && <p className="exam-table__empty">Carregando…</p>}
        {isError && (
          <p role="alert" className="exam-table__empty">
            Não foi possível carregar os exames.
          </p>
        )}
        {!isLoading && !isError && exams.length === 0 && (
          <p className="exam-table__empty">Nenhum exame encontrado.</p>
        )}

        {!isLoading &&
          exams.map((exam) => {
            const menuItems: KebabMenuItem[] =
              canManage && exam.status !== 'INACTIVE'
                ? [{ label: 'Inativar', onSelect: () => onDeactivate(exam.id), destructive: true }]
                : []
            const speciesLabel = exam.speciesIds
              .map((id) => speciesNameById.get(id))
              .filter((name): name is string => Boolean(name))
              .join(' · ')

            return (
              <div
                key={exam.id}
                className="exam-table__row"
                data-price-visible={priceVisible}
                data-clickable
                role="button"
                tabIndex={0}
                onClick={() => onRowClick(exam.id)}
                onKeyDown={(event) => {
                  if (event.key === 'Enter' || event.key === ' ') {
                    event.preventDefault()
                    onRowClick(exam.id)
                  }
                }}
              >
                <div className="exam-table__code" title={exam.code}>
                  {exam.code}
                </div>
                <div>
                  <div className="exam-table__name">
                    <span className="exam-table__name-text" title={exam.name}>
                      {exam.name}
                    </span>
                    <span className="exam-table__status" data-status={exam.status}>
                      {STATUS_LABELS[exam.status]}
                    </span>
                    {exam.isPanel && (
                      <span className="exam-table__panel-badge">
                        Pacote · {exam.componentExamIds.length} exames
                      </span>
                    )}
                  </div>
                  {exam.description && (
                    <div className="exam-table__description">{exam.description}</div>
                  )}
                </div>
                <div>
                  <span className="exam-table__category-badge">
                    {categoryNameById.get(exam.categoryId) ?? '—'}
                  </span>
                </div>
                {priceVisible && (
                  <div className="exam-table__price">
                    {exam.priceBase ? formatCurrencyBRL(exam.priceBase) : '—'}
                  </div>
                )}
                <div className="exam-table__species">{speciesLabel || '—'}</div>
                <div className="exam-table__menu" onClick={(event) => event.stopPropagation()}>
                  {menuItems.length > 0 && <KebabMenu label={`Ações para ${exam.name}`} items={menuItems} />}
                </div>
              </div>
            )
          })}
      </div>
    </div>
  )
}
