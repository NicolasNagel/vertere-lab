import { formatCurrencyBRL } from '../../../shared/lib/formatters'
import type { AttendanceExamItem } from '../api/attendances-api'
import './attendance-summary-panel.css'

interface AttendanceSummaryPanelProps {
  items: AttendanceExamItem[]
  subtotal: string
  discountTotal: string
  onCallFee: string
  grandTotal: string
  isLoading: boolean
}

export function AttendanceSummaryPanel({
  items,
  subtotal,
  discountTotal,
  onCallFee,
  grandTotal,
  isLoading,
}: AttendanceSummaryPanelProps) {
  return (
    <section className="attendance-summary-panel">
      <h2 className="attendance-summary-panel__title">
        <span className="attendance-summary-panel__badge">5</span>
        Valor
      </h2>

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
            <div className="attendance-summary-panel__line">
              <span>Taxa de plantão</span>
              <span className="attendance-summary-panel__mono">
                {Number(onCallFee) > 0 ? formatCurrencyBRL(onCallFee) : 'não se aplica'}
              </span>
            </div>
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
