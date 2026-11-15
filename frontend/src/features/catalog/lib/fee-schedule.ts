/** Dias da semana e horário (informativos) de uma taxa. 0 = segunda … 6 = domingo. */
export interface FeeScheduleValue {
  weekdays: number[]
  /** "HH:MM" ou "" quando não definido. */
  startTime: string
  endTime: string
}

export const EMPTY_SCHEDULE: FeeScheduleValue = {
  weekdays: [],
  startTime: '',
  endTime: '',
}

export const WEEKDAYS = [
  { value: 0, short: 'Seg', long: 'Segunda-feira' },
  { value: 1, short: 'Ter', long: 'Terça-feira' },
  { value: 2, short: 'Qua', long: 'Quarta-feira' },
  { value: 3, short: 'Qui', long: 'Quinta-feira' },
  { value: 4, short: 'Sex', long: 'Sexta-feira' },
  { value: 5, short: 'Sáb', long: 'Sábado' },
  { value: 6, short: 'Dom', long: 'Domingo' },
] as const

export const WEEKDAY_PRESETS = [
  { label: 'Seg-Sex', weekdays: [0, 1, 2, 3, 4] },
  { label: 'Fim de semana', weekdays: [5, 6] },
  { label: 'Todos', weekdays: [0, 1, 2, 3, 4, 5, 6] },
] as const

/** A API devolve "18:00:00"; os campos de hora trabalham com "18:00". */
export function timeFromApi(value: string | null | undefined): string {
  return value ? value.slice(0, 5) : ''
}

export function scheduleFromApi(source: {
  weekdays: number[]
  start_time: string | null
  end_time: string | null
}): FeeScheduleValue {
  return {
    weekdays: [...(source.weekdays ?? [])].sort((a, b) => a - b),
    startTime: timeFromApi(source.start_time),
    endTime: timeFromApi(source.end_time),
  }
}

export function scheduleToApi(value: FeeScheduleValue) {
  return {
    weekdays: [...value.weekdays].sort((a, b) => a - b),
    start_time: value.startTime || null,
    end_time: value.endTime || null,
  }
}

export function sameSchedule(a: FeeScheduleValue, b: FeeScheduleValue): boolean {
  return (
    a.startTime === b.startTime &&
    a.endTime === b.endTime &&
    a.weekdays.length === b.weekdays.length &&
    [...a.weekdays].sort().join() === [...b.weekdays].sort().join()
  )
}

/** Início e fim precisam vir juntos e ser diferentes (a virada de meia-noite é permitida). */
export function scheduleError(value: FeeScheduleValue): string | undefined {
  if (Boolean(value.startTime) !== Boolean(value.endTime)) {
    return 'Informe o horário de início e o de fim.'
  }
  if (value.startTime && value.startTime === value.endTime) {
    return 'O horário de fim deve ser diferente do início.'
  }
  return undefined
}

export function crossesMidnight(value: FeeScheduleValue): boolean {
  return Boolean(value.startTime && value.endTime) && value.endTime < value.startTime
}

function hourLabel(time: string): string {
  const [hours, minutes] = time.split(':')
  return minutes === '00' ? `${hours}h` : `${hours}:${minutes}`
}

export function daysLabel(weekdays: number[]): string {
  const days = [...weekdays].sort((a, b) => a - b)
  if (days.length === 0) return ''
  if (days.length === 7) return 'Todos os dias'
  if (days.length === 2 && days[0] === 5 && days[1] === 6) return 'Fim de semana'
  const first = days[0]!
  const last = days[days.length - 1]!
  if (days.length >= 3 && last - first + 1 === days.length) {
    return `${WEEKDAYS[first]!.short}-${WEEKDAYS[last]!.short}`
  }
  return days.map((day) => WEEKDAYS[day]!.short).join(', ')
}

export function hoursLabel(value: FeeScheduleValue): string {
  if (!value.startTime || !value.endTime) return ''
  return `${hourLabel(value.startTime)} às ${hourLabel(value.endTime)}`
}
