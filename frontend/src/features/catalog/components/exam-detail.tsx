import { Button } from '../../../shared/ui/button'
import { KebabMenu, type KebabMenuItem } from '../../../shared/ui/kebab-menu'
import { useSpeciesQuery } from '../../patients/api/use-species-query'
import { useActiveExamCategoriesQuery } from '../api/use-active-exam-categories-query'
import { useExamCategoryQuery } from '../api/use-exam-category-query'
import type { Exam, ExamFormValues, ExamStatus } from '../api/catalog-api'
import { ExamForm } from './exam-form'
import './exam-detail.css'

const STATUS_LABELS: Record<Exam['status'], string> = {
  ACTIVE: 'Ativo',
  INACTIVE: 'Inativo',
}

function displayValue(value: string | null): string {
  return value && value.trim().length > 0 ? value : '—'
}

interface ExamDetailProps {
  exam: Exam | null
  isLoading: boolean
  isEditing: boolean
  canManage: boolean
  submitting: boolean
  submitError?: unknown
  onStartEdit: () => void
  onCancelEdit: () => void
  onSubmitUpdate: (values: ExamFormValues & { status: ExamStatus }) => void
  onDeactivate: () => void
}

export function ExamDetail({
  exam,
  isLoading,
  isEditing,
  canManage,
  submitting,
  submitError,
  onStartEdit,
  onCancelEdit,
  onSubmitUpdate,
  onDeactivate,
}: ExamDetailProps) {
  const categoriesQuery = useActiveExamCategoriesQuery()
  const speciesQuery = useSpeciesQuery()
  // Categoria pode ter sido inativada depois da criação do exame — nesse
  // caso ela não aparece em categoriesQuery (só ativas). Busca avulsa para
  // não mostrar "—" para um exame que na verdade tem categoria.
  const currentCategoryMissing =
    exam !== null &&
    !categoriesQuery.isLoading &&
    !(categoriesQuery.data ?? []).some((category) => category.id === exam.categoryId)
  const missingCategoryQuery = useExamCategoryQuery(
    currentCategoryMissing && exam ? exam.categoryId : null,
  )

  if (isLoading) {
    return (
      <div className="exam-detail">
        <p className="exam-detail__empty">Carregando…</p>
      </div>
    )
  }

  if (!exam) {
    return (
      <div className="exam-detail">
        <p className="exam-detail__empty">Selecione um exame na lista ao lado.</p>
      </div>
    )
  }

  if (isEditing) {
    return (
      <div className="exam-detail">
        <ExamForm
          exam={exam}
          submitting={submitting}
          error={submitError}
          onCancel={onCancelEdit}
          onSubmitUpdate={onSubmitUpdate}
        />
      </div>
    )
  }

  const categoryName =
    categoriesQuery.data?.find((category) => category.id === exam.categoryId)?.name ??
    missingCategoryQuery.data?.name ??
    '—'
  const speciesNames = exam.speciesIds
    .map((id) => speciesQuery.data?.find((species) => species.id === id)?.name)
    .filter((name): name is string => Boolean(name))

  const priceHidden = exam.priceBase === null

  const menuItems: KebabMenuItem[] =
    exam.status !== 'INACTIVE'
      ? [{ label: 'Inativar', onSelect: onDeactivate, destructive: true }]
      : []

  return (
    <div className="exam-detail">
      <div className="exam-detail__content">
        <div className="exam-detail__header">
          <div>
            <div className="exam-detail__title-row">
              <h2 className="exam-detail__title">{exam.name}</h2>
              <span className="exam-detail__status" data-status={exam.status}>
                {STATUS_LABELS[exam.status]}
              </span>
            </div>
          </div>
          {canManage && (
            <div className="exam-detail__actions">
              <Button
                type="button"
                variant="ghost"
                className="exam-detail__edit"
                onClick={onStartEdit}
              >
                Editar
              </Button>
              {menuItems.length > 0 && <KebabMenu label="Mais ações" items={menuItems} />}
            </div>
          )}
        </div>

        <div className="exam-detail__cards">
          <div className="exam-detail__card">
            <div className="exam-detail__card-title">Dados gerais</div>
            <dl className="exam-detail__fields">
              <dt>Código</dt>
              <dd className="exam-detail__mono">{exam.code}</dd>
              <dt>Categoria</dt>
              <dd>{categoryName}</dd>
              <dt>Descrição</dt>
              <dd>{displayValue(exam.description)}</dd>
              <dt>Espécies atendidas</dt>
              <dd>{speciesNames.length > 0 ? speciesNames.join(', ') : '—'}</dd>
            </dl>
          </div>

          <div className="exam-detail__card">
            <div className="exam-detail__card-title">Preço</div>
            {priceHidden ? (
              <p className="exam-detail__price-hidden">
                Você não tem permissão para visualizar valores.
              </p>
            ) : (
              <dl className="exam-detail__fields">
                <dt>Preço base</dt>
                <dd>{exam.priceBase}</dd>
                <dt>Adicional de plantão</dt>
                <dd>
                  {exam.plantaoSurchargePercent
                    ? `${exam.plantaoSurchargePercent}%`
                    : exam.plantaoSurchargeFixed
                      ? exam.plantaoSurchargeFixed
                      : '—'}
                </dd>
              </dl>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
