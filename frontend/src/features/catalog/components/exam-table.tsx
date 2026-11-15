import { formatCurrencyBRL } from '../../../shared/lib/formatters'
import { Badge } from '../../../shared/ui/badge'
import { KebabMenu, type KebabMenuItem } from '../../../shared/ui/kebab-menu'
import type { Species } from '../../patients/api/patients-api'
import type { Exam, ExamCategory } from '../api/catalog-api'
import './exam-table.css'

interface ExamTableProps {
  exams: Exam[]
  categories: ExamCategory[]
  species: Species[]
  isLoading: boolean
  isError: boolean
  canManage: boolean
  priceVisible: boolean
  /** Linha com o resumo aberto. */
  selectedId?: string | null
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
  selectedId = null,
  onRowClick,
  onDeactivate,
}: ExamTableProps) {
  const categoryNameById = new Map(categories.map((category) => [category.id, category.name]))
  const speciesNameById = new Map(species.map((item) => [item.id, item.name]))

  if (isLoading) return <p className="exam-table__hint">Carregando…</p>
  if (isError) {
    return (
      <p role="alert" className="exam-table__hint exam-table__hint--error">
        Não foi possível carregar os exames. Tente novamente.
      </p>
    )
  }
  if (exams.length === 0) {
    return <p className="exam-table__hint">Nenhum exame encontrado para os filtros selecionados.</p>
  }

  return (
    <div className="exam-table">
      <table className="exam-table__table">
        <thead>
          <tr>
            <th scope="col">Código</th>
            <th scope="col">Exame</th>
            <th scope="col">Categoria</th>
            <th scope="col">Espécies</th>
            {priceVisible && (
              <th scope="col" className="exam-table__num">
                Preço
              </th>
            )}
            <th scope="col">Status</th>
            <th scope="col" className="exam-table__actions-header">
              Ações
            </th>
          </tr>
        </thead>
        <tbody>
          {exams.map((exam) => {
            const menuItems: KebabMenuItem[] =
              canManage && exam.status !== 'INACTIVE'
                ? [{ label: 'Inativar', onSelect: () => onDeactivate(exam.id), destructive: true }]
                : []
            const speciesLabel = exam.speciesIds
              .map((id) => speciesNameById.get(id))
              .filter((name): name is string => Boolean(name))
              .join(' · ')

            return (
              <tr
                key={exam.id}
                data-inactive={exam.status === 'INACTIVE' || undefined}
                data-selected={exam.id === selectedId || undefined}
                onClick={() => onRowClick(exam.id)}
              >
                <td className="exam-table__code">{exam.code}</td>
                <td>
                  <div className="exam-table__name">
                    <button
                      type="button"
                      className="exam-table__name-link"
                      title={exam.name}
                      onClick={(event) => {
                        event.stopPropagation()
                        onRowClick(exam.id)
                      }}
                    >
                      {exam.name}
                    </button>
                    {exam.isPanel && (
                      <span className="exam-table__chip">
                        Pacote · {exam.componentExamIds.length} exames
                      </span>
                    )}
                  </div>
                </td>
                <td>
                  <span className="exam-table__chip">
                    {categoryNameById.get(exam.categoryId) ?? '—'}
                  </span>
                </td>
                <td className="exam-table__muted">{speciesLabel || '—'}</td>
                {priceVisible && (
                  <td className="exam-table__num exam-table__price">
                    {exam.priceBase ? formatCurrencyBRL(exam.priceBase) : '—'}
                  </td>
                )}
                <td>
                  <Badge tone={exam.status === 'ACTIVE' ? 'success' : 'neutral'}>
                    {exam.status === 'ACTIVE' ? 'Ativo' : 'Inativo'}
                  </Badge>
                </td>
                <td className="exam-table__actions" onClick={(event) => event.stopPropagation()}>
                  {menuItems.length > 0 && (
                    <KebabMenu label={`Ações para ${exam.name}`} items={menuItems} />
                  )}
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
