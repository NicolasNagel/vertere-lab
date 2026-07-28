import { formatCurrencyBRL } from '../../../shared/lib/formatters'
import type { ClosurePreviewBlockedItem, ClosurePreviewItem } from '../api/closures-api'
import './closure-preview-items-table.css'

type Row =
  | { kind: 'eligible'; item: ClosurePreviewItem }
  | { kind: 'blocked'; item: ClosurePreviewBlockedItem }

interface ClosurePreviewItemsTableProps {
  eligibleItems: ClosurePreviewItem[]
  blockedItems: ClosurePreviewBlockedItem[]
}

export function ClosurePreviewItemsTable({
  eligibleItems,
  blockedItems,
}: ClosurePreviewItemsTableProps) {
  const rows: Row[] = [
    ...eligibleItems.map((item): Row => ({ kind: 'eligible', item })),
    ...blockedItems.map((item): Row => ({ kind: 'blocked', item })),
  ]

  if (rows.length === 0) {
    return (
      <div className="closure-preview-items-table">
        <p className="closure-preview-items-table__empty">
          Nenhum atendimento encontrado para esta clínica e competência.
        </p>
      </div>
    )
  }

  return (
    <div className="closure-preview-items-table">
      <div className="closure-preview-items-table__header">
        <div>Status</div>
        <div>Protocolo</div>
        <div>Paciente</div>
        <div>Exame</div>
        <div>Motivo</div>
        <div>Total</div>
      </div>
      {rows.map((row) => (
        <div
          key={`${row.kind}-${row.item.attendanceExamId}`}
          className="closure-preview-items-table__row"
          data-status={row.kind}
        >
          <div>
            <span className="closure-preview-items-table__badge" data-status={row.kind}>
              {row.kind === 'eligible' ? 'Elegível' : 'Bloqueado'}
            </span>
          </div>
          <div className="closure-preview-items-table__protocol">
            {row.item.protocolNumber ?? '—'}
          </div>
          <div>{row.item.patientName}</div>
          <div>{row.item.examName}</div>
          <div className="closure-preview-items-table__reason">
            {row.kind === 'blocked' ? row.item.reason : '—'}
          </div>
          <div className="closure-preview-items-table__total">
            {formatCurrencyBRL(row.item.totalAmount)}
          </div>
        </div>
      ))}
    </div>
  )
}
