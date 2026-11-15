import { formatCurrencyBRL, formatDate } from '../../../shared/lib/formatters'
import { CalendarIcon, ExamsIcon, PatientsIcon, BillingIcon } from '../../../shared/ui/icons'
import type { Exam } from '../api/catalog-api'
import '../../attendances/components/attendance-summary-cards.css'
import './exam-summary-cards.css'

interface ExamSummaryCardsProps {
  exam: Exam
  speciesNames: string[]
}

function validityHint(exam: Exam): string {
  const from =
    exam.priceValidFrom && !exam.priceValidFrom.startsWith('1900')
      ? `desde ${formatDate(exam.priceValidFrom)}`
      : 'sem data de início'
  return exam.priceValidTo ? `${from} até ${formatDate(exam.priceValidTo)}` : from
}

/** Faixa de resumo do exame, no padrão dos cartões da Operação. Preço só com `pricing.read`
 * (a API devolve null sem ela). */
export function ExamSummaryCards({ exam, speciesNames }: ExamSummaryCardsProps) {
  const active = exam.status === 'ACTIVE'
  return (
    <section className="attendance-summary-cards exam-summary-cards" aria-label="Resumo do exame">
      {exam.priceBase !== null && (
        <article className="attendance-summary-card">
          <header className="attendance-summary-card__label">
            <span>Preço vigente</span>
            <span className="attendance-summary-card__icon">
              <BillingIcon />
            </span>
          </header>
          <strong className="attendance-summary-card__value">
            {formatCurrencyBRL(exam.priceBase)}
          </strong>
          <small className="attendance-summary-card__hint">{validityHint(exam)}</small>
        </article>
      )}

      <article className="attendance-summary-card">
        <header className="attendance-summary-card__label">
          <span>Status</span>
          <span className="attendance-summary-card__icon">
            <CalendarIcon />
          </span>
        </header>
        <strong className="attendance-summary-card__value">{active ? 'Ativo' : 'Inativo'}</strong>
        <small className="attendance-summary-card__hint">
          {active ? 'disponível para novos atendimentos' : 'fora de novos atendimentos'}
        </small>
      </article>

      <article className="attendance-summary-card">
        <header className="attendance-summary-card__label">
          <span>Espécies</span>
          <span className="attendance-summary-card__icon">
            <PatientsIcon />
          </span>
        </header>
        <strong className="attendance-summary-card__value">{speciesNames.length}</strong>
        <small className="attendance-summary-card__hint">
          {speciesNames.length > 0 ? speciesNames.join(' · ') : 'nenhuma espécie vinculada'}
        </small>
      </article>

      {exam.isPanel && (
        <article className="attendance-summary-card">
          <header className="attendance-summary-card__label">
            <span>Exames no pacote</span>
            <span className="attendance-summary-card__icon">
              <ExamsIcon />
            </span>
          </header>
          <strong className="attendance-summary-card__value">{exam.componentExamIds.length}</strong>
          <small className="attendance-summary-card__hint">exames que compõem o pacote</small>
        </article>
      )}
    </section>
  )
}
