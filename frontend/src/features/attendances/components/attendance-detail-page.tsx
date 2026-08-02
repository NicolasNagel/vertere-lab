import { useState } from 'react'
import { Link, useParams } from 'react-router'

import { ApiError } from '../../../shared/api/errors'
import { Button } from '../../../shared/ui/button'
import { ArrowLeftIcon } from '../../../shared/ui/icons'
import { useAuth } from '../../auth/auth-context'
import { useAttendanceQuery } from '../api/use-attendance-query'
import { AttendanceCancelModal } from './attendance-cancel-modal'
import { AttendanceConfirmationForm } from './attendance-confirmation-form'
import { AttendanceReadonlyDetail } from './attendance-readonly-detail'
import { AttendanceStatusBadge } from './attendance-status-badge'
import { AttendanceTimeline } from './attendance-timeline'
import './attendance-detail-page.css'

const CANCELLABLE_STATUSES = new Set(['DRAFT', 'CONFIRMED'])

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

  const canCancelThisAttendance =
    canCancel && !!attendanceQuery.data && CANCELLABLE_STATUSES.has(attendanceQuery.data.status)

  return (
    <div className="attendance-detail-page">
      <div className="attendance-detail-page__header">
        <div>
          <div className="attendance-detail-page__eyebrow">
            Operação · {attendanceQuery.data?.protocolNumber ?? 'Atendimento'}
          </div>
          <h1 className="attendance-detail-page__title">
            {attendanceQuery.data?.status === 'DRAFT' ? 'Confirmação de atendimento' : 'Atendimento'}
          </h1>
        </div>
        {attendanceQuery.data && (
          <div className="attendance-detail-page__actions">
            <Link to="/operacao" className="attendance-detail-page__back-link">
              <ArrowLeftIcon />
              Voltar
            </Link>
            <AttendanceStatusBadge status={attendanceQuery.data.status} />
            {canCancelThisAttendance && (
              <Button type="button" variant="ghost" onClick={() => setShowCancelModal(true)}>
                Cancelar atendimento
              </Button>
            )}
          </div>
        )}
      </div>

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
          (attendanceQuery.data.status === 'DRAFT' ? (
            <AttendanceConfirmationForm
              attendance={attendanceQuery.data}
              onConfirmed={() => void attendanceQuery.refetch()}
            />
          ) : (
            <AttendanceReadonlyDetail attendance={attendanceQuery.data} />
          ))}

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
