import { expect, test } from 'vitest'

import { groupItemsByProtocol } from './group-by-protocol'

function item(overrides: Record<string, string>) {
  return {
    attendanceId: 'att-1',
    protocolNumber: 'P000001/26',
    patientName: 'Rex',
    examName: 'Hemograma',
    serviceLevel: 'NORMAL',
    totalAmount: '75.00',
    ...overrides,
  }
}

test('groups items by attendance, sums their totals and flags on-call groups', () => {
  // Itens do mesmo atendimento somam e viram um grupo só.
  const shared = groupItemsByProtocol([
    item({}),
    item({ examName: 'Bioquímico renal', totalAmount: '120.00' }),
  ])
  expect(shared).toHaveLength(1)
  expect(shared[0]).toMatchObject({
    attendanceId: 'att-1',
    examNames: ['Hemograma', 'Bioquímico renal'],
    isOnCall: false,
    totalAmount: '195.00',
  })

  // Soma em centavos: 0.10 + 0.20 não vira 0.30000000000000004.
  const cents = groupItemsByProtocol([
    item({ totalAmount: '0.10' }),
    item({ examName: 'Outro', totalAmount: '0.20' }),
  ])
  expect(cents[0]?.totalAmount).toBe('0.30')

  // Qualquer item fora de NORMAL marca o grupo como plantão.
  const onCall = groupItemsByProtocol([
    item({ patientName: 'Akira', serviceLevel: 'PLANTAO_ESPECIAL', totalAmount: '97.50' }),
  ])
  expect(onCall[0]?.isOnCall).toBe(true)

  // Atendimentos distintos continuam em grupos separados.
  const distinct = groupItemsByProtocol([
    item({}),
    item({
      attendanceId: 'att-2',
      protocolNumber: 'P000002/26',
      patientName: 'Mia',
      examName: 'Urinálise',
      totalAmount: '60.00',
    }),
  ])
  expect(distinct).toHaveLength(2)
})
