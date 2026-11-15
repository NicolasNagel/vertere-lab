import { useQueries } from '@tanstack/react-query'
import { useNavigate, useParams } from 'react-router'

import { ApiError } from '../../../shared/api/errors'
import { formatCurrencyBRL, formatDate } from '../../../shared/lib/formatters'
import { Button } from '../../../shared/ui/button'
import { useAuth } from '../../auth/auth-context'
import { useSpeciesQuery } from '../../patients/api/use-species-query'
import { fetchExam } from '../api/catalog-api'
import { useActiveExamCategoriesQuery } from '../api/use-active-exam-categories-query'
import { examQueryKey, useExamQuery } from '../api/use-exam-query'
import { ExamDetailBlock } from './exam-detail-block'
import {
  CategorySpeciesForm,
  CompositionForm,
  IdentityForm,
  PriceForm,
  StatusForm,
} from './exam-detail-forms'
import '../../attendances/components/attendance-readonly-detail.css'

/** Detalhe do exame em blocos, cada um com "Editar" + motivo. Preço só com `pricing.read`
 * e só editável com `pricing.manage`; o backend é quem decide de verdade. */
export function ExamDetailPage() {
  const { examId } = useParams<{ examId: string }>()
  const navigate = useNavigate()
  const { user } = useAuth()
  const permissions = user?.permissions ?? []
  const canEdit = permissions.includes('catalog.manage')
  const canManagePrice = permissions.includes('pricing.manage')

  const examQuery = useExamQuery(examId ?? null)
  const categoriesQuery = useActiveExamCategoriesQuery()
  const speciesQuery = useSpeciesQuery()
  const exam = examQuery.data
  const componentQueries = useQueries({
    queries: (exam?.componentExamIds ?? []).map((id) => ({
      queryKey: examQueryKey(id),
      queryFn: () => fetchExam(id),
    })),
  })

  const back = (
    <Button type="button" variant="cancel" onClick={() => navigate('/cadastros/exames')}>
      Voltar
    </Button>
  )

  if (examQuery.isLoading) return <p className="attendance-readonly-detail__hint">Carregando…</p>
  if (examQuery.isError || !exam) {
    const forbidden = examQuery.error instanceof ApiError && examQuery.error.status === 403
    return (
      <div className="attendance-readonly-detail">
        <p role="alert">
          {forbidden ? 'Sem permissão para ver este exame.' : 'Não foi possível carregar o exame.'}
        </p>
        {back}
      </div>
    )
  }

  const categories = categoriesQuery.data ?? []
  const categoryName = categories.find((c) => c.id === exam.categoryId)?.name ?? '—'
  const speciesNames = (speciesQuery.data ?? [])
    .filter((s) => exam.speciesIds.includes(s.id))
    .map((s) => s.name)
    .join(' · ')
  const formProps = { exam, canManagePrice, onClose: () => undefined }
  const priceVisible = exam.priceBase !== null

  return (
    <div className="attendance-readonly-detail">
      <div>
        <h1 className="attendance-readonly-detail__section-title">
          {exam.name} <span className="attendance-readonly-detail__mono">{exam.code}</span>
        </h1>
        {back}
      </div>

      <ExamDetailBlock
        title="Identificação"
        examId={exam.id}
        canEdit={canEdit}
        form={({ close }) => <IdentityForm {...formProps} onClose={close} />}
      >
        <dl className="attendance-readonly-detail__fields">
          <dt>Nome</dt>
          <dd>{exam.name}</dd>
          <dt>Código</dt>
          <dd>{exam.code}</dd>
          <dt>Descrição</dt>
          <dd>{exam.description || '—'}</dd>
        </dl>
      </ExamDetailBlock>

      <ExamDetailBlock
        title="Categoria e espécies"
        examId={exam.id}
        canEdit={canEdit}
        form={({ close }) => (
          <CategorySpeciesForm {...formProps} categories={categories} onClose={close} />
        )}
      >
        <dl className="attendance-readonly-detail__fields">
          <dt>Categoria</dt>
          <dd>{categoryName}</dd>
          <dt>Espécies</dt>
          <dd>{speciesNames || '—'}</dd>
        </dl>
      </ExamDetailBlock>

      {exam.isPanel && (
        <ExamDetailBlock
          title="Composição"
          examId={exam.id}
          canEdit={canEdit}
          form={({ close }) => <CompositionForm {...formProps} onClose={close} />}
        >
          <ul className="attendance-readonly-detail__items">
            {componentQueries.map((query, index) => (
              <li key={exam.componentExamIds[index]} className="attendance-readonly-detail__item">
                {query.data?.name ?? '…'}
              </li>
            ))}
          </ul>
        </ExamDetailBlock>
      )}

      {priceVisible && (
        <ExamDetailBlock
          title="Preço e vigência"
          examId={exam.id}
          canEdit={canEdit && canManagePrice}
          form={({ close }) => <PriceForm {...formProps} onClose={close} />}
        >
          <dl className="attendance-readonly-detail__fields">
            <dt>Preço</dt>
            <dd>{formatCurrencyBRL(exam.priceBase ?? '0')}</dd>
            <dt>Vigência</dt>
            <dd>
              {exam.priceValidFrom ? `desde ${formatDate(exam.priceValidFrom)}` : '—'}
              {exam.priceValidTo ? ` até ${formatDate(exam.priceValidTo)}` : ''}
            </dd>
          </dl>
          {!canManagePrice && (
            <p className="attendance-readonly-detail__hint">
              Alterar preço exige a permissão de gerir preços.
            </p>
          )}
        </ExamDetailBlock>
      )}

      <ExamDetailBlock
        title="Status"
        examId={exam.id}
        canEdit={canEdit}
        form={({ close }) => <StatusForm {...formProps} onClose={close} />}
      >
        <dl className="attendance-readonly-detail__fields">
          <dt>Status</dt>
          <dd>{exam.status === 'ACTIVE' ? 'Ativo' : 'Inativo'}</dd>
        </dl>
      </ExamDetailBlock>
    </div>
  )
}
