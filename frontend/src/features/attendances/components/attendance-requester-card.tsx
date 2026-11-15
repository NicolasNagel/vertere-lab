import type { Clinic } from '../../clinics/api/clinics-api'
import type { Veterinarian } from '../../veterinarians/api/veterinarians-api'

interface AttendanceRequesterCardProps {
  clinic: Clinic | undefined
  veterinarian: Veterinarian | undefined
}

function display(value: string | null | undefined): string {
  return value && value.trim() ? value : '—'
}

/** Conteúdo do bloco "Solicitante": clínica + veterinário do atendimento. */
export function AttendanceRequesterCard({ clinic, veterinarian }: AttendanceRequesterCardProps) {
  return (
    <dl className="attendance-readonly-detail__fields">
        <dt>Clínica</dt>
        <dd>{display(clinic?.name)}</dd>
        <dt>Veterinário</dt>
        <dd>{display(veterinarian?.name)}</dd>
        <dt>CRMV</dt>
        <dd className="attendance-readonly-detail__mono">{display(veterinarian?.crmv)}</dd>
        <dt>Contato</dt>
        <dd className="attendance-readonly-detail__mono">{display(veterinarian?.phone)}</dd>
    </dl>
  )
}
