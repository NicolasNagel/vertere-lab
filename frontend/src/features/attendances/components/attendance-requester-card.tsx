import type { Clinic } from '../../clinics/api/clinics-api'
import type { Veterinarian } from '../../veterinarians/api/veterinarians-api'

interface AttendanceRequesterCardProps {
  clinic: Clinic | undefined
  veterinarian: Veterinarian | undefined
}

/** Read-only "Solicitante" card — clínica + veterinário do atendimento. Sem
 * edição própria: troca de clínica/veterinário só é permitida em `DRAFT`,
 * pela tela de confirmação (`AttendanceHeaderDetails`), nunca aqui. */
export function AttendanceRequesterCard({ clinic, veterinarian }: AttendanceRequesterCardProps) {
  return (
    <section className="attendance-readonly-detail__section">
      <h2 className="attendance-readonly-detail__section-title">Solicitante</h2>
      <div className="attendance-readonly-detail__field-list">
        <div className="attendance-readonly-detail__field-row">
          <span className="attendance-readonly-detail__label">Clínica</span>
          <span className="attendance-readonly-detail__value">{clinic?.name ?? '—'}</span>
        </div>
        <div className="attendance-readonly-detail__field-row">
          <span className="attendance-readonly-detail__label">Veterinário</span>
          <span className="attendance-readonly-detail__value">{veterinarian?.name ?? '—'}</span>
        </div>
        <div className="attendance-readonly-detail__field-row">
          <span className="attendance-readonly-detail__label">CRMV</span>
          <span className="attendance-readonly-detail__value attendance-readonly-detail__mono">
            {veterinarian?.crmv ?? '—'}
          </span>
        </div>
        <div className="attendance-readonly-detail__field-row">
          <span className="attendance-readonly-detail__label">Contato</span>
          <span className="attendance-readonly-detail__value attendance-readonly-detail__mono">
            {veterinarian?.phone ?? '—'}
          </span>
        </div>
      </div>
    </section>
  )
}
