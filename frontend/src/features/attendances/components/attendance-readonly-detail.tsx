import { Fragment, useState } from 'react'

import { formatCurrencyBRL, formatDate, formatServiceDateTime } from '../../../shared/lib/formatters'
import { useAuth } from '../../auth/auth-context'
import { feeRows } from '../lib/attendance-fees'
import { useClinicQuery } from '../../clinics/api/use-clinic-query'
import { usePatientQuery } from '../../patients/api/use-patient-query'
import { useSpeciesQuery } from '../../patients/api/use-species-query'
import { useVeterinarianQuery } from '../../veterinarians/api/use-veterinarian-query'
import {
  COLLECTION_METHOD_LABELS,
  SERVICE_LEVEL_LABELS,
  type Attendance,
} from '../api/attendances-api'
import { AttendanceExamCategoryTag } from './attendance-exam-category-tag'
import { Button } from '../../../shared/ui/button'
import { AttendanceCorrectionBlock } from './attendance-correction-block'
import { AttendancePatientDataModal } from './attendance-patient-data-modal'
import { ExamsCorrectionForm } from './attendance-exams-correction'
import {
  NotesCorrectionForm,
  PatientCorrectionForm,
  RequesterCorrectionForm,
  ServiceCorrectionForm,
} from './attendance-header-corrections'
import { AttendancePatientCard } from './attendance-patient-card'
import { AttendanceRequesterCard } from './attendance-requester-card'
import './attendance-readonly-detail.css'

interface AttendanceReadonlyDetailProps {
  attendance: Attendance
}

function isPositive(value: string): boolean {
  return Number(value) > 0
}

/** Atendimento que não está mais em `DRAFT` — edição de clínica/veterinário/
 * paciente fica restrita à confirmação (`AttendanceHeaderDetails`, só em
 * `DRAFT`); aqui só `notes` é editável (`AttendanceNotesSection`), conforme
 * `.claude/rules/12-attendance.md` ("CONFIRMED: edição controlada").
 * Blocos no mesmo padrão do Novo Protocolo; valores só com `pricing.read`. */
export function AttendanceReadonlyDetail({ attendance }: AttendanceReadonlyDetailProps) {
  const { user } = useAuth()
  const [editingPatientData, setEditingPatientData] = useState(false)
  const permissions = user?.permissions ?? []
  // Tudo é corrigível depois de confirmado ou cancelado (com motivo); o backend decide de verdade.
  const canEdit =
    permissions.includes('attendances.update') &&
    (attendance.status === 'CONFIRMED' || attendance.status === 'CANCELLED')
  const showMoney = permissions.includes('pricing.read')
  const canDiscount = permissions.includes('attendances.override_price')
  const canEditPatientData = permissions.includes('patients.manage')

  const clinicQuery = useClinicQuery(attendance.clinicId)
  const veterinarianQuery = useVeterinarianQuery(attendance.veterinarianId)
  const patientQuery = usePatientQuery(attendance.patientId)
  const speciesQuery = useSpeciesQuery()

  return (
    <div className="attendance-readonly-detail">
      {attendance.cancelReason && (
        <p className="attendance-readonly-detail__cancel-reason">
          Motivo do cancelamento: {attendance.cancelReason}
        </p>
      )}

      <div
        className="attendance-readonly-detail__columns"
        data-money={showMoney ? 'true' : 'false'}
      >
        <div className="attendance-readonly-detail__column">
          <AttendanceCorrectionBlock
            title="Solicitante"
            attendanceId={attendance.id}
            canEdit={canEdit}
            form={({ close }) => <RequesterCorrectionForm attendance={attendance} onClose={close} />}
          >
            <AttendanceRequesterCard
              clinic={clinicQuery.data}
              veterinarian={veterinarianQuery.data}
            />
          </AttendanceCorrectionBlock>

          <AttendanceCorrectionBlock
            title="Paciente"
            attendanceId={attendance.id}
            canEdit={canEdit}
            actions={
              canEditPatientData && patientQuery.data ? (
                <Button
                  type="button"
                  variant="secondary"
                  className="attendance-correction-block__edit"
                  onClick={() => setEditingPatientData(true)}
                >
                  Corrigir cadastro
                </Button>
              ) : undefined
            }
            form={({ close }) => (
              <PatientCorrectionForm
                attendance={attendance}
                currentPatient={patientQuery.data}
                onClose={close}
              />
            )}
          >
            <AttendancePatientCard patient={patientQuery.data} species={speciesQuery.data} />
          </AttendanceCorrectionBlock>

          <AttendanceCorrectionBlock
            title="Atendimento"
            attendanceId={attendance.id}
            canEdit={canEdit}
            form={({ close }) => <ServiceCorrectionForm attendance={attendance} onClose={close} />}
          >
            <dl className="attendance-readonly-detail__fields">
              <dt>Tipo</dt>
              <dd>{SERVICE_LEVEL_LABELS[attendance.serviceLevel]}</dd>
              <dt>Forma de coleta</dt>
              <dd>{COLLECTION_METHOD_LABELS[attendance.collectionMethod]}</dd>
              <dt>Data</dt>
              <dd>{formatServiceDateTime(attendance.serviceDate, attendance.createdAt)}</dd>
            </dl>
          </AttendanceCorrectionBlock>

          <AttendanceCorrectionBlock
            title="Exames"
            attendanceId={attendance.id}
            canEdit={canEdit}
            form={({ close }) => (
              <ExamsCorrectionForm
                attendance={attendance}
                patient={patientQuery.data}
                showMoney={showMoney}
                canDiscount={canDiscount}
                onClose={close}
              />
            )}
          >
            {attendance.items.length === 0 ? (
              <p className="attendance-readonly-detail__hint">Nenhum exame associado.</p>
            ) : (
              <ul className="attendance-readonly-detail__items">
                {attendance.items.map((item) => (
                  <li
                    key={item.id}
                    className="attendance-readonly-detail__item"
                    data-removed={item.status === 'CANCELLED'}
                  >
                    <AttendanceExamCategoryTag examId={item.examId} />
                    <span className="attendance-readonly-detail__item-name">
                      {item.examName}
                      {item.quantity > 1 ? ` ×${item.quantity}` : ''}
                      {item.status === 'CANCELLED' && (
                        <span className="attendance-readonly-detail__muted">removido</span>
                      )}
                      {item.components.length > 0 && (
                        <span className="attendance-readonly-detail__muted">
                          {item.components.map((component) => component.name).join(', ')}
                        </span>
                      )}
                    </span>
                    {showMoney && item.status === 'ACTIVE' && (
                      <span className="attendance-readonly-detail__amount">
                        {formatCurrencyBRL(item.totalAmount)}
                        {isPositive(item.discountAmount) && (
                          <span className="attendance-readonly-detail__muted">
                            desconto − {formatCurrencyBRL(item.discountAmount)}
                          </span>
                        )}
                      </span>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </AttendanceCorrectionBlock>

          <AttendanceCorrectionBlock
            title="Observações"
            attendanceId={attendance.id}
            canEdit={canEdit}
            form={({ close }) => <NotesCorrectionForm attendance={attendance} onClose={close} />}
          >
            <p className="attendance-readonly-detail__notes">
              {attendance.notes || 'Nenhuma observação registrada.'}
            </p>
          </AttendanceCorrectionBlock>
        </div>

        <div className="attendance-readonly-detail__column">
          {showMoney && (
            <section className="attendance-readonly-detail__section">
              <h2 className="attendance-readonly-detail__section-title">Valor</h2>
              <dl className="attendance-readonly-detail__totals">
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
                    <dt>Acréscimo</dt>
                    <dd>+ {formatCurrencyBRL(attendance.surchargeTotal)}</dd>
                  </>
                )}
                {feeRows(attendance).map((row) => (
                  <Fragment key={row.label}>
                    <dt>{row.label}</dt>
                    <dd>+ {formatCurrencyBRL(row.amount)}</dd>
                  </Fragment>
                ))}
                <dt className="attendance-readonly-detail__grand">Total</dt>
                <dd className="attendance-readonly-detail__grand">
                  {formatCurrencyBRL(attendance.grandTotal)}
                </dd>
              </dl>
            </section>
          )}

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
      {editingPatientData && patientQuery.data && (
        <AttendancePatientDataModal
          patient={patientQuery.data}
          onClose={() => setEditingPatientData(false)}
        />
      )}
    </div>
  )
}
