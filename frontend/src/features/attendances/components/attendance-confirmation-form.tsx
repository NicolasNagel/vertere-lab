import { Button } from '../../../shared/ui/button'
import { useAuth } from '../../auth/auth-context'
import { useAttendanceExamSelections } from '../api/use-attendance-exam-selections'
import type { Attendance } from '../api/attendances-api'
import { AttendanceExamSelectionList } from './attendance-exam-selection-list'
import { AttendanceHeaderDetails } from './attendance-header-details'
import { AttendanceSummaryPanel } from './attendance-summary-panel'
import './attendance-confirmation-form.css'

interface AttendanceConfirmationFormProps {
  attendance: Attendance
  onConfirmed: (attendance: Attendance) => void
}

export function AttendanceConfirmationForm({
  attendance,
  onConfirmed,
}: AttendanceConfirmationFormProps) {
  const { user } = useAuth()
  const canOverridePrice = user?.permissions.includes('attendances.override_price') ?? false
  const canEditHeader = user?.permissions.includes('attendances.update') ?? false

  const {
    selections,
    previewQuery,
    canConfirm,
    isPending,
    errorMessage,
    isConflict,
    addExam,
    removeExam,
    updateSelection,
    handleConfirm,
    handleReload,
  } = useAttendanceExamSelections(attendance, onConfirmed)

  return (
    <div className="attendance-confirmation-form">
      <AttendanceHeaderDetails attendance={attendance} editable={canEditHeader} />

      <div className="attendance-confirmation-form__main">
        <section className="attendance-confirmation-form__section">
          <div className="attendance-confirmation-form__section-header">
            <h2 className="attendance-confirmation-form__section-title">
              <span className="attendance-confirmation-form__badge">3</span>
              Exames
            </h2>
            <span className="attendance-confirmation-form__count">
              {selections.length} selecionado{selections.length === 1 ? '' : 's'}
            </span>
          </div>

          <AttendanceExamSelectionList
            selections={selections}
            canOverridePrice={canOverridePrice}
            disabled={isPending}
            onAdd={addExam}
            onRemove={removeExam}
            onUpdate={updateSelection}
          />
        </section>
      </div>

      <div className="attendance-confirmation-form__side">
        <AttendanceSummaryPanel
          items={previewQuery.data?.items ?? []}
          subtotal={previewQuery.data?.subtotal ?? '0.00'}
          discountTotal={previewQuery.data?.discountTotal ?? '0.00'}
          onCallFee={previewQuery.data?.onCallFee ?? '0.00'}
          grandTotal={previewQuery.data?.grandTotal ?? '0.00'}
          isLoading={selections.length > 0 && previewQuery.isLoading}
        />

        {selections.length === 0 && (
          <p className="attendance-confirmation-form__hint">
            Selecione ao menos um exame para ver o valor.
          </p>
        )}

        {errorMessage && (
          <div className="attendance-confirmation-form__domain-error" role="alert">
            <p>{errorMessage}</p>
            {isConflict && (
              <button type="button" onClick={handleReload}>
                Recarregar atendimento
              </button>
            )}
          </div>
        )}

        <Button type="button" disabled={!canConfirm} onClick={handleConfirm}>
          {isPending ? 'Confirmando…' : 'Confirmar atendimento'}
        </Button>
      </div>
    </div>
  )
}
