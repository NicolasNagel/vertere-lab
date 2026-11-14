import { Link } from 'react-router'

import { useAttendancesQuery } from '../features/attendances/api/use-attendances-query'
import { useAttendanceStatusCountsQuery } from '../features/attendances/api/use-attendance-status-counts-query'
import { AttendanceStatusBadge } from '../features/attendances/components/attendance-status-badge'
import { AttendanceSummaryCards } from '../features/attendances/components/attendance-summary-cards'
import { useAuth } from '../features/auth/auth-context'
import { PageHeader } from '../shared/ui/page-header'
import { PlusIcon } from '../shared/ui/icons'
import { greetingFor } from './greeting'
import '../shared/ui/button.css'
import './home-page.css'

const dateFormatter = new Intl.DateTimeFormat('pt-BR', {
  weekday: 'long',
  day: '2-digit',
  month: 'long',
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

const UPCOMING_MODULES = [
  { title: 'Laudos pendentes', text: 'Disponível quando o módulo de laudos for liberado.' },
  { title: 'Em coleta', text: 'Disponível quando o módulo de coletas for liberado.' },
  {
    title: 'Exames mais pedidos',
    text: 'O ranking será exibido quando o endpoint agregado do dashboard estiver disponível.',
  },
]

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
  const countsQuery = useAttendanceStatusCountsQuery(
    canReadAttendances ? { serviceDateFrom: dateValue, serviceDateTo: dateValue } : null,
  )
  const firstName = user?.fullName.trim().split(/\s+/)[0] ?? 'equipe'
  const attendances = attendancesQuery.data?.items ?? []

  return (
    <div className="dashboard-page">
      <PageHeader
        subtitle={<span className="dashboard-page__date">{dateFormatter.format(today)}</span>}
        title={`${greetingFor(today)}, ${firstName}.`}
        actions={
          user?.permissions.includes('attendances.create') && (
            <Link className="button button--primary" to="/operacao/novo">
              <PlusIcon /> Novo protocolo
            </Link>
          )
        }
      />

      <AttendanceSummaryCards counts={countsQuery.data} scopeLabel="de hoje" />

      <div className="dashboard-page__grid">
        <section className="dashboard-card dashboard-activity">
          <header className="dashboard-card__header">
            <h2>Atividade do dia</h2>
            <Link to="/operacao">Ver todos</Link>
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
              <span className="dashboard-activity__protocol">
                {attendance.protocolNumber ?? 'Rascunho'}
              </span>
              <span className="dashboard-activity__exams">
                {attendance.items.map((item) => item.examName).join(' · ') || 'Sem exames'}
              </span>
              <AttendanceStatusBadge status={attendance.status} />
              <time className="dashboard-activity__time">
                {timeFormatter.format(new Date(attendance.createdAt))}
              </time>
            </Link>
          ))}
        </section>

        <aside className="dashboard-page__side">
          <section className="dashboard-card">
            <header className="dashboard-card__header">
              <h2>Em breve</h2>
            </header>
            <ul className="dashboard-upcoming">
              {UPCOMING_MODULES.map((module) => (
                <li key={module.title}>
                  <strong>{module.title}</strong>
                  <span>{module.text}</span>
                </li>
              ))}
            </ul>
          </section>
          <section className="dashboard-attention">
            <strong>Atenção</strong>
            <p>Laudos e alertas clínicos ainda não fazem parte do núcleo liberado.</p>
          </section>
        </aside>
      </div>
    </div>
  )
}
