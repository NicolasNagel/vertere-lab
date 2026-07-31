import { formatCurrencyBRL } from '../../../shared/lib/formatters'
import type { AttendanceExamItem } from '../api/attendances-api'
import './attendance-summary-panel.css'

interface AttendanceSummaryPanelProps {
  items: AttendanceExamItem[]
  subtotal: string
  discountTotal: string
  surchargeTotal: string
  grandTotal: string
  isLoading: boolean
}

export function AttendanceSummaryPanel({
  items,
  subtotal,
  discountTotal,
  surchargeTotal,
  grandTotal,
  isLoading,
}: AttendanceSummaryPanelProps) {
  return (
    <section className="attendance-summary-panel">
      <h2 className="attendance-summary-panel__title">Valor</h2>

      {isLoading ? (
        <p className="attendance-summary-panel__hint">Calculando…</p>
      ) : (
        <>
          <div className="attendance-summary-panel__lines">
            {items.map((item) => (
              <div key={item.id} className="attendance-summary-panel__line">
                <span>
                  {item.examName}
                  {item.quantity > 1 ? ` ×${item.quantity}` : ''}
                </span>
                <span className="attendance-summary-panel__mono">
                  {formatCurrencyBRL(item.totalAmount)}
                </span>
              </div>
            ))}
            <div className="attendance-summary-panel__line attendance-summary-panel__line--subtotal">
              <span>Subtotal</span>
              <span className="attendance-summary-panel__mono">{formatCurrencyBRL(subtotal)}</span>
            </div>
            {Number(discountTotal) > 0 && (
              <div className="attendance-summary-panel__line">
                <span>Desconto</span>
                <span className="attendance-summary-panel__mono">
                  – {formatCurrencyBRL(discountTotal)}
                </span>
              </div>
            )}
            {Number(surchargeTotal) > 0 && (
              <div className="attendance-summary-panel__line">
                <span>Adicional</span>
                <span className="attendance-summary-panel__mono">
                  {formatCurrencyBRL(surchargeTotal)}
                </span>
              </div>
            )}
          </div>
          <div className="attendance-summary-panel__total">
            <span>Valor total</span>
            <span className="attendance-summary-panel__total-value">
              {formatCurrencyBRL(grandTotal)}
            </span>
          </div>
        </>
      )}
    </section>
  )
}
