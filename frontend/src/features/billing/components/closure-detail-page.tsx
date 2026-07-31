import { useState } from 'react'
import { useParams } from 'react-router-dom'

import { ApiError } from '../../../shared/api/errors'
import { formatCompetence, formatCurrencyBRL, formatDateTime } from '../../../shared/lib/formatters'
import { useAuth } from '../../auth/auth-context'
import { useClinicQuery } from '../../clinics/api/use-clinic-query'
import { monthlyClosureExportUrl } from '../api/closures-api'
import { useMonthlyClosureQuery } from '../api/use-monthly-closure-query'
import { useReopenMonthlyClosureMutation } from '../api/use-reopen-monthly-closure-mutation'
import { ClosureReopenModal } from './closure-reopen-modal'
import { MonthlyClosureStatusBadge } from './monthly-closure-status-badge'
import './closure-detail-page.css'

export function ClosureDetailPage() {
  const { closureId } = useParams<{ closureId: string }>()
  const { user } = useAuth()
  const canRead = user?.permissions.includes('closures.read') ?? false
  const canReopen = user?.permissions.includes('closures.reopen') ?? false
  const [showReopenModal, setShowReopenModal] = useState(false)

  const closureQuery = useMonthlyClosureQuery(canRead ? (closureId ?? null) : null)
  const clinicQuery = useClinicQuery(closureQuery.data?.clinicId ?? null)

  const isForbidden = closureQuery.error instanceof ApiError && closureQuery.error.status === 403
  const isNotFound = closureQuery.error instanceof ApiError && closureQuery.error.status === 404
  const isGenericError = closureQuery.isError && !isForbidden && !isNotFound

  const closure = closureQuery.data
  const reopenMutation = useReopenMonthlyClosureMutation(closureId ?? '')

  return (
    <div className="closure-detail-page">
      <div className="closure-detail-page__header">
        <div>
          <div className="closure-detail-page__eyebrow">Financeiro · Fechamento</div>
          <h1 className="closure-detail-page__title">
            {closure ? formatCompetence(closure.competenceYear, closure.competenceMonth) : 'Fechamento'}
          </h1>
        </div>
        {closure && (
          <div className="closure-detail-page__actions">
            {canReopen && closure.status === 'CLOSED' && (
              <button
                className="button button--ghost"
                type="button"
                onClick={() => setShowReopenModal(true)}
              >
                Reabrir
              </button>
            )}
            <a className="button button--ghost" href={monthlyClosureExportUrl(closure.id)} download>
              Baixar CSV
            </a>
          </div>
        )}
      </div>

      <div className="closure-detail-page__body">
        {!canRead && (
          <p className="closure-detail-page__forbidden">
            Você não tem permissão para visualizar fechamentos.
          </p>
        )}

        {canRead && closureQuery.isLoading && <p className="closure-detail-page__hint">Carregando…</p>}

        {canRead && isForbidden && (
          <p className="closure-detail-page__forbidden">
            Você não tem permissão para visualizar este fechamento.
          </p>
        )}

        {canRead && isNotFound && (
          <p className="closure-detail-page__forbidden">Fechamento não encontrado.</p>
        )}

        {canRead && isGenericError && (
          <p className="closure-detail-page__error">
            Não foi possível carregar o fechamento. Tente novamente.
          </p>
        )}

        {canRead && closure && (
          <div className="closure-detail-page__content">
            <div className="closure-detail-page__header-row">
              <MonthlyClosureStatusBadge status={closure.status} />
            </div>

            <section className="closure-detail-page__section">
              <h2 className="closure-detail-page__section-title">Dados do fechamento</h2>
              <div className="closure-detail-page__grid">
                <div className="closure-detail-page__field">
                  <span className="closure-detail-page__label">Clínica</span>
                  <span className="closure-detail-page__value">{clinicQuery.data?.name ?? '—'}</span>
                </div>
                <div className="closure-detail-page__field">
                  <span className="closure-detail-page__label">Período</span>
                  <span className="closure-detail-page__value">
                    {closure.periodStart} – {closure.periodEnd}
                  </span>
                </div>
                <div className="closure-detail-page__field">
                  <span className="closure-detail-page__label">Fechado em</span>
                  <span className="closure-detail-page__value">{formatDateTime(closure.closedAt)}</span>
                </div>
                <div className="closure-detail-page__field">
                  <span className="closure-detail-page__label">Versão</span>
                  <span className="closure-detail-page__value">{closure.version}</span>
                </div>
              </div>
            </section>

            <section className="closure-detail-page__section">
              <h2 className="closure-detail-page__section-title">Itens ({closure.itemCount})</h2>
              {closure.items.length === 0 ? (
                <p className="closure-detail-page__value">Nenhum item associado.</p>
              ) : (
                <ul className="closure-detail-page__items">
                  {closure.items.map((item) => (
                    <li key={item.id} className="closure-detail-page__item">
                      <span>
                        {item.protocolNumber ?? '—'} · {item.patientName} · {item.examName}
                        {item.quantity > 1 ? ` ×${item.quantity}` : ''}
                      </span>
                      <span className="closure-detail-page__mono">
                        {formatCurrencyBRL(item.totalAmount)}
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </section>

            <section className="closure-detail-page__section">
              <h2 className="closure-detail-page__section-title">Valor</h2>
              <div className="closure-detail-page__grid">
                <div className="closure-detail-page__field">
                  <span className="closure-detail-page__label">Subtotal</span>
                  <span className="closure-detail-page__value">
                    {formatCurrencyBRL(closure.subtotal)}
                  </span>
                </div>
                <div className="closure-detail-page__field">
                  <span className="closure-detail-page__label">Descontos</span>
                  <span className="closure-detail-page__value">
                    {formatCurrencyBRL(closure.discountTotal)}
                  </span>
                </div>
              </div>
              <div className="closure-detail-page__total">
                <span>Valor total</span>
                <span className="closure-detail-page__total-value">
                  {formatCurrencyBRL(closure.grandTotal)}
                </span>
              </div>
            </section>
          </div>
        )}
      </div>
      {showReopenModal && (
        <ClosureReopenModal
          isPending={reopenMutation.isPending}
          error={reopenMutation.error}
          onCancel={() => {
            if (!reopenMutation.isPending) setShowReopenModal(false)
          }}
          onConfirm={(reason) =>
            reopenMutation.mutate(reason, { onSuccess: () => setShowReopenModal(false) })
          }
        />
      )}
    </div>
  )
}
