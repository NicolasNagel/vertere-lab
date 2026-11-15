import { CalendarIcon, ClockIcon } from '../../../shared/ui/icons'
import { TextField } from '../../../shared/ui/text-field'
import {
  WEEKDAYS,
  WEEKDAY_PRESETS,
  crossesMidnight,
  sameSchedule,
  scheduleError,
  type FeeScheduleValue,
} from '../lib/fee-schedule'
import './fees.css'

interface FeeScheduleFieldsProps {
  idPrefix: string
  value: FeeScheduleValue
  disabled?: boolean
  onChange: (value: FeeScheduleValue) => void
}

/** Dias da semana (chips com atalhos) e horário de início/fim. Tudo informativo. */
export function FeeScheduleFields({ idPrefix, value, disabled, onChange }: FeeScheduleFieldsProps) {
  const error = scheduleError(value)

  function toggle(day: number) {
    const weekdays = value.weekdays.includes(day)
      ? value.weekdays.filter((item) => item !== day)
      : [...value.weekdays, day]
    onChange({ ...value, weekdays })
  }

  return (
    <>
      <fieldset className="fees__days" disabled={disabled}>
        <legend className="fees__legend">
          <CalendarIcon /> Dias da semana
        </legend>
        <div className="fees__chips" role="group" aria-label="Dias da semana">
          {WEEKDAYS.map((day) => {
            const active = value.weekdays.includes(day.value)
            return (
              <button
                key={day.value}
                type="button"
                className="fees__chip"
                aria-pressed={active}
                aria-label={day.long}
                data-active={active || undefined}
                onClick={() => toggle(day.value)}
              >
                {day.short}
              </button>
            )
          })}
        </div>
        <div className="fees__presets">
          {WEEKDAY_PRESETS.map((preset) => (
            <button
              key={preset.label}
              type="button"
              className="fees__preset"
              data-active={
                sameSchedule(
                  { ...value, startTime: '', endTime: '' },
                  {
                    weekdays: [...preset.weekdays],
                    startTime: '',
                    endTime: '',
                  },
                ) || undefined
              }
              onClick={() => onChange({ ...value, weekdays: [...preset.weekdays] })}
            >
              {preset.label}
            </button>
          ))}
          {value.weekdays.length > 0 && (
            <button
              type="button"
              className="fees__preset"
              onClick={() => onChange({ ...value, weekdays: [] })}
            >
              Limpar
            </button>
          )}
        </div>
      </fieldset>
      <div className="fees__row">
        <TextField
          id={`${idPrefix}-start`}
          type="time"
          label="Horário de início"
          icon={<ClockIcon />}
          disabled={disabled}
          value={value.startTime}
          onChange={(event) => onChange({ ...value, startTime: event.target.value })}
        />
        <TextField
          id={`${idPrefix}-end`}
          type="time"
          label="Horário de fim"
          icon={<ClockIcon />}
          disabled={disabled}
          value={value.endTime}
          errorMessage={error}
          onChange={(event) => onChange({ ...value, endTime: event.target.value })}
        />
      </div>
      {crossesMidnight(value) && (
        <p className="fees__note">O horário termina no dia seguinte (vira a meia-noite).</p>
      )}
      <p className="fees__note">
        Dias e horário são só informativos: o tipo do atendimento é escolhido na hora do registro e
        não muda o cálculo.
      </p>
    </>
  )
}
