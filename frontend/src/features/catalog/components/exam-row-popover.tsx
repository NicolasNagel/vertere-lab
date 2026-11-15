import { useQueries } from '@tanstack/react-query'
import { Link } from 'react-router'

import { formatCurrencyBRL, formatDate } from '../../../shared/lib/formatters'
import { Badge } from '../../../shared/ui/badge'
import { KebabMenu, type KebabMenuItem } from '../../../shared/ui/kebab-menu'
import type { Species } from '../../patients/api/patients-api'
import { fetchExam, type Exam, type ExamCategory } from '../api/catalog-api'
import { examQueryKey } from '../api/use-exam-query'
import '../../../shared/ui/button.css'
import '../../attendances/components/attendance-row-popover.css'

export const EXAM_POPOVER_TITLE_ID = 'exam-row-popover-title'

interface ExamRowPopoverProps {
  exam: Exam
  categories: ExamCategory[]
  species: Species[]
  /** `catalog.manage`: libera "Inativar"; editar acontece nos blocos do detalhe, como na Operação. */
  canManage: boolean
  onClose: () => void
  onDeactivate: (examId: string) => void
}

/** Resumo do exame, aberto ao clicar na linha da lista — mesmo padrão do resumo de atendimento. */
export function ExamRowPopover({
  exam,
  categories,
  species,
  canManage,
  onClose,
  onDeactivate,
}: ExamRowPopoverProps) {
  const components = useQueries({
    queries: exam.componentExamIds.map((id) => ({
      queryKey: examQueryKey(id),
      queryFn: () => fetchExam(id),
    })),
  })
  const categoryName = categories.find((category) => category.id === exam.categoryId)?.name ?? '—'
  const speciesNames = species
    .filter((item) => exam.speciesIds.includes(item.id))
    .map((item) => item.name)
    .join(' · ')
  const hasStart = exam.priceValidFrom && !exam.priceValidFrom.startsWith('1900')
  const menuItems: KebabMenuItem[] =
    canManage && exam.status === 'ACTIVE'
      ? [
          {
            label: 'Inativar exame',
            onSelect: () => onDeactivate(exam.id),
            destructive: true,
          },
        ]
      : []

  return (
    <aside className="attendance-row-popover" aria-label="Resumo do exame">
      <header className="attendance-row-popover__header">
        <div className="attendance-row-popover__heading">
          <h2 id={EXAM_POPOVER_TITLE_ID} className="attendance-row-popover__title">
            {exam.name}
          </h2>
          <div className="attendance-row-popover__sub">
            <Badge tone={exam.status === 'ACTIVE' ? 'success' : 'neutral'}>
              {exam.status === 'ACTIVE' ? 'Ativo' : 'Inativo'}
            </Badge>
            <span>{exam.code}</span>
            {exam.isPanel && <span>Pacote · {exam.componentExamIds.length} exames</span>}
          </div>
        </div>
        <div className="attendance-row-popover__actions">
          <Link
            to={`/cadastros/exames/${exam.id}`}
            className="button button--secondary attendance-row-popover__open"
          >
            Abrir exame
          </Link>
          {menuItems.length > 0 && <KebabMenu label="Mais ações" items={menuItems} />}
          <button
            type="button"
            className="attendance-row-popover__close"
            aria-label="Fechar resumo"
            onClick={onClose}
          >
            ×
          </button>
        </div>
      </header>

      <div className="attendance-row-popover__body">
        <dl className="attendance-row-popover__fields">
          <dt>Categoria</dt>
          <dd>{categoryName}</dd>
          <dt>Espécies</dt>
          <dd>{speciesNames || '—'}</dd>
          {exam.description && (
            <>
              <dt>Descrição</dt>
              <dd>{exam.description}</dd>
            </>
          )}
          {exam.priceBase !== null && (
            <>
              <dt>Preço</dt>
              <dd>
                {formatCurrencyBRL(exam.priceBase)}
                <span className="attendance-row-popover__muted">
                  {hasStart && exam.priceValidFrom
                    ? `vigente desde ${formatDate(exam.priceValidFrom)}`
                    : 'sem data de início'}
                  {exam.priceValidTo ? ` até ${formatDate(exam.priceValidTo)}` : ''}
                </span>
              </dd>
            </>
          )}
        </dl>

        {exam.isPanel && (
          <section aria-labelledby="exam-row-popover-components">
            <h3 id="exam-row-popover-components" className="attendance-row-popover__section">
              Exames do pacote
            </h3>
            <ul className="attendance-row-popover__exams">
              {components.map((query, index) => (
                <li key={exam.componentExamIds[index]}>
                  <span>{query.data?.name ?? '…'}</span>
                </li>
              ))}
            </ul>
          </section>
        )}
      </div>
    </aside>
  )
}
