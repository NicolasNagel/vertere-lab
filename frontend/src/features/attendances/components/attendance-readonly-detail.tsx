import { formatCurrencyBRL, formatDate, formatServiceDateTime } from '../../../shared/lib/formatters'
import { useAuth } from '../../auth/auth-context'
import { useClinicQuery } from '../../clinics/api/use-clinic-query'
import { usePatientQuery } from '../../patients/api/use-patient-query'
import { useSpeciesQuery } from '../../patients/api/use-species-query'
import { useVeterinarianQuery } from '../../veterinarians/api/use-veterinarian-query'
import { SERVICE_LEVEL_LABELS, type Attendance } from '../api/attendances-api'
import { AttendanceExamCategoryTag } from './attendance-exam-category-tag'
import { AttendanceNotesSection } from './attendance-notes-section'
import { AttendancePatientCard } from './attendance-patient-card'
import { AttendanceRequesterCard } from './attendance-requester-card'
import './attendance-readonly-detail.css'

const COLLECTION_METHOD_LABELS: Record<Attendance['collectionMethod'], string> = {
  INTERNAL: 'Internos',
  HELITO_NICOLAS: 'Helito/Nicolas',
  MARLI: 'Marli',
  COURIER: 'Motoboy',
  UBER: 'Uber',
}

interface AttendanceReadonlyDetailProps {
  attendance: Attendance
}

/** Atendimento que não está mais em `DRAFT` — edição de clínica/veterinário/
 * paciente fica restrita à confirmação (`AttendanceHeaderDetails`, só em
 * `DRAFT`); aqui só `notes` é editável (`AttendanceNotesSection`), conforme
 * `.claude/rules/12-attendance.md` ("CONFIRMED: edição controlada"). Layout
 * de duas colunas inspirado em `assets/features/screens/Tela 18 - Detalhe
 * do Protocolo.html` — adaptado aos tokens/cards já usados em
 * `closure-existing-view.css`, não copiado do mockup. */
export function AttendanceReadonlyDetail({ attendance }: AttendanceReadonlyDetailProps) {
  const { user } = useAuth()
  const canEditNotes = user?.permissions.includes('attendances.update') ?? false

  const clinicQuery = useClinicQuery(attendance.clinicId)
  const veterinarianQuery = useVeterinarianQuery(attendance.veterinarianId)
  const patientQuery = usePatientQuery(attendance.patientId)
  const speciesQuery = useSpeciesQuery()

  return (
    <div className="attendance-readonly-detail">
      {attendance.protocolNumber && (
        <span className="attendance-readonly-detail__protocol">{attendance.protocolNumber}</span>
      )}

      {attendance.cancelReason && (
        <p className="attendance-readonly-detail__cancel-reason">
          Motivo do cancelamento: {attendance.cancelReason}
        </p>
      )}

      <div className="attendance-readonly-detail__columns">
        <div className="attendance-readonly-detail__column">
          <div className="attendance-readonly-detail__row">
            <AttendanceRequesterCard
              clinic={clinicQuery.data}
              veterinarian={veterinarianQuery.data}
            />
            <AttendancePatientCard patient={patientQuery.data} species={speciesQuery.data} />
          </div>

          <section className="attendance-readonly-detail__section">
            <h2 className="attendance-readonly-detail__section-title">Exames</h2>
            {attendance.items.length === 0 ? (
              <p className="attendance-readonly-detail__hint">Nenhum exame associado.</p>
            ) : (
              <ul className="attendance-readonly-detail__items">
                {attendance.items.map((item) => (
                  <li key={item.id} className="attendance-readonly-detail__item">
                    <AttendanceExamCategoryTag examId={item.examId} />
                    <span className="attendance-readonly-detail__item-name">
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
            <h2 className="attendance-readonly-detail__section-title">Coleta & atendimento</h2>
            <div className="attendance-readonly-detail__field-list attendance-readonly-detail__field-list--grid">
              <div className="attendance-readonly-detail__field-row attendance-readonly-detail__field-row--stack">
                <span className="attendance-readonly-detail__label">Tipo</span>
                <span className="attendance-readonly-detail__value">
                  {SERVICE_LEVEL_LABELS[attendance.serviceLevel]}
                </span>
              </div>
              <div className="attendance-readonly-detail__field-row attendance-readonly-detail__field-row--stack">
                <span className="attendance-readonly-detail__label">Método de coleta</span>
                <span className="attendance-readonly-detail__value">
                  {COLLECTION_METHOD_LABELS[attendance.collectionMethod]}
                </span>
              </div>
              <div className="attendance-readonly-detail__field-row attendance-readonly-detail__field-row--stack">
                <span className="attendance-readonly-detail__label">Data do atendimento</span>
                <span className="attendance-readonly-detail__value">
                  {formatServiceDateTime(attendance.serviceDate, attendance.createdAt)}
                </span>
              </div>
            </div>
          </section>

          <AttendanceNotesSection
            attendance={attendance}
            canEdit={canEditNotes && attendance.status === 'CONFIRMED'}
          />
        </div>

        <div className="attendance-readonly-detail__column attendance-readonly-detail__column--side">
          <section className="attendance-readonly-detail__section attendance-readonly-detail__section--valor">
            <h2 className="attendance-readonly-detail__section-title">Valor</h2>
            {attendance.items.map((item) => (
              <div key={item.id} className="attendance-readonly-detail__field-row">
                <span>
                  {item.examName}
                  {item.quantity > 1 ? ` ×${item.quantity}` : ''}
                </span>
                <span className="attendance-readonly-detail__mono">
                  {formatCurrencyBRL(item.totalAmount)}
                </span>
              </div>
            ))}
            <div className="attendance-readonly-detail__field-row">
              <span>Desconto</span>
              <span className="attendance-readonly-detail__mono">
                {formatCurrencyBRL(attendance.discountTotal)}
              </span>
            </div>
            {Number(attendance.surchargeTotal) > 0 && (
              <div className="attendance-readonly-detail__field-row">
                <span>Acréscimo</span>
                <span className="attendance-readonly-detail__mono">
                  {formatCurrencyBRL(attendance.surchargeTotal)}
                </span>
              </div>
            )}
            <div className="attendance-readonly-detail__field-row">
              <span>Taxa de plantão</span>
              <span className="attendance-readonly-detail__mono">
                {Number(attendance.onCallFee) > 0
                  ? formatCurrencyBRL(attendance.onCallFee)
                  : 'não se aplica'}
              </span>
            </div>
            <div className="attendance-readonly-detail__total">
              <span>Total</span>
              <span className="attendance-readonly-detail__total-value">
                {formatCurrencyBRL(attendance.grandTotal)}
              </span>
            </div>
          </section>

          <section className="attendance-readonly-detail__section">
            <h2 className="attendance-readonly-detail__section-title">Fechamento</h2>
            <p className="attendance-readonly-detail__hint">
              {attendance.billingCompetence
                ? `Competência: ${formatDate(attendance.billingCompetence)}`
                : 'Ainda sem competência de faturamento definida.'}
            </p>
          </section>
        </div>
      </div>
    </div>
  )
}
