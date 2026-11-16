import { expect, test } from 'vitest'

import type { Permission } from '../api/roles-api'
import { groupPermissionsByCategory } from './permission-groups'

function permission(code: string): Permission {
  return { id: code, code, description: code, masterOnly: false }
}

test('groups permissions by category in a fixed order, omits empty categories and rejects unmapped codes', () => {
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

  const onlyAdmin = groupPermissionsByCategory([permission('users.read')])
  expect(onlyAdmin).toHaveLength(1)
  expect(onlyAdmin[0]?.category).toBe('Administração')
  expect(onlyAdmin[0]?.permissions).toEqual([permission('users.read')])

  // Código sem categoria falha alto em vez de sumir silenciosamente.
  expect(() => groupPermissionsByCategory([permission('does.not_exist')])).toThrow(
    /não está mapeada em nenhuma categoria/,
  )
})
