import { useState } from 'react'
import { useParams } from 'react-router'

import { ApiError } from '../../../shared/api/errors'
import { formatCompetence, formatCurrencyBRL, formatDateTime } from '../../../shared/lib/formatters'
import { useAuth } from '../../auth/auth-context'
import { useClinicQuery } from '../../clinics/api/use-clinic-query'
import { monthlyClosureExportUrl } from '../api/closures-api'
import { useMonthlyClosureQuery } from '../api/use-monthly-closure-query'
import { useAddFinancialAdjustmentMutation } from '../api/use-add-financial-adjustment-mutation'
import { useReopenMonthlyClosureMutation } from '../api/use-reopen-monthly-closure-mutation'
import { ClosureReopenModal } from './closure-reopen-modal'
import { FinancialAdjustmentModal } from './financial-adjustment-modal'
import { MonthlyClosureStatusBadge } from './monthly-closure-status-badge'
import './closure-detail-page.css'

export function ClosureDetailPage() {
  const { closureId } = useParams<{ closureId: string }>()
  const { user } = useAuth()
  const canRead = user?.permissions.includes('closures.read') ?? false
  const canReopen = user?.permissions.includes('closures.reopen') ?? false
  const canAdjust = user?.permissions.includes('closures.adjust') ?? false
  const [showReopenModal, setShowReopenModal] = useState(false)
  const [showAdjustmentModal, setShowAdjustmentModal] = useState(false)

  const closureQuery = useMonthlyClosureQuery(canRead ? (closureId ?? null) : null)
  const clinicQuery = useClinicQuery(closureQuery.data?.clinicId ?? null)

  const isForbidden = closureQuery.error instanceof ApiError && closureQuery.error.status === 403
  const isNotFound = closureQuery.error instanceof ApiError && closureQuery.error.status === 404
  const isGenericError = closureQuery.isError && !isForbidden && !isNotFound

  const closure = closureQuery.data
  const reopenMutation = useReopenMonthlyClosureMutation(closureId ?? '')
  const adjustmentMutation = useAddFinancialAdjustmentMutation(closureId ?? '')

  return (
    <div className="closure-detail-page">
      <header className="closure-detail-page__header">
        <div>
          <div className="closure-detail-page__eyebrow">Financeiro · Fechamento</div>
          <h1 className="closure-detail-page__title">
            {closure ? formatCompetence(closure.competenceYear, closure.competenceMonth) : 'Fechamento'}
          </h1>
        </div>
        {closure && (
          <div className="closure-detail-page__actions">
            {canAdjust && closure.status === 'CLOSED' && (
              <button
                className="button button--ghost"
                type="button"
                onClick={() => setShowAdjustmentModal(true)}
              >
                Adicionar ajuste
              </button>
            )}
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
      </header>

      <div
        aria-label="Conteúdo do fechamento"
        className="closure-detail-page__body"
        tabIndex={0}
      >
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
              <h2 className="closure-detail-page__section-title">
                Ajustes ({closure.adjustments.length})
              </h2>
              {closure.adjustments.length === 0 ? (
                <p className="closure-detail-page__value">Nenhum ajuste registrado.</p>
              ) : (
                <ul className="closure-detail-page__items">
                  {closure.adjustments.map((adjustment) => (
                    <li key={adjustment.id} className="closure-detail-page__item">
                      <span>
                        {adjustment.kind === 'DEBIT' ? 'Débito' : 'Crédito'} · {adjustment.reason}
                      </span>
                      <span className="closure-detail-page__mono">
                        {adjustment.kind === 'CREDIT' ? '−' : '+'}
                        {formatCurrencyBRL(adjustment.amount)}
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </section>

            <section className="closure-detail-page__section">
              <h2 className="closure-detail-page__section-title">Itens ({closure.itemCount})</h2>

              <div className="closure-detail-page__summary-cards">
                <div className="closure-detail-page__summary-card">
                  <div className="closure-detail-page__summary-card-label">Protocolos</div>
                  <div className="closure-detail-page__summary-card-value">
                    {new Set(closure.items.map((item) => item.attendanceId)).size}
                  </div>
                </div>
                <div className="closure-detail-page__summary-card">
                  <div className="closure-detail-page__summary-card-label">Exames</div>
                  <div className="closure-detail-page__summary-card-value">
                    {closure.itemCount}
                  </div>
                </div>
                <div className="closure-detail-page__summary-card closure-detail-page__summary-card--total">
                  <div className="closure-detail-page__summary-card-label">Valor total</div>
                  <div className="closure-detail-page__summary-card-value">
                    {formatCurrencyBRL(closure.grandTotal)}
                  </div>
                </div>
              </div>

              {closure.items.length === 0 ? (
                <p className="closure-detail-page__value">Nenhum item associado.</p>
              ) : (
                <table className="closure-detail-page__item-table">
                  <thead>
                    <tr>
                      <th>Protocolo</th>
                      <th>Paciente</th>
                      <th>Exame</th>
                      <th>Qtd.</th>
                      <th>Valor</th>
                    </tr>
                  </thead>
                  <tbody>
                    {closure.items.map((item) => (
                      <tr key={item.id}>
                        <td className="closure-detail-page__item-table-protocol">
                          {item.protocolNumber ?? '—'}
                        </td>
                        <td>{item.patientName}</td>
                        <td>{item.examName}</td>
                        <td>{item.quantity}</td>
                        <td className="closure-detail-page__item-table-value">
                          {formatCurrencyBRL(item.totalAmount)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
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
      {showAdjustmentModal && (
        <FinancialAdjustmentModal
          isPending={adjustmentMutation.isPending}
          error={adjustmentMutation.error}
          onCancel={() => {
            if (!adjustmentMutation.isPending) setShowAdjustmentModal(false)
          }}
          onConfirm={(params) =>
            adjustmentMutation.mutate(params, {
              onSuccess: () => setShowAdjustmentModal(false),
            })
          }
        />
      )}
    </div>
  )
}
