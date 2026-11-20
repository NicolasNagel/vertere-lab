import { useQueries } from '@tanstack/react-query'
import { Link, useParams } from 'react-router'

import { ApiError } from '../../../shared/api/errors'
import { formatCurrencyBRL, formatDate } from '../../../shared/lib/formatters'
import { Badge } from '../../../shared/ui/badge'
import { ArrowLeftIcon } from '../../../shared/ui/icons'
import { PageHeader } from '../../../shared/ui/page-header'
import { useAuth } from '../../auth/auth-context'
import { useSpeciesQuery } from '../../patients/api/use-species-query'
import { fetchExam } from '../api/catalog-api'
import { useActiveExamCategoriesQuery } from '../api/use-active-exam-categories-query'
import { examQueryKey, useExamQuery } from '../api/use-exam-query'
import { DetailBlock } from '../../../shared/ui/detail-block'
import {
  CategorySpeciesForm,
  CompositionForm,
  IdentityForm,
  PriceForm,
  StatusForm,
} from './exam-detail-forms'
import { ExamSummaryCards } from './exam-summary-cards'
import '../../../shared/ui/button.css'
import '../../attendances/components/attendance-detail-page.css'
import '../../../shared/ui/readonly-detail.css'

/** Detalhe do exame em blocos, cada um com "Editar" + motivo. Preço só com `pricing.read`
 * e só editável com `pricing.manage`; o backend é quem decide de verdade. */
export function ExamDetailPage() {
  const { examId } = useParams<{ examId: string }>()
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
    <Link to="/cadastros/exames" className="button button--secondary">
      <ArrowLeftIcon />
      Voltar
    </Link>
  )

  if (examQuery.isLoading || examQuery.isError || !exam) {
    const forbidden = examQuery.error instanceof ApiError && examQuery.error.status === 403
    return (
      <div className="attendance-detail-page">
        <PageHeader title="Exame" actions={back} />
        <div className="attendance-detail-page__body">
          {examQuery.isLoading ? (
            <p className="attendance-detail-page__hint">Carregando…</p>
          ) : (
            <p role="alert" className="attendance-detail-page__error">
              {forbidden
                ? 'Você não tem permissão para visualizar este exame.'
                : 'Não foi possível carregar o exame. Tente novamente.'}
            </p>
          )}
        </div>
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
    <div className="attendance-detail-page">
      <PageHeader
        title={exam.name}
        subtitle={
          <span className="attendance-detail-page__sub">
            <span className="attendance-readonly-detail__mono">{exam.code}</span>
            <Badge tone={exam.status === 'ACTIVE' ? 'success' : 'neutral'}>
              {exam.status === 'ACTIVE' ? 'Ativo' : 'Inativo'}
            </Badge>
          </span>
        }
        actions={back}
      />

      <div className="attendance-detail-page__body">
        <ExamSummaryCards
          exam={exam}
          speciesNames={(speciesQuery.data ?? [])
            .filter((s) => exam.speciesIds.includes(s.id))
            .map((s) => s.name)}
        />
        <div className="attendance-readonly-detail">
          <div className="attendance-readonly-detail__columns" data-money={priceVisible}>
            <div className="attendance-readonly-detail__column">
              <DetailBlock
                title="Identificação"
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
              </DetailBlock>

              <DetailBlock
                title="Categoria e espécies"
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
              </DetailBlock>

              {exam.isPanel && (
                <DetailBlock
                  title="Composição"
                  canEdit={canEdit}
                  form={({ close }) => <CompositionForm {...formProps} onClose={close} />}
                >
                  <ul className="attendance-readonly-detail__items">
                    {componentQueries.map((query, index) => (
                      <li
                        key={exam.componentExamIds[index]}
                        className="attendance-readonly-detail__item"
                      >
                        {query.data?.name ?? '…'}
                      </li>
                    ))}
                  </ul>
                </DetailBlock>
              )}
            </div>
            <div className="attendance-readonly-detail__column">
              {priceVisible && (
                <DetailBlock
                  title="Preço e vigência"
                  canEdit={canEdit && canManagePrice}
                  form={({ close }) => <PriceForm {...formProps} onClose={close} />}
                >
                  <dl className="attendance-readonly-detail__fields">
                    <dt>Preço</dt>
                    <dd>{formatCurrencyBRL(exam.priceBase ?? '0')}</dd>
                    <dt>Vigência</dt>
                    <dd>
                      {exam.priceValidFrom && !exam.priceValidFrom.startsWith('1900')
                        ? `desde ${formatDate(exam.priceValidFrom)}`
                        : 'Sem data de início'}
                      {exam.priceValidTo ? ` até ${formatDate(exam.priceValidTo)}` : ''}
                    </dd>
                  </dl>
                  {!canManagePrice && (
                    <p className="attendance-readonly-detail__hint">
                      Alterar preço exige a permissão de gerir preços.
                    </p>
                  )}
                </DetailBlock>
              )}

              <DetailBlock
                title="Status"
                canEdit={canEdit}
                form={({ close }) => <StatusForm {...formProps} onClose={close} />}
              >
                <dl className="attendance-readonly-detail__fields">
                  <dt>Status</dt>
                  <dd>{exam.status === 'ACTIVE' ? 'Ativo' : 'Inativo'}</dd>
                </dl>
              </DetailBlock>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
