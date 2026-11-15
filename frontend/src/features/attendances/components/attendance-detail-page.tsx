import { useState } from 'react'
import { Link, useParams } from 'react-router'

import { ApiError } from '../../../shared/api/errors'
import { Button } from '../../../shared/ui/button'
import { ArrowLeftIcon } from '../../../shared/ui/icons'
import { PageHeader } from '../../../shared/ui/page-header'
import { useAuth } from '../../auth/auth-context'
import { CANCELLABLE_STATUSES } from '../api/attendances-api'
import { useAttendanceQuery } from '../api/use-attendance-query'
import { AttendanceCancelModal } from './attendance-cancel-modal'
import { AttendanceDraftPage } from './attendance-draft-page'
import { AttendanceReadonlyDetail } from './attendance-readonly-detail'
import { AttendanceStatusBadge } from './attendance-status-badge'
import { AttendanceTimeline } from './attendance-timeline'
import '../../../shared/ui/button.css'
import './attendance-detail-page.css'

export function AttendanceDetailPage() {
  const { attendanceId } = useParams<{ attendanceId: string }>()
  const { user } = useAuth()
  const canRead = user?.permissions.includes('attendances.read') ?? false
  const canCancel = user?.permissions.includes('attendances.cancel') ?? false
  const [showCancelModal, setShowCancelModal] = useState(false)

  const attendanceQuery = useAttendanceQuery(canRead ? (attendanceId ?? null) : null)

  const isForbidden =
    attendanceQuery.error instanceof ApiError && attendanceQuery.error.status === 403
  const isNotFound = attendanceQuery.error instanceof ApiError && attendanceQuery.error.status === 404
  const isGenericError = attendanceQuery.isError && !isForbidden && !isNotFound

  // Rascunho abre no próprio Novo Protocolo, já preenchido — não há tela paralela de confirmação.
  if (canRead && attendanceQuery.data?.status === 'DRAFT') {
    return <AttendanceDraftPage resumeAttendance={attendanceQuery.data} />
  }

  const canCancelThisAttendance =
    canCancel && !!attendanceQuery.data && CANCELLABLE_STATUSES.has(attendanceQuery.data.status)

  return (
    <div className="attendance-detail-page">
      <PageHeader
        title={attendanceQuery.data?.protocolNumber ?? 'Atendimento'}
        subtitle={
          attendanceQuery.data ? (
            <span className="attendance-detail-page__sub">
              <AttendanceStatusBadge status={attendanceQuery.data.status} />
            </span>
          ) : undefined
        }
        actions={
          <>
            <Link to="/operacao" className="button button--secondary">
              <ArrowLeftIcon />
              Voltar
            </Link>
            {canCancelThisAttendance && (
              <Button type="button" variant="cancel" onClick={() => setShowCancelModal(true)}>
                Cancelar atendimento
              </Button>
            )}
          </>
        }
      />

      <div className="attendance-detail-page__body">
        {!canRead && (
          <p className="attendance-detail-page__forbidden">
            Você não tem permissão para visualizar atendimentos.
          </p>
        )}

        {canRead && attendanceQuery.isLoading && (
          <p className="attendance-detail-page__hint">Carregando…</p>
        )}

        {canRead && isForbidden && (
          <p className="attendance-detail-page__forbidden">
            Você não tem permissão para visualizar este atendimento.
          </p>
        )}

        {canRead && isNotFound && (
          <p className="attendance-detail-page__forbidden">Atendimento não encontrado.</p>
        )}

        {canRead && isGenericError && (
          <p className="attendance-detail-page__error">
            Não foi possível carregar o atendimento. Tente novamente.
          </p>
        )}

        {canRead &&
          attendanceQuery.data &&
          <AttendanceReadonlyDetail attendance={attendanceQuery.data} />}

        {canRead && attendanceQuery.data && attendanceId && (
          <AttendanceTimeline attendanceId={attendanceId} />
        )}
      </div>

      {showCancelModal && attendanceQuery.data && (
        <AttendanceCancelModal
          attendance={attendanceQuery.data}
          onClose={() => setShowCancelModal(false)}
          onCancelled={() => setShowCancelModal(false)}
        />
      )}
    </div>
  )
}
