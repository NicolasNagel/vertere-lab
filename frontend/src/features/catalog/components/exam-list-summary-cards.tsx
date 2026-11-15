import { ExamsIcon } from '../../../shared/ui/icons'
import '../../attendances/components/attendance-summary-cards.css'

interface ExamListSummaryCardsProps {
  /** Totais vindos do servidor para os filtros atuais; `undefined` enquanto carrega. */
  total: number | undefined
  active: number | undefined
  inactive: number | undefined
  scopeLabel: string
}

/** Cartões de resumo da lista de exames, no padrão dos cartões da Operação. */
export function ExamListSummaryCards({
  total,
  active,
  inactive,
  scopeLabel,
}: ExamListSummaryCardsProps) {
  const cards = [
    { label: 'Exames', value: total, hint: scopeLabel },
    {
      label: 'Ativos',
      value: active,
      hint: 'disponíveis para novos atendimentos',
    },
    { label: 'Inativos', value: inactive, hint: 'fora de novos atendimentos' },
  ]
  return (
    <section className="attendance-summary-cards" aria-label="Resumo dos exames">
      {cards.map((card) => (
        <article key={card.label} className="attendance-summary-card">
          <header className="attendance-summary-card__label">
            <span>{card.label}</span>
            <span className="attendance-summary-card__icon">
              <ExamsIcon />
            </span>
          </header>
          <strong className="attendance-summary-card__value">{card.value ?? '—'}</strong>
          <small className="attendance-summary-card__hint">{card.hint}</small>
        </article>
      ))}
    </section>
  )
}
