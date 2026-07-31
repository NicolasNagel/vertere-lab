import { formatCurrencyBRL, formatDate } from '../../../shared/lib/formatters'
import { useAuth } from '../../auth/auth-provider'
import type { Attendance } from '../api/attendances-api'
import { AttendanceHeaderDetails } from './attendance-header-details'
import { AttendanceNotesSection } from './attendance-notes-section'
import { AttendanceStatusBadge } from './attendance-status-badge'
import './attendance-readonly-detail.css'

interface AttendanceReadonlyDetailProps {
  attendance: Attendance
}

/** Atendimento que não está mais em `DRAFT` — edição/exames ficam para uma
 * fatia futura (edição controlada de `CONFIRMED`). Esta vista é só leitura,
 * suficiente para o clique na lista (Fatia 6) sempre levar a algum lugar
 * coerente, independente do status. */
export function AttendanceReadonlyDetail({ attendance }: AttendanceReadonlyDetailProps) {
  const { user } = useAuth()
  const canEditNotes = user?.permissions.includes('attendances.update') ?? false

  return (
    <div className="attendance-readonly-detail">
      <div className="attendance-readonly-detail__header">
        <AttendanceStatusBadge status={attendance.status} />
        {attendance.protocolNumber && (
          <span className="attendance-readonly-detail__protocol">
            {attendance.protocolNumber}
          </span>
        )}
      </div>

      {attendance.cancelReason && (
        <p className="attendance-readonly-detail__cancel-reason">
          Motivo do cancelamento: {attendance.cancelReason}
        </p>
      )}

      <AttendanceHeaderDetails attendance={attendance} editable={false} />

      <AttendanceNotesSection
        attendance={attendance}
        canEdit={canEditNotes && attendance.status === 'CONFIRMED'}
      />

      <section className="attendance-readonly-detail__section">
        <h2 className="attendance-readonly-detail__section-title">Exames</h2>
        {attendance.items.length === 0 ? (
          <p className="attendance-readonly-detail__hint">Nenhum exame associado.</p>
        ) : (
          <ul className="attendance-readonly-detail__items">
            {attendance.items.map((item) => (
              <li key={item.id} className="attendance-readonly-detail__item">
                <span>
                  {item.examName}
                  {item.quantity > 1 ? ` ×${item.quantity}` : ''}
                </span>
                <span className="attendance-readonly-detail__mono">
                  {formatCurrencyBRL(item.totalAmount)}
                </span>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="attendance-readonly-detail__section">
        <h2 className="attendance-readonly-detail__section-title">Valor</h2>
        <div className="attendance-readonly-detail__total">
          <span>Valor total</span>
          <span className="attendance-readonly-detail__total-value">
            {formatCurrencyBRL(attendance.grandTotal)}
          </span>
        </div>
        {attendance.billingCompetence && (
          <p className="attendance-readonly-detail__hint">
            Competência: {formatDate(attendance.billingCompetence)}
          </p>
        )}
      </section>
    </div>
  )
}
