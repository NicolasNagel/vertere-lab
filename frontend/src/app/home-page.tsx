import { Link } from 'react-router'

import { useAttendancesQuery } from '../features/attendances/api/use-attendances-query'
import { AttendanceStatusBadge } from '../features/attendances/components/attendance-status-badge'
import { useAuth } from '../features/auth/auth-context'
import { formatCurrencyBRL } from '../shared/lib/formatters'
import './home-page.css'

const dateFormatter = new Intl.DateTimeFormat('pt-BR', {
  weekday: 'long',
  day: '2-digit',
  month: 'short',
  year: 'numeric',
})

const timeFormatter = new Intl.DateTimeFormat('pt-BR', {
  hour: '2-digit',
  minute: '2-digit',
})

function localDateValue(date: Date): string {
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

export function HomePage() {
  const { user } = useAuth()
  const today = new Date()
  const dateValue = localDateValue(today)
  const canReadAttendances = user?.permissions.includes('attendances.read') ?? false
  const attendancesQuery = useAttendancesQuery(
    canReadAttendances
      ? { serviceDateFrom: dateValue, serviceDateTo: dateValue, page: 1, pageSize: 5 }
      : null,
  )
  const firstName = user?.fullName.trim().split(/\s+/)[0] ?? 'equipe'
  const attendances = attendancesQuery.data?.items ?? []
  const billedToday = attendances.reduce(
    (total, attendance) => total + Number(attendance.grandTotal),
    0,
  )

  return (
    <div className="dashboard-page">
      <header className="dashboard-page__header">
        <div>
          <div className="dashboard-page__date">{dateFormatter.format(today)}</div>
          <h1 className="dashboard-page__title">
            Bom dia, <em>{firstName}.</em>
          </h1>
        </div>
        {user?.permissions.includes('attendances.create') && (
          <Link className="dashboard-page__new" to="/operacao/novo">
            <span aria-hidden="true">＋</span> Novo protocolo
          </Link>
        )}
      </header>

      <section className="dashboard-page__kpis" aria-label="Resumo operacional">
        <article className="dashboard-kpi">
          <span>Protocolos hoje</span>
          <strong>{attendancesQuery.isLoading ? '—' : (attendancesQuery.data?.total ?? 0)}</strong>
          <small>atendimentos na data de hoje</small>
        </article>
        <article className="dashboard-kpi">
          <span>Laudos pendentes</span>
          <strong>—</strong>
          <small>módulo ainda não disponível</small>
        </article>
        <article className="dashboard-kpi">
          <span>Em coleta</span>
          <strong>—</strong>
          <small>módulo ainda não disponível</small>
        </article>
        <article className="dashboard-kpi dashboard-kpi--accent">
          <span>Atendido hoje</span>
          <strong>{formatCurrencyBRL(billedToday.toFixed(2))}</strong>
          <small>total dos protocolos exibidos</small>
        </article>
      </section>

      <div className="dashboard-page__grid">
        <section className="dashboard-card dashboard-activity">
          <header className="dashboard-card__header">
            <h2>Atividade do dia</h2>
            <Link to="/operacao">ver todos →</Link>
          </header>
          {attendancesQuery.isError && (
            <p className="dashboard-card__empty">Não foi possível carregar a atividade.</p>
          )}
          {!attendancesQuery.isLoading && !attendancesQuery.isError && attendances.length === 0 && (
            <p className="dashboard-card__empty">Nenhum protocolo registrado hoje.</p>
          )}
          {attendances.map((attendance) => (
            <Link
              className="dashboard-activity__item"
              to={`/operacao/${attendance.id}`}
              key={attendance.id}
            >
              <span className="dashboard-activity__icon" aria-hidden="true">＋</span>
              <span className="dashboard-activity__body">
                <strong>{attendance.protocolNumber ?? 'Rascunho'}</strong>
                <small>{attendance.items.map((item) => item.examName).join(' · ') || 'Sem exames'}</small>
              </span>
              <AttendanceStatusBadge status={attendance.status} />
              <time>{timeFormatter.format(new Date(attendance.createdAt))}</time>
            </Link>
          ))}
        </section>

        <aside className="dashboard-page__side">
          <section className="dashboard-card dashboard-placeholder">
            <header className="dashboard-card__header"><h2>Exames mais pedidos</h2></header>
            <p>O ranking será exibido quando o endpoint agregado do dashboard estiver disponível.</p>
          </section>
          <section className="dashboard-attention">
            <strong>ⓘ Atenção</strong>
            <p>Laudos e alertas clínicos ainda não fazem parte do núcleo liberado.</p>
          </section>
        </aside>
      </div>
    </div>
  )
}
