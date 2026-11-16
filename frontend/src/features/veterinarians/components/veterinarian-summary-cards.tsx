import { CheckIcon, ClinicsIcon, UserIcon } from '../../../shared/ui/icons'
import '../../attendances/components/attendance-summary-cards.css'

interface VeterinarianSummaryCardsProps {
  /** Totais do servidor para a busca atual; `undefined` enquanto carrega. */
  total: number | undefined
  active: number | undefined
  autonomous: number | undefined
}

/** Cartões de resumo da lista de veterinários, no padrão dos cartões da Operação. */
export function VeterinarianSummaryCards({
  total,
  active,
  autonomous,
}: VeterinarianSummaryCardsProps) {
  const cards = [
    {
      label: 'Veterinários',
      value: total,
      hint: 'na busca atual',
      icon: <UserIcon />,
    },
    {
      label: 'Ativos',
      value: active,
      hint: 'disponíveis para atendimentos',
      icon: <CheckIcon />,
    },
    {
      label: 'Autônomos',
      value: autonomous,
      hint: 'sem vínculo obrigatório com clínica',
      icon: <ClinicsIcon />,
    },
  ]
  return (
    <section className="attendance-summary-cards" aria-label="Resumo dos veterinários">
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
