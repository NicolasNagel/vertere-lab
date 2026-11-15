import type { Attendance, AttendancePreview } from '../api/attendances-api'

export interface FeeRow {
  label: string
  amount: string
}

type FeeSource = Pick<
  Attendance | AttendancePreview,
  'onCallFee' | 'urgencyFee' | 'clinicFee' | 'feeLines'
>

/** Linhas de taxa do atendimento: plantão, urgência e cada taxa da clínica (só as positivas). */
export function feeRows(source: FeeSource): FeeRow[] {
  const rows: FeeRow[] = []
  if (Number(source.onCallFee) > 0) rows.push({ label: 'Taxa de plantão', amount: source.onCallFee })
  if (Number(source.urgencyFee) > 0) {
    rows.push({ label: 'Taxa de urgência', amount: source.urgencyFee })
  }
  const clinicLines = source.feeLines.filter((line) => line.kind === 'CLINICA')
  if (clinicLines.length > 0) {
    for (const line of clinicLines) rows.push({ label: line.label, amount: line.amount })
  } else if (Number(source.clinicFee) > 0) {
    rows.push({ label: 'Taxa da clínica', amount: source.clinicFee })
  }
  return rows
}
