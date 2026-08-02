import type { Patient } from '../../patients/api/patients-api'
import type { Species } from '../../patients/api/patients-api'

const SEX_LABELS: Record<Patient['sex'], string> = {
  MALE: 'Macho',
  FEMALE: 'Fêmea',
}

interface AttendancePatientCardProps {
  patient: Patient | undefined
  species: Species[] | undefined
}

/** Read-only "Paciente" card. Troca de paciente só é permitida em `DRAFT`,
 * pela tela de confirmação — esta é só a ficha resumida do atendimento. */
export function AttendancePatientCard({ patient, species }: AttendancePatientCardProps) {
  const speciesName = species?.find((item) => item.id === patient?.speciesId)?.name ?? '—'

  return (
    <section className="attendance-readonly-detail__section">
      <h2 className="attendance-readonly-detail__section-title">Paciente</h2>
      <div className="attendance-readonly-detail__field-list">
        <div className="attendance-readonly-detail__field-row">
          <span className="attendance-readonly-detail__label">Nome</span>
          <span className="attendance-readonly-detail__value">{patient?.name ?? '—'}</span>
        </div>
        <div className="attendance-readonly-detail__field-row">
          <span className="attendance-readonly-detail__label">Espécie</span>
          <span className="attendance-readonly-detail__value">
            {patient ? [speciesName, patient.breed, SEX_LABELS[patient.sex]].filter(Boolean).join(' · ') : '—'}
          </span>
        </div>
        <div className="attendance-readonly-detail__field-row">
          <span className="attendance-readonly-detail__label">Idade</span>
          <span className="attendance-readonly-detail__value">{patient?.ageDescription ?? '—'}</span>
        </div>
        <div className="attendance-readonly-detail__field-row">
          <span className="attendance-readonly-detail__label">Tutor</span>
          <span className="attendance-readonly-detail__value">{patient?.ownerName ?? '—'}</span>
        </div>
      </div>
    </section>
  )
}
