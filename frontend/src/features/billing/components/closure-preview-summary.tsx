import { formatCurrencyBRL } from '../../../shared/lib/formatters'
import type { ClosurePreview } from '../api/closures-api'
import './closure-preview-summary.css'

interface ClosurePreviewSummaryProps {
  preview: ClosurePreview
}

export function ClosurePreviewSummary({ preview }: ClosurePreviewSummaryProps) {
  return (
    <div className="closure-preview-summary">
      <div className="closure-preview-summary__card">
        <div className="closure-preview-summary__label">Atendimentos</div>
        <div className="closure-preview-summary__value">{preview.attendanceCount}</div>
      </div>
      <div className="closure-preview-summary__card">
        <div className="closure-preview-summary__label">Itens elegíveis</div>
        <div className="closure-preview-summary__value">{preview.itemCount}</div>
      </div>
      <div className="closure-preview-summary__card">
        <div className="closure-preview-summary__label">Cancelados</div>
        <div className="closure-preview-summary__value">{preview.cancelledAttendanceCount}</div>
      </div>
      <div className="closure-preview-summary__card">
        <div className="closure-preview-summary__label">Subtotal</div>
        <div className="closure-preview-summary__value closure-preview-summary__value--mono">
          {formatCurrencyBRL(preview.subtotal)}
        </div>
      </div>
      <div className="closure-preview-summary__card">
        <div className="closure-preview-summary__label">Descontos</div>
        <div className="closure-preview-summary__value closure-preview-summary__value--mono">
          {formatCurrencyBRL(preview.discountTotal)}
        </div>
      </div>
      <div className="closure-preview-summary__card">
        <div className="closure-preview-summary__label">Adicionais</div>
        <div className="closure-preview-summary__value closure-preview-summary__value--mono">
          {formatCurrencyBRL(preview.surchargeTotal)}
        </div>
      </div>
      <div className="closure-preview-summary__card closure-preview-summary__card--total">
        <div className="closure-preview-summary__label">Total</div>
        <div className="closure-preview-summary__value closure-preview-summary__value--mono">
          {formatCurrencyBRL(preview.grandTotal)}
        </div>
      </div>
    </div>
  )
}
