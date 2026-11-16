import { useState } from 'react'

import { formatCurrencyBRL, formatDateTime } from '../../../shared/lib/formatters'
import { monthlyClosureExportUrl } from '../api/closures-api'
import type { MonthlyClosure } from '../api/closures-api'
import { useAddFinancialAdjustmentMutation } from '../api/use-add-financial-adjustment-mutation'
import { useReopenMonthlyClosureMutation } from '../api/use-reopen-monthly-closure-mutation'
import { groupItemsByProtocol } from '../lib/group-by-protocol'
import { ClosureProtocolTable } from './closure-protocol-table'
import { ClosureReopenModal } from './closure-reopen-modal'
import { ClosureSummaryCards } from './closure-summary-cards'
import { ClosureViewModeToggle, type ClosureItemsViewMode } from './closure-view-mode-toggle'
import { FinancialAdjustmentModal } from './financial-adjustment-modal'
import { MonthlyClosureStatusBadge } from './monthly-closure-status-badge'
import './closure-existing-view.css'

interface ClosureExistingViewProps {
  closure: MonthlyClosure
  canReopen: boolean
  canAdjust: boolean
}

/** Body of an already-existing fechamento (CLOSED or REOPENED) — the "found
 * by clinic+período" branch of the unified fechamento screen (Tela 15). */
export function ClosureExistingView({ closure, canReopen, canAdjust }: ClosureExistingViewProps) {
  const [showReopenModal, setShowReopenModal] = useState(false)
  const [showAdjustmentModal, setShowAdjustmentModal] = useState(false)
  const [itemsViewMode, setItemsViewMode] = useState<ClosureItemsViewMode>('exame')

  const reopenMutation = useReopenMonthlyClosureMutation(closure.id)
  const adjustmentMutation = useAddFinancialAdjustmentMutation(closure.id)

  const protocolCount = new Set(closure.items.map((item) => item.attendanceId)).size
  const onCallProtocolCount = new Set(
    closure.items
      .filter((item) => item.serviceLevel && item.serviceLevel !== 'NORMAL')
      .map((item) => item.attendanceId),
  ).size

  return (
    <div className="closure-existing-view">
      <div className="closure-existing-view__header-row">
        <MonthlyClosureStatusBadge status={closure.status} />
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

      <ClosureSummaryCards
        cards={[
          { id: 'protocols', label: 'Protocolos', value: String(protocolCount) },
          { id: 'items', label: 'Exames', value: String(closure.itemCount) },
          { id: 'on-call', label: 'Plantão', value: String(onCallProtocolCount), tone: 'warning' },
          { id: 'total', label: 'Valor total', value: formatCurrencyBRL(closure.grandTotal), tone: 'total' },
        ]}
      />

      <section className="closure-existing-view__section">
        <h2 className="closure-existing-view__section-title">
          Ajustes ({closure.adjustments.length})
        </h2>
        {closure.adjustments.length === 0 ? (
          <p className="closure-existing-view__value">Nenhum ajuste registrado.</p>
        ) : (
          <ul className="closure-existing-view__items">
            {closure.adjustments.map((adjustment) => (
              <li key={adjustment.id} className="closure-existing-view__item">
                <span>
                  {adjustment.kind === 'DEBIT' ? 'Débito' : 'Crédito'} · {adjustment.reason}
                </span>
                <span className="closure-existing-view__mono">
                  {adjustment.kind === 'CREDIT' ? '−' : '+'}
                  {formatCurrencyBRL(adjustment.amount)}
                </span>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="closure-existing-view__section">
        <h2 className="closure-existing-view__section-title">Itens ({closure.itemCount})</h2>
        {closure.items.length === 0 ? (
          <p className="closure-existing-view__value">Nenhum item associado.</p>
        ) : (
          <>
            <ClosureViewModeToggle mode={itemsViewMode} onChange={setItemsViewMode} />
            {itemsViewMode === 'protocolo' ? (
              <ClosureProtocolTable groups={groupItemsByProtocol(closure.items)} />
            ) : (
              <table className="closure-existing-view__item-table">
                <thead>
                  <tr>
                    <th>Protocolo</th>
                    <th>Paciente</th>
                    <th>Exame</th>
                    <th>Tipo</th>
                    <th>Qtd.</th>
                    <th>Valor</th>
                  </tr>
                </thead>
                <tbody>
                  {closure.items.map((item) => (
                    <tr key={item.id}>
                      <td className="closure-existing-view__item-table-protocol">
                        {item.protocolNumber ?? '—'}
                      </td>
                      <td>{item.patientName}</td>
                      <td>{item.examName}</td>
                      <td>
                        <span
                          className="closure-existing-view__service-badge"
                          data-on-call={item.serviceLevel !== null && item.serviceLevel !== 'NORMAL'}
                        >
                          {item.serviceLevel === null
                            ? '—'
                            : item.serviceLevel === 'NORMAL'
                              ? 'Normal'
                              : 'Plantão'}
                        </span>
                      </td>
                      <td>{item.quantity}</td>
                      <td className="closure-existing-view__item-table-value">
                        {formatCurrencyBRL(item.totalAmount)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </>
        )}
      </section>

      <section className="closure-existing-view__section">
        <h2 className="closure-existing-view__section-title">Valor</h2>
        <div className="closure-existing-view__grid">
          <div className="closure-existing-view__field">
            <span className="closure-existing-view__label">Subtotal</span>
            <span className="closure-existing-view__value">
              {formatCurrencyBRL(closure.subtotal)}
            </span>
          </div>
          <div className="closure-existing-view__field">
            <span className="closure-existing-view__label">Descontos</span>
            <span className="closure-existing-view__value">
              {formatCurrencyBRL(closure.discountTotal)}
            </span>
          </div>
          {Number(closure.onCallFeeTotal) > 0 && (
            <div className="closure-existing-view__field">
              <span className="closure-existing-view__label">Taxas</span>
              <span className="closure-existing-view__value">
                {formatCurrencyBRL(closure.onCallFeeTotal)}
              </span>
            </div>
          )}
          <div className="closure-existing-view__field">
            <span className="closure-existing-view__label">Fechado em</span>
            <span className="closure-existing-view__value">{formatDateTime(closure.closedAt)}</span>
          </div>
          <div className="closure-existing-view__field">
            <span className="closure-existing-view__label">Versão</span>
            <span className="closure-existing-view__value">{closure.version}</span>
          </div>
        </div>
        <div className="closure-existing-view__total">
          <span>Valor total</span>
          <span className="closure-existing-view__total-value">
            {formatCurrencyBRL(closure.grandTotal)}
          </span>
        </div>
      </section>

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
