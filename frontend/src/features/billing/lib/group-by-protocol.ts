/** Client-side regrouping of already-server-computed item totals for the
 * "por protocolo" table view (Tela 15) — never a financial decision, the
 * backend total per item is the canonical value; this only re-presents it
 * grouped by attendance. */

import { sumMoney } from '../../../shared/lib/money'

export interface ProtocolGroupableItem {
  attendanceId: string
  protocolNumber: string | null
  patientName: string
  examName: string
  serviceLevel: string | null
  totalAmount: string
}

export interface ProtocolGroup {
  attendanceId: string
  protocolNumber: string | null
  patientName: string
  examNames: string[]
  isOnCall: boolean
  totalAmount: string
}

export function groupItemsByProtocol<T extends ProtocolGroupableItem>(items: T[]): ProtocolGroup[] {
  const groups = new Map<string, ProtocolGroup>()
  for (const item of items) {
    const existing = groups.get(item.attendanceId)
    const isOnCall = item.serviceLevel !== null && item.serviceLevel !== 'NORMAL'
    if (existing) {
      existing.examNames.push(item.examName)
      existing.isOnCall = existing.isOnCall || isOnCall
      existing.totalAmount = sumMoney([existing.totalAmount, item.totalAmount])
    } else {
      groups.set(item.attendanceId, {
        attendanceId: item.attendanceId,
        protocolNumber: item.protocolNumber,
        patientName: item.patientName,
        examNames: [item.examName],
        isOnCall,
        totalAmount: item.totalAmount,
      })
    }
  }
  return Array.from(groups.values())
}
