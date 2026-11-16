import { ExamsIcon, TagIcon } from '../../../shared/ui/icons'
import type { FeeAttendanceType } from '../../attendances/api/clinic-fee-rules-api'
import { FEE_ATTENDANCE_TYPES } from '../lib/fee-conditions'
import { ExamConditionPicker } from './exam-condition-picker'
import './fees.css'

interface FeeConditionFieldsProps {
  idPrefix: string
  examIds: string[]
  attendanceTypes: FeeAttendanceType[]
  onExamIdsChange: (value: string[]) => void
  onAttendanceTypesChange: (value: FeeAttendanceType[]) => void
}

/** Condições da regra da clínica: exames (basta um) e tipos de atendimento (basta um). Vazio
 * significa "qualquer"; as duas condições preenchidas valem juntas. */
export function FeeConditionFields({
  idPrefix,
  examIds,
  attendanceTypes,
  onExamIdsChange,
  onAttendanceTypesChange,
}: FeeConditionFieldsProps) {
  function toggleType(type: FeeAttendanceType) {
    onAttendanceTypesChange(
      attendanceTypes.includes(type)
        ? attendanceTypes.filter((item) => item !== type)
        : [...attendanceTypes, type],
    )
  }

  return (
    <>
      <fieldset className="fees__days">
        <legend className="fees__legend">
          <TagIcon /> Tipo de atendimento
        </legend>
        <div className="fees__chips" role="group" aria-label="Tipo de atendimento">
          {FEE_ATTENDANCE_TYPES.map((type) => {
            const active = attendanceTypes.includes(type.value)
            return (
              <button
                key={type.value}
                type="button"
                className="fees__chip"
                aria-pressed={active}
                data-active={active || undefined}
                onClick={() => toggleType(type.value)}
              >
                {type.label}
              </button>
            )
          })}
        </div>
        <p className="fees__note">Sem seleção, vale para qualquer tipo.</p>
      </fieldset>
      <fieldset className="fees__days">
        <legend className="fees__legend">
          <ExamsIcon /> Exames
        </legend>
        <ExamConditionPicker idPrefix={idPrefix} examIds={examIds} onChange={onExamIdsChange} />
        <p className="fees__note">
          Sem exames, vale para qualquer exame. Basta um deles no atendimento.
        </p>
      </fieldset>
    </>
  )
}
