import { CheckIcon, LockIcon, PatientsIcon } from '../../../shared/ui/icons'
import '../../attendances/components/attendance-summary-cards.css'

interface PatientSummaryCardsProps {
  /** Totais do servidor para a busca atual; `undefined` enquanto carrega. */
  total: number | undefined
  active: number | undefined
  inactive: number | undefined
}

/** Cartões de resumo da lista de pacientes, no padrão dos cartões da Operação. */
export function PatientSummaryCards({ total, active, inactive }: PatientSummaryCardsProps) {
  const cards = [
    { label: 'Pacientes', value: total, hint: 'na busca atual', icon: <PatientsIcon /> },
    {
      label: 'Ativos',
      value: active,
      hint: 'disponíveis para atendimentos',
      icon: <CheckIcon />,
    },
    {
      label: 'Inativos',
      value: inactive,
      hint: 'somente leitura até reativar',
      icon: <LockIcon />,
    },
  ]
  return (
    <section className="attendance-summary-cards" aria-label="Resumo dos pacientes">
      {cards.map((card) => (
        <article key={card.label} className="attendance-summary-card">
          <header className="attendance-summary-card__label">
            <span>{card.label}</span>
            <span className="attendance-summary-card__icon">{card.icon}</span>
          </header>
          <strong className="attendance-summary-card__value">{card.value ?? '—'}</strong>
          <small className="attendance-summary-card__hint">{card.hint}</small>
        </article>
      ))}
    </section>
  )
}
