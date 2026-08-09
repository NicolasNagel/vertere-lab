import './closure-summary-cards.css'

export interface ClosureSummaryCard {
  id: string
  label: string
  value: string
  tone?: 'default' | 'warning' | 'total'
}

interface ClosureSummaryCardsProps {
  cards: ClosureSummaryCard[]
}

export function ClosureSummaryCards({ cards }: ClosureSummaryCardsProps) {
  return (
    <div className="closure-summary-cards">
      {cards.map((card) => (
        <div key={card.id} className="closure-summary-cards__card" data-tone={card.tone ?? 'default'}>
          <div className="closure-summary-cards__label">{card.label}</div>
          <div className="closure-summary-cards__value">{card.value}</div>
        </div>
      ))}
    </div>
  )
}
