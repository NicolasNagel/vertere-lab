import { formatCurrencyBRL } from '../../../shared/lib/formatters'
import type { ProtocolGroup } from '../lib/group-by-protocol'
import './closure-protocol-table.css'

interface ClosureProtocolTableProps {
  groups: ProtocolGroup[]
}

/** "Por protocolo" view (Tela 15) — one row per atendimento, exames
 * combinados numa única célula. Não tem coluna de data: nem `ClosurePreviewItem`
 * nem `MonthlyClosureItem` carregam uma data por item hoje. */
export function ClosureProtocolTable({ groups }: ClosureProtocolTableProps) {
  return (
    <div className="closure-protocol-table">
      <div className="closure-protocol-table__header">
        <div>Protocolo</div>
        <div>Paciente</div>
        <div>Exames</div>
        <div>Tipo</div>
        <div>Valor</div>
      </div>
      {groups.map((group) => (
        <div key={group.attendanceId} className="closure-protocol-table__row">
          <div className="closure-protocol-table__protocol">{group.protocolNumber ?? '—'}</div>
          <div className="closure-protocol-table__patient" title={group.patientName}>
            {group.patientName}
          </div>
          <div className="closure-protocol-table__exams" title={group.examNames.join(', ')}>
            {group.examNames.join(', ')}
          </div>
          <div>
            <span className="closure-protocol-table__badge" data-on-call={group.isOnCall}>
              {group.isOnCall ? 'Plantão' : 'Normal'}
            </span>
          </div>
          <div className="closure-protocol-table__total">
            {formatCurrencyBRL(group.totalAmount)}
          </div>
        </div>
      ))}
    </div>
  )
}
