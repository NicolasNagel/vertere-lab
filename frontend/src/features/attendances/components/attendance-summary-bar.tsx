import type { ReactNode } from 'react'

import { formatCurrencyBRL } from '../../../shared/lib/formatters'
import './attendance-summary-bar.css'

interface AttendanceSummaryBarProps {
  examCount: number
  /** `pricing.read`: sem ele a barra mostra só a contagem de exames. */
  showMoney: boolean
  subtotal: string
  discountTotal: string
  onCallFee: string
  grandTotal: string
  isCalculating: boolean
  /** Motivo de o valor não ter sido calculado (ex.: falta a data do atendimento). */
  calculationError?: string | null
  children: ReactNode
}

/** Barra fixa no rodapé da tela de protocolo: resumo do que foi marcado e as ações finais. */
export function AttendanceSummaryBar({
  examCount,
  showMoney,
  subtotal,
  discountTotal,
  onCallFee,
  grandTotal,
  isCalculating,
  calculationError = null,
  children,
}: AttendanceSummaryBarProps) {
  return (
    <div className="attendance-summary-bar" role="region" aria-label="Resumo do protocolo">
      {calculationError && (
        <p role="alert" className="attendance-summary-bar__error">
          {calculationError}
        </p>
      )}
      <dl className="attendance-summary-bar__figures">
        <div>
          <dt>Exames</dt>
          <dd>{examCount}</dd>
        </div>
        {showMoney && (
          <>
            <div>
              <dt>Subtotal</dt>
              <dd>{isCalculating ? '…' : formatCurrencyBRL(subtotal)}</dd>
            </div>
            {Number(discountTotal) > 0 && (
              <div>
                <dt>Desconto</dt>
                <dd>− {formatCurrencyBRL(discountTotal)}</dd>
              </div>
            )}
            {Number(onCallFee) > 0 && (
              <div>
                <dt>Taxa de plantão</dt>
                <dd>+ {formatCurrencyBRL(onCallFee)}</dd>
              </div>
            )}
            <div className="attendance-summary-bar__total">
              <dt>Total</dt>
              <dd>{isCalculating ? 'Calculando…' : formatCurrencyBRL(grandTotal)}</dd>
            </div>
          </>
        )}
      </dl>
      <div className="attendance-summary-bar__actions">{children}</div>
    </div>
  )
}
