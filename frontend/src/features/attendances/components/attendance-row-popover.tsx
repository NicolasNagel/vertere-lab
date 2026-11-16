import { Fragment } from 'react'
import { Link } from 'react-router'

import {
  formatCurrencyBRL,
  formatDateTime,
  formatServiceDateTime,
} from '../../../shared/lib/formatters'
import { KebabMenu, type KebabMenuItem } from '../../../shared/ui/kebab-menu'
import { SERVICE_LEVEL_LABELS, CANCELLABLE_STATUSES, type Attendance } from '../api/attendances-api'
import { useAttendanceTimelineQuery } from '../api/use-attendance-timeline-query'
import { feeRows } from '../lib/attendance-fees'
import type { PatientDisplay } from './attendance-list-table'
import { AttendanceStatusBadge } from './attendance-status-badge'
import { describeTimelineAction } from './attendance-timeline-labels'
import '../../../shared/ui/button.css'
import './attendance-row-popover.css'

export const ATTENDANCE_POPOVER_TITLE_ID = 'attendance-row-popover-title'

const HISTORY_LIMIT = 5

interface AttendanceRowPopoverProps {
  attendance: Attendance
  clinicName: string
  veterinarianName: string
  patient: PatientDisplay | undefined
  /** `pricing.read`: valores só aparecem para quem vê o financeiro. */
  showMoney: boolean
  canCancel: boolean
  onClose: () => void
  onCancel: (attendance: Attendance) => void
}

function isPositive(value: string): boolean {
  return Number(value) > 0
}

/** Resumo do que foi feito no atendimento, aberto ao clicar na linha da tabela de Operação.
 * Tudo vem da própria lista, exceto o histórico, que só é buscado ao abrir. */
export function AttendanceRowPopover({
  attendance,
  clinicName,
  veterinarianName,
  patient,
  showMoney,
  canCancel,
  onClose,
  onCancel,
}: AttendanceRowPopoverProps) {
  const timelineQuery = useAttendanceTimelineQuery(attendance.id, 1, true)
  const activeItems = attendance.items.filter((item) => item.status === 'ACTIVE')
  const history = timelineQuery.data?.items.slice(0, HISTORY_LIMIT) ?? []
  const showCancel = canCancel && CANCELLABLE_STATUSES.has(attendance.status)
  const menuItems: KebabMenuItem[] = showCancel
    ? [{ label: 'Cancelar atendimento', onSelect: () => onCancel(attendance), destructive: true }]
    : []
  const protocol = attendance.protocolNumber ?? 'Rascunho'

  return (
    <aside className="attendance-row-popover" aria-label="Resumo do atendimento">
      <header className="attendance-row-popover__header">
        <div className="attendance-row-popover__heading">
          <h2 id={ATTENDANCE_POPOVER_TITLE_ID} className="attendance-row-popover__title">
            {protocol}
          </h2>
          <div className="attendance-row-popover__sub">
            <AttendanceStatusBadge status={attendance.status} />
            <span>{SERVICE_LEVEL_LABELS[attendance.serviceLevel]}</span>
          </div>
        </div>
        <div className="attendance-row-popover__actions">
          <Link
            to={`/operacao/${attendance.id}`}
            className="button button--secondary attendance-row-popover__open"
          >
            Abrir atendimento
          </Link>
          {menuItems.length > 0 && <KebabMenu label="Mais ações" items={menuItems} />}
          <button
            type="button"
            className="attendance-row-popover__close"
            aria-label="Fechar resumo"
            onClick={onClose}
          >
            ×
          </button>
        </div>
      </header>

      <div className="attendance-row-popover__body">
      <dl className="attendance-row-popover__fields">
        <dt>Solicitante</dt>
        <dd>
          {veterinarianName}
          <span className="attendance-row-popover__muted">{clinicName}</span>
        </dd>
        <dt>Paciente</dt>
        <dd>
          {patient ? `${patient.name}${patient.detail ? ` · ${patient.detail}` : ''}` : '—'}
          {patient?.ownerName && (
            <span className="attendance-row-popover__muted">Tutor: {patient.ownerName}</span>
          )}
        </dd>
        <dt>Data</dt>
        <dd>{formatServiceDateTime(attendance.serviceDate, attendance.createdAt)}</dd>
      </dl>

      <section aria-labelledby="attendance-row-popover-exams">
        <h3 id="attendance-row-popover-exams" className="attendance-row-popover__section">
          Exames
        </h3>
        {activeItems.length === 0 ? (
          <p className="attendance-row-popover__muted">Nenhum exame neste atendimento.</p>
        ) : (
          <ul className="attendance-row-popover__exams">
            {activeItems.map((item) => (
              <li key={item.id}>
                <span>
                  {item.quantity > 1 ? `${item.quantity}× ` : ''}
                  {item.examName}
                  {item.components.length > 0 && (
                    <span className="attendance-row-popover__muted">
                      {item.components.map((component) => component.name).join(', ')}
                    </span>
                  )}
                </span>
                {showMoney && (
                  <span className="attendance-row-popover__amount">
                    {formatCurrencyBRL(item.totalAmount)}
                    {isPositive(item.discountAmount) && (
                      <span className="attendance-row-popover__muted">
                        desconto − {formatCurrencyBRL(item.discountAmount)}
                      </span>
                    )}
                  </span>
                )}
              </li>
            ))}
          </ul>
        )}
      </section>

      {showMoney && activeItems.length > 0 && (
        <dl className="attendance-row-popover__totals" aria-label="Valores">
          <dt>Subtotal</dt>
          <dd>{formatCurrencyBRL(attendance.subtotal)}</dd>
          {isPositive(attendance.discountTotal) && (
            <>
              <dt>Desconto</dt>
              <dd>− {formatCurrencyBRL(attendance.discountTotal)}</dd>
            </>
          )}
          {isPositive(attendance.surchargeTotal) && (
            <>
              <dt>Adicional</dt>
              <dd>+ {formatCurrencyBRL(attendance.surchargeTotal)}</dd>
            </>
          )}
          {feeRows(attendance).map((row) => (
            <Fragment key={row.label}>
              <dt>{row.label}</dt>
              <dd>+ {formatCurrencyBRL(row.amount)}</dd>
            </Fragment>
          ))}
          <dt className="attendance-row-popover__grand">Total</dt>
          <dd className="attendance-row-popover__grand">{formatCurrencyBRL(attendance.grandTotal)}</dd>
        </dl>
      )}

      {attendance.status === 'CANCELLED' && attendance.cancelReason && (
        <p className="attendance-row-popover__reason">
          Motivo do cancelamento: {attendance.cancelReason}
        </p>
      )}

      <section
        aria-labelledby="attendance-row-popover-history"
        className="attendance-row-popover__history-block"
      >
        <h3 id="attendance-row-popover-history" className="attendance-row-popover__section">
          Histórico
        </h3>
        {timelineQuery.isLoading && <p className="attendance-row-popover__muted">Carregando…</p>}
        {timelineQuery.isError && (
          <p className="attendance-row-popover__muted">Não foi possível carregar o histórico.</p>
        )}
        {timelineQuery.data && history.length === 0 && (
          <p className="attendance-row-popover__muted">Nenhum evento registrado.</p>
        )}
        {history.length > 0 && (
          <ul className="attendance-row-popover__history">
            {history.map((entry) => (
              <li key={entry.id}>
                <b>{describeTimelineAction(entry.action)}</b>
                <span className="attendance-row-popover__muted">
                  {entry.actorName ? `${entry.actorName} · ` : ''}
                  {formatDateTime(entry.occurredAt)}
                  {entry.reason ? ` · ${entry.reason}` : ''}
                </span>
              </li>
            ))}
          </ul>
        )}
      </section>

      </div>
    </aside>
  )
}
