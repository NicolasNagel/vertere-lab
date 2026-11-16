import { daysLabel } from '../lib/fee-schedule'
import './fees.css'

interface ScheduleDaysProps {
  setting: {
    scheduleLabel: string
    schedule: { weekdays: number[]; startTime: string }
  }
}

/** Dias da taxa; para dados antigos (texto livre), mostra o texto que existia. */
export function ScheduleDays({ setting }: ScheduleDaysProps) {
  const label = daysLabel(setting.schedule.weekdays)
  if (label) return <>{label}</>
  if (setting.scheduleLabel && !setting.schedule.startTime) {
    return (
      <span className="fees__legacy" title="Texto livre anterior; edite para estruturar">
        {setting.scheduleLabel}
      </span>
    )
  }
  return <>—</>
}
