import { expect, test } from 'vitest'

import type { Permission } from '../api/roles-api'
import { groupPermissionsByCategory } from './permission-groups'

function permission(code: string): Permission {
  return { id: code, code, description: code, masterOnly: false }
}

test('groups permissions by business category, in a fixed display order', () => {
  const groups = groupPermissionsByCategory([
    permission('users.read'),
    permission('attendances.create'),
    permission('closures.close'),
    permission('clinics.read'),
  ])

  expect(groups.map((group) => group.category)).toEqual([
    'Operação',
    'Cadastros',
    'Financeiro',
    'Administração',
  ])
})

test('omits categories that have no permission in the given list', () => {
  const groups = groupPermissionsByCategory([permission('users.read')])

  expect(groups).toHaveLength(1)
  expect(groups[0]?.category).toBe('Administração')
  expect(groups[0]?.permissions).toEqual([permission('users.read')])
})

test('throws for a permission code with no category mapping, instead of silently dropping it', () => {
  expect(() => groupPermissionsByCategory([permission('does.not_exist')])).toThrow(
    /não está mapeada em nenhuma categoria/,
  )
})
