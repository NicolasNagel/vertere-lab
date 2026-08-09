import { describe, expect, test } from 'vitest'

import { groupItemsByProtocol } from './group-by-protocol'

describe('groupItemsByProtocol', () => {
  test('sums totals of items sharing the same attendance', () => {
    const groups = groupItemsByProtocol([
      {
        attendanceId: 'att-1',
        protocolNumber: '2026/000001',
        patientName: 'Rex',
        examName: 'Hemograma',
        serviceLevel: 'NORMAL',
        totalAmount: '75.00',
      },
      {
        attendanceId: 'att-1',
        protocolNumber: '2026/000001',
        patientName: 'Rex',
        examName: 'Bioquímico renal',
        serviceLevel: 'NORMAL',
        totalAmount: '120.00',
      },
    ])

    expect(groups).toHaveLength(1)
    expect(groups[0]).toMatchObject({
      attendanceId: 'att-1',
      examNames: ['Hemograma', 'Bioquímico renal'],
      isOnCall: false,
      totalAmount: '195',
    })
  })

  test('marks the group as on-call when any item in it is not NORMAL', () => {
    const groups = groupItemsByProtocol([
      {
        attendanceId: 'att-1',
        protocolNumber: '2026/000001',
        patientName: 'Akira',
        examName: 'Hemograma',
        serviceLevel: 'PLANTAO_ESPECIAL',
        totalAmount: '97.50',
      },
    ])

    expect(groups[0]?.isOnCall).toBe(true)
  })

  test('keeps distinct attendances as separate groups', () => {
    const groups = groupItemsByProtocol([
      {
        attendanceId: 'att-1',
        protocolNumber: '2026/000001',
        patientName: 'Rex',
        examName: 'Hemograma',
        serviceLevel: 'NORMAL',
        totalAmount: '75.00',
      },
      {
        attendanceId: 'att-2',
        protocolNumber: '2026/000002',
        patientName: 'Mia',
        examName: 'Urinálise',
        serviceLevel: 'NORMAL',
        totalAmount: '60.00',
      },
    ])

    expect(groups).toHaveLength(2)
  })
})
