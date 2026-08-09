import { useState } from 'react'

import { formatCurrencyBRL } from '../../../shared/lib/formatters'
import type { ClosurePreviewBlockedItem, ClosurePreviewItem } from '../api/closures-api'
import { ClosureProtocolTable } from './closure-protocol-table'
import { ClosureViewModeToggle, type ClosureItemsViewMode } from './closure-view-mode-toggle'
import { groupItemsByProtocol } from '../lib/group-by-protocol'
import './closure-preview-items-table.css'

interface ClosurePreviewItemsTableProps {
  eligibleItems: ClosurePreviewItem[]
  blockedItems: ClosurePreviewBlockedItem[]
}

export function ClosurePreviewItemsTable({
  eligibleItems,
  blockedItems,
}: ClosurePreviewItemsTableProps) {
  const [mode, setMode] = useState<ClosureItemsViewMode>('exame')

  if (eligibleItems.length === 0 && blockedItems.length === 0) {
    return (
      <div className="closure-preview-items-table">
        <p className="closure-preview-items-table__empty">
          Nenhum atendimento encontrado para esta clínica e período.
        </p>
      </div>
    )
  }

  return (
    <>
      {eligibleItems.length > 0 && (
        <ClosureViewModeToggle mode={mode} onChange={setMode} />
      )}

      {mode === 'protocolo' && eligibleItems.length > 0 && (
        <div className="closure-preview-items-table__protocol-group">
          <ClosureProtocolTable groups={groupItemsByProtocol(eligibleItems)} />
        </div>
      )}

      {(mode === 'exame' || blockedItems.length > 0) && (
        <div className="closure-preview-items-table">
          <div className="closure-preview-items-table__header">
            <div>Status</div>
            <div>Protocolo</div>
            <div>Paciente</div>
            <div>Exame</div>
            <div>Motivo</div>
            <div>Total</div>
          </div>
          {(mode === 'exame' ? eligibleItems : []).map((item) => (
            <div
              key={`eligible-${item.attendanceExamId}`}
              className="closure-preview-items-table__row"
              data-status="eligible"
            >
              <div>
                <span className="closure-preview-items-table__badge" data-status="eligible">
                  Elegível
                </span>
              </div>
              <div className="closure-preview-items-table__protocol">
                {item.protocolNumber ?? '—'}
              </div>
              <div className="closure-preview-items-table__patient" title={item.patientName}>
                {item.patientName}
              </div>
              <div className="closure-preview-items-table__exam" title={item.examName}>
                {item.examName}
              </div>
              <div className="closure-preview-items-table__reason">—</div>
              <div className="closure-preview-items-table__total">
                {formatCurrencyBRL(item.totalAmount)}
              </div>
            </div>
          ))}
          {blockedItems.map((item) => (
            <div
              key={`blocked-${item.attendanceExamId}`}
              className="closure-preview-items-table__row"
              data-status="blocked"
            >
              <div>
                <span className="closure-preview-items-table__badge" data-status="blocked">
                  Bloqueado
                </span>
              </div>
              <div className="closure-preview-items-table__protocol">
                {item.protocolNumber ?? '—'}
              </div>
              <div className="closure-preview-items-table__patient" title={item.patientName}>
                {item.patientName}
              </div>
              <div className="closure-preview-items-table__exam" title={item.examName}>
                {item.examName}
              </div>
              <div className="closure-preview-items-table__reason">{item.reason}</div>
              <div className="closure-preview-items-table__total">
                {formatCurrencyBRL(item.totalAmount)}
              </div>
            </div>
          ))}
        </div>
      )}
    </>
  )
}
