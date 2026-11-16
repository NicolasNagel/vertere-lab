import { formatCurrencyBRL, formatDate, formatTaxId } from '../../../shared/lib/formatters'
import type { CategoryGroup } from '../lib/group-by-category'
import './closure-invoice-panel.css'

interface ClosureInvoicePanelProps {
  clinicName: string
  clinicTaxId: string | null
  periodStart: string
  periodEnd: string
  categoryBreakdown: CategoryGroup[]
  onCallFeeTotal: string
  grandTotal: string
  exportUrl: string | null
}

/** Right-hand "Demonstrativo analítico" panel (Tela 15) — a preview of what
 * the eventual export contains, built from the same totals already shown on
 * the left, not a separate calculation. PDF generation and NFS-e upload from
 * the mockup have no backend support yet (`spec-pages.md` lists them as
 * planned integration, not implemented) — this panel only offers the export
 * action that actually exists. */
export function ClosureInvoicePanel({
  clinicName,
  clinicTaxId,
  periodStart,
  periodEnd,
  categoryBreakdown,
  onCallFeeTotal,
  grandTotal,
  exportUrl,
}: ClosureInvoicePanelProps) {
  return (
    <aside className="closure-invoice-panel">
      <div className="closure-invoice-panel__eyebrow">Pré-visualização</div>
      <h2 className="closure-invoice-panel__title">
        Demonstrativo <em>analítico</em>
      </h2>

      <div className="closure-invoice-panel__card">
        <div className="closure-invoice-panel__brand">
          VERTERE <em>laboratório</em>
        </div>
        <div className="closure-invoice-panel__brand-sub">FECHAMENTO MENSAL</div>

        <dl className="closure-invoice-panel__meta">
          <div className="closure-invoice-panel__meta-row">
            <dt>Cliente</dt>
            <dd>{clinicName || '—'}</dd>
          </div>
          <div className="closure-invoice-panel__meta-row">
            <dt>CNPJ</dt>
            <dd className="closure-invoice-panel__mono">{formatTaxId(clinicTaxId) ?? '—'}</dd>
          </div>
          <div className="closure-invoice-panel__meta-row">
            <dt>Período</dt>
            <dd>
              {formatDate(periodStart)} – {formatDate(periodEnd)}
            </dd>
          </div>
        </dl>

        {categoryBreakdown.length > 0 && (
          <dl className="closure-invoice-panel__breakdown">
            {categoryBreakdown.map((group) => (
              <div key={group.category} className="closure-invoice-panel__meta-row">
                <dt>
                  {group.category} · {group.count}
                </dt>
                <dd className="closure-invoice-panel__mono">{formatCurrencyBRL(group.total)}</dd>
              </div>
            ))}
            {Number(onCallFeeTotal) > 0 && (
              <div className="closure-invoice-panel__meta-row">
                <dt>Taxas</dt>
                <dd className="closure-invoice-panel__mono closure-invoice-panel__mono--on-call">
                  {formatCurrencyBRL(onCallFeeTotal)}
                </dd>
              </div>
            )}
          </dl>
        )}

        <div className="closure-invoice-panel__total">
          <span>Total</span>
          <span className="closure-invoice-panel__total-value">{formatCurrencyBRL(grandTotal)}</span>
        </div>
      </div>

      <div className="closure-invoice-panel__documents-label">Exportação</div>
      {exportUrl ? (
        <a className="closure-invoice-panel__document" href={exportUrl} download>
          <span className="closure-invoice-panel__document-name">Baixar CSV do fechamento</span>
        </a>
      ) : (
        <p className="closure-invoice-panel__hint">
          A exportação fica disponível depois que o período é fechado.
        </p>
      )}
    </aside>
  )
}
