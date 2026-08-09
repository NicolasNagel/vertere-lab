import { Link } from 'react-router'

import { formatCurrencyBRL, formatDate } from '../../../shared/lib/formatters'
import type { MonthlyClosureSummary } from '../api/closures-api'
import { MonthlyClosureStatusBadge } from './monthly-closure-status-badge'
import './closures-list-table.css'

interface ClosuresListTableProps {
  closures: MonthlyClosureSummary[]
  clinicNameById: Record<string, string>
}

export function ClosuresListTable({ closures, clinicNameById }: ClosuresListTableProps) {
  if (closures.length === 0) {
    return (
      <div className="closures-list-table">
        <p className="closures-list-table__empty">
          Nenhum fechamento encontrado para os filtros selecionados.
        </p>
      </div>
    )
  }

  return (
    <div className="closures-list-table">
      <div className="closures-list-table__header">
        <div>Período</div>
        <div>Clínica</div>
        <div>Itens</div>
        <div className="closures-list-table__value-header">Total</div>
        <div>Status</div>
        <div>Fechado em</div>
      </div>
      {closures.map((closure) => (
        <Link
          key={closure.id}
          to={`/financeiro/fechamento?clinicId=${closure.clinicId}&periodStart=${closure.periodStart}&periodEnd=${closure.periodEnd}`}
          className="closures-list-table__row"
        >
          <div className="closures-list-table__period">
            {formatDate(closure.periodStart)} – {formatDate(closure.periodEnd)}
          </div>
          <div className="closures-list-table__clinic" title={clinicNameById[closure.clinicId] ?? '—'}>
            {clinicNameById[closure.clinicId] ?? '—'}
          </div>
          <div>{closure.itemCount}</div>
          <div className="closures-list-table__value">{formatCurrencyBRL(closure.grandTotal)}</div>
          <div>
            <MonthlyClosureStatusBadge status={closure.status} />
          </div>
          <div className="closures-list-table__muted">{formatDate(closure.closedAt)}</div>
        </Link>
      ))}
    </div>
  )
}
