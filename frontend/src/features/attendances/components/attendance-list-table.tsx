import { Link } from 'react-router'

import { formatCurrencyBRL, formatDateTime } from '../../../shared/lib/formatters'
import type { Attendance } from '../api/attendances-api'
import { AttendanceStatusBadge } from './attendance-status-badge'
import './attendance-list-table.css'

export interface PatientDisplay {
  name: string
  detail: string
}

interface AttendanceListTableProps {
  attendances: Attendance[]
  clinicNameById: Record<string, string>
  veterinarianNameById: Record<string, string>
  patientDisplayById: Record<string, PatientDisplay>
}

function examsSummary(attendance: Attendance): string {
  if (attendance.items.length === 0) return '—'
  const [first, ...rest] = attendance.items
  if (!first) return '—'
  return rest.length === 0 ? first.examName : `${first.examName} +${rest.length}`
}

export function AttendanceListTable({
  attendances,
  clinicNameById,
  veterinarianNameById,
  patientDisplayById,
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
      <div className="attendance-list-table__header" role="row">
        <div>Protocolo</div>
        <div>Data · Hora</div>
        <div>Clínica</div>
        <div>Veterinário</div>
        <div>Paciente</div>
        <div>Exames</div>
        <div>Status</div>
        <div className="attendance-list-table__value-header">Valor</div>
      </div>
      {attendances.map((attendance) => {
        const patient = patientDisplayById[attendance.patientId]
        return (
          <Link
            key={attendance.id}
            to={`/operacao/${attendance.id}`}
            className="attendance-list-table__row"
            role="row"
          >
            <div className="attendance-list-table__protocol">
              {attendance.protocolNumber ?? 'Rascunho'}
            </div>
            <div className="attendance-list-table__muted">
              {formatDateTime(attendance.createdAt)}
            </div>
            <div
              className="attendance-list-table__clinic"
              title={clinicNameById[attendance.clinicId] ?? '—'}
            >
              {clinicNameById[attendance.clinicId] ?? '—'}
            </div>
            <div
              className="attendance-list-table__veterinarian"
              title={veterinarianNameById[attendance.veterinarianId] ?? '—'}
            >
              {veterinarianNameById[attendance.veterinarianId] ?? '—'}
            </div>
            <div
              className="attendance-list-table__patient"
              title={
                patient?.detail ? `${patient.name} · ${patient.detail}` : (patient?.name ?? '—')
              }
            >
              <span className="attendance-list-table__patient-name">
                {patient?.name ?? '—'}
              </span>
              {patient?.detail && (
                <span className="attendance-list-table__muted"> · {patient.detail}</span>
              )}
            </div>
            <div>{examsSummary(attendance)}</div>
            <div>
              <AttendanceStatusBadge status={attendance.status} />
            </div>
            <div className="attendance-list-table__value">
              {/* Sem itens = nunca foi confirmado (rascunho, ou cancelado
                  ainda em rascunho) — grand_total é "0.00" por padrão nesse
                  caso e mostrar como valor real seria enganoso. Um
                  cancelado que chegou a ser confirmado antes tem itens e
                  mostra o total de verdade. */}
              {attendance.items.length === 0 ? '—' : formatCurrencyBRL(attendance.grandTotal)}
            </div>
          </Link>
        )
      })}
    </div>
  )
}
