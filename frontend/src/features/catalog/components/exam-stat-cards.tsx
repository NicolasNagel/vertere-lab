import { formatDate } from '../../../shared/lib/formatters'
import './exam-stat-cards.css'

interface ExamStatCardsProps {
  activeCount: number
  averagePriceLabel: string | null
  priceVisible: boolean
  lastUpdatedAt: string | null
}

export function ExamStatCards({
  activeCount,
  averagePriceLabel,
  priceVisible,
  lastUpdatedAt,
}: ExamStatCardsProps) {
  return (
    <div className="exam-stat-cards">
      <div className="exam-stat-cards__card">
        <div className="exam-stat-cards__label">Exames ativos</div>
        <div className="exam-stat-cards__value">{activeCount}</div>
      </div>
      {priceVisible && (
        <div className="exam-stat-cards__card">
          <div className="exam-stat-cards__label">Ticket médio</div>
          <div className="exam-stat-cards__value exam-stat-cards__value--mono">
            {averagePriceLabel ?? '—'}
          </div>
        </div>
      )}
      <div className="exam-stat-cards__card">
        <div className="exam-stat-cards__label">Última atualização</div>
        <div className="exam-stat-cards__date">
          {lastUpdatedAt ? formatDate(lastUpdatedAt) : '—'}
        </div>
      </div>
    </div>
  )
}
