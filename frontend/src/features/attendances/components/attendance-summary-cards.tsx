import { formatCurrencyBRL } from '../../../shared/lib/formatters'
import { BillingIcon, OperationIcon } from '../../../shared/ui/icons'
import type { AttendanceStatusCounts } from '../api/attendances-api'
import './attendance-summary-cards.css'

interface AttendanceSummaryCardsProps {
  counts: AttendanceStatusCounts | undefined
  /** Complements the card hints, e.g. "de hoje"; defaults to the active list filters. */
  scopeLabel?: string
}

/** Totals come from the server (`status-counts`): the cards only present them. */
export function AttendanceSummaryCards({
  counts,
  scopeLabel = 'nos filtros atuais',
}: AttendanceSummaryCardsProps) {
  const drafts = counts?.byStatus.DRAFT ?? 0
  const cancelled = counts?.byStatus.CANCELLED ?? 0
  const total = counts?.total ?? 0
  const share = (count: number) => (total === 0 ? 0 : (count / total) * 100)

  return (
    <section className="attendance-summary-cards" aria-label="Resumo dos atendimentos">
      <article className="attendance-summary-card">
        <header className="attendance-summary-card__label">
          <span>Valor atendido</span>
          <span className="attendance-summary-card__icon">
            <BillingIcon />
          </span>
        </header>
        <strong className="attendance-summary-card__value">
          {counts ? formatCurrencyBRL(counts.billedTotal) : '—'}
        </strong>
        <small className="attendance-summary-card__hint">
          sem rascunhos e cancelados, {scopeLabel}
        </small>
      </article>

      <article className="attendance-summary-card">
        <header className="attendance-summary-card__label">
          <span>Protocolos</span>
          <span className="attendance-summary-card__icon">
            <OperationIcon />
          </span>
        </header>
        <strong className="attendance-summary-card__value">{counts ? total : '—'}</strong>
        {counts && total > 0 && (
          <>
            <div className="attendance-summary-card__bar" aria-hidden="true">
              <i data-tone="ok" style={{ width: `${share(total - drafts - cancelled)}%` }} />
              <i data-tone="draft" style={{ width: `${share(drafts)}%` }} />
              <i data-tone="cancelled" style={{ width: `${share(cancelled)}%` }} />
            </div>
            <small className="attendance-summary-card__hint">
              {total - drafts - cancelled} ativos · {drafts} em rascunho · {cancelled} cancelados
            </small>
          </>
        )}
      </article>

      <article className="attendance-summary-card">
        <header className="attendance-summary-card__label">
          <span>A confirmar</span>
          <span className="attendance-summary-card__icon">
            <OperationIcon />
          </span>
        </header>
        <strong className="attendance-summary-card__value">{counts ? drafts : '—'}</strong>
        <small className="attendance-summary-card__hint">rascunhos aguardando confirmação</small>
      </article>
    </section>
  )
}
