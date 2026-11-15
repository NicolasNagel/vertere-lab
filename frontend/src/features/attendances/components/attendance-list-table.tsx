import { Link } from 'react-router'

import { formatCurrencyBRL, formatServiceDateTime } from '../../../shared/lib/formatters'
import { EyeIcon, PatientsIcon } from '../../../shared/ui/icons'
import { SERVICE_LEVEL_LABELS, type Attendance } from '../api/attendances-api'
import { AttendanceStatusBadge } from './attendance-status-badge'
import './attendance-list-table.css'

export interface PatientDisplay {
  name: string
  detail: string
  ownerName?: string
  sex?: 'MALE' | 'FEMALE'
}

interface AttendanceListTableProps {
  attendances: Attendance[]
  clinicNameById: Record<string, string>
  veterinarianNameById: Record<string, string>
  patientDisplayById: Record<string, PatientDisplay>
  /** Linha com o resumo aberto (popover). */
  selectedId?: string | null
  /** Clique ou Enter na linha abre o resumo. */
  onSelect: (attendance: Attendance) => void
}

function ExamChips({ attendance }: { attendance: Attendance }) {
  const [first, ...rest] = attendance.items
  if (!first) return <span className="attendance-list-table__muted">—</span>
  return (
    <span className="attendance-list-table__chips">
      <span className="attendance-list-table__chip">{first.examName}</span>
      {rest.length > 0 && (
        <span
          className="attendance-list-table__chip attendance-list-table__chip--more"
          title={attendance.items.map((item) => item.examName).join(', ')}
        >
          +{rest.length}
        </span>
      )}
    </span>
  )
}

export function AttendanceListTable({
  attendances,
  clinicNameById,
  veterinarianNameById,
  patientDisplayById,
  selectedId = null,
  onSelect,
}: AttendanceListTableProps) {
  if (attendances.length === 0) {
    return (
      <div className="attendance-list-table">
        <p className="attendance-list-table__empty">
          Nenhum atendimento encontrado para os filtros selecionados.
        </p>
      </div>
    )
  }

  return (
    <div className="attendance-list-table">
      <table className="attendance-list-table__table">
        <thead>
          <tr>
            <th scope="col">Protocolo</th>
            <th scope="col">Veterinário / Clínica</th>
            <th scope="col">Paciente</th>
            <th scope="col">Exames</th>
            <th scope="col">Data · Hora</th>
            <th scope="col">Tipo</th>
            <th scope="col">Status</th>
            <th scope="col" className="attendance-list-table__num">
              Valor
            </th>
            <th scope="col" className="attendance-list-table__actions-header">
              Ações
            </th>
          </tr>
        </thead>
        <tbody>
          {attendances.map((attendance) => {
            const patient = patientDisplayById[attendance.patientId]
            const clinicName = clinicNameById[attendance.clinicId] ?? '—'
            const veterinarianName = veterinarianNameById[attendance.veterinarianId] ?? '—'
            return (
              <tr
                key={attendance.id}
                tabIndex={0}
                aria-haspopup="dialog"
                aria-expanded={attendance.id === selectedId}
                data-selected={attendance.id === selectedId || undefined}
                data-cancelled={attendance.status === 'CANCELLED' || undefined}
                onClick={() => onSelect(attendance)}
                onKeyDown={(event) => {
                  if (event.target !== event.currentTarget) return
                  if (event.key === 'Enter' || event.key === ' ') {
                    event.preventDefault()
                    onSelect(attendance)
                  }
                }}
              >
                <td className="attendance-list-table__protocol">
                  {attendance.protocolNumber ?? 'Rascunho'}
                </td>
                <td>
                  <div
                    className="attendance-list-table__stack"
                    title={`${veterinarianName} · ${clinicName}`}
                  >
                    <span className="attendance-list-table__primary">{veterinarianName}</span>
                    <span className="attendance-list-table__muted">{clinicName}</span>
                  </div>
                </td>
                <td>
                  <div className="attendance-list-table__patient">
                    <span
                      className="attendance-list-table__avatar"
                      data-sex={patient?.sex}
                      title={
                        patient?.sex === 'MALE'
                          ? 'Macho'
                          : patient?.sex === 'FEMALE'
                            ? 'Fêmea'
                            : undefined
                      }
                    >
                      <PatientsIcon />
                    </span>
                    <div className="attendance-list-table__stack">
                      <span className="attendance-list-table__primary">{patient?.name ?? '—'}</span>
                      {patient?.detail && (
                        <span className="attendance-list-table__muted">{patient.detail}</span>
                      )}
                    </div>
                  </div>
                </td>
                <td>
                  <ExamChips attendance={attendance} />
                </td>
                <td className="attendance-list-table__muted">
                  {formatServiceDateTime(attendance.serviceDate, attendance.createdAt)}
                </td>
                <td>
                  <span
                    className="attendance-list-table__service-level"
                    data-level={attendance.serviceLevel}
                  >
                    {SERVICE_LEVEL_LABELS[attendance.serviceLevel]}
                  </span>
                </td>
                <td>
                  <AttendanceStatusBadge status={attendance.status} />
                </td>
                <td className="attendance-list-table__num attendance-list-table__value">
                  {/* Sem itens = nunca foi confirmado (rascunho, ou cancelado
                      ainda em rascunho) — grand_total é "0.00" por padrão nesse
                      caso e mostrar como valor real seria enganoso. Um
                      cancelado que chegou a ser confirmado antes tem itens e
                      mostra o total de verdade. */}
                  {attendance.items.length === 0 ? '—' : formatCurrencyBRL(attendance.grandTotal)}
                </td>
                <td
                  className="attendance-list-table__actions"
                  onClick={(event) => event.stopPropagation()}
                >
                  <Link
                    to={`/operacao/${attendance.id}`}
                    className="attendance-list-table__view-button"
                    title="Ver detalhes do protocolo"
                    aria-label={`Ver detalhes do protocolo ${attendance.protocolNumber ?? 'rascunho'}`}
                  >
                    <EyeIcon />
                  </Link>
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
