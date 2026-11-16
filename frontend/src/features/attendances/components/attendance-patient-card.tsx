import type { Patient, Species } from '../../patients/api/patients-api'

const SEX_LABELS: Record<Patient['sex'], string> = {
  MALE: 'Macho',
  FEMALE: 'Fêmea',
}

interface AttendancePatientCardProps {
  patient: Patient | undefined
  species: Species[] | undefined
}

function display(value: string | null | undefined): string {
  return value && value.trim() ? value : '—'
}

/** Conteúdo do bloco "Paciente": a ficha do paciente neste atendimento. */
export function AttendancePatientCard({ patient, species }: AttendancePatientCardProps) {
  const speciesName = species?.find((item) => item.id === patient?.speciesId)?.name

  return (
    <dl className="attendance-readonly-detail__fields">
        <dt>Nome</dt>
        <dd>{display(patient?.name)}</dd>
        <dt>Espécie</dt>
        <dd>{display(speciesName)}</dd>
        <dt>Raça</dt>
        <dd>{display(patient?.breed)}</dd>
        <dt>Sexo</dt>
        <dd>{patient ? SEX_LABELS[patient.sex] : '—'}</dd>
        <dt>Idade</dt>
        <dd>{display(patient?.ageDescription)}</dd>
        <dt>Tutor</dt>
        <dd>{display(patient?.ownerName)}</dd>
    </dl>
  )
}
