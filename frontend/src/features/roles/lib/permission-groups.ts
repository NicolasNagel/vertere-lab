import type { Permission } from '../api/roles-api'

// Categoria de negócio (não mais prefixo técnico de recurso) — mais perto do
// mockup de referência (Operação/Cadastros/Financeiro/Administração), mas
// só cobrindo as ~34 permissões reais que já existem no backend
// (backend/app/modules/identity/infrastructure/seed.py). Os grupos "Laudos"
// e "Relatórios" do mockup ficam de fora de propósito: não existe permissão
// real pra eles ainda (Laudos é P1 futuro; os itens de "Relatórios" do
// mockup — produção por veterinário, operação sem valores — são telas de
// visualização sem permissão própria hoje). Não inventamos permissão nova só
// pra preencher essas seções.
const CATEGORY_ORDER = ['Operação', 'Cadastros', 'Financeiro', 'Administração'] as const

type Category = (typeof CATEGORY_ORDER)[number]

const CODE_TO_CATEGORY: Record<string, Category> = {
  'attendances.read': 'Operação',
  'attendances.create': 'Operação',
  'attendances.update': 'Operação',
  'attendances.cancel': 'Operação',
  'attendances.override_price': 'Operação',
  'attendances.view_prices': 'Operação',
  'pricing.read': 'Operação',
  'clinics.read': 'Cadastros',
  'clinics.manage': 'Cadastros',
  'veterinarians.read': 'Cadastros',
  'veterinarians.manage': 'Cadastros',
  'owners.read': 'Cadastros',
  'owners.manage': 'Cadastros',
  'patients.read': 'Cadastros',
  'patients.manage': 'Cadastros',
  'catalog.read': 'Cadastros',
  'catalog.manage': 'Cadastros',
  'pricing.manage': 'Financeiro',
  'closures.read': 'Financeiro',
  'closures.preview': 'Financeiro',
  'closures.close': 'Financeiro',
  'closures.adjust': 'Financeiro',
  'closures.reopen': 'Financeiro',
  'users.read': 'Administração',
  'users.create': 'Administração',
  'users.update': 'Administração',
  'users.deactivate': 'Administração',
  'users.activate': 'Administração',
  'roles.read': 'Administração',
  'roles.assign': 'Administração',
  'roles.manage': 'Administração',
  'permissions.read': 'Administração',
  'audit.read': 'Administração',
  'imports.execute': 'Administração',
}

export interface PermissionGroup {
  category: Category
  label: Category
  permissions: Permission[]
}

function categoryOf(code: string): Category {
  const category = CODE_TO_CATEGORY[code]
  if (!category) {
    throw new Error(
      `Permissão "${code}" não está mapeada em nenhuma categoria (permission-groups.ts) — ` +
        'atualize CODE_TO_CATEGORY antes de exibi-la na tela de perfis.',
    )
  }
  return category
}

export function groupPermissionsByCategory(permissions: Permission[]): PermissionGroup[] {
  const byCategory = new Map<Category, Permission[]>()
  for (const permission of permissions) {
    const category = categoryOf(permission.code)
    const group = byCategory.get(category)
    if (group) {
      group.push(permission)
    } else {
      byCategory.set(category, [permission])
    }
  }
  return CATEGORY_ORDER.filter((category) => byCategory.has(category)).map((category) => ({
    category,
    label: category,
    permissions: byCategory.get(category) as Permission[],
  }))
}
