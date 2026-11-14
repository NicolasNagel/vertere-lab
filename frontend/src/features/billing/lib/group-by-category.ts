/** Client-side aggregation for the "Demonstrativo analítico" panel's
 * category breakdown (Tela 15) — same non-authoritative regrouping caveat as
 * `group-by-protocol.ts`. */

import { sumMoney } from '../../../shared/lib/money'

export interface CategoryGroupableItem {
  examCategory: string | null
  totalAmount: string
}

export interface CategoryGroup {
  category: string
  count: number
  total: string
}

const UNCATEGORIZED_LABEL = 'Outros'

export function groupItemsByCategory<T extends CategoryGroupableItem>(items: T[]): CategoryGroup[] {
  const totals = new Map<string, { count: number; amounts: string[] }>()
  for (const item of items) {
    const category = item.examCategory ?? UNCATEGORIZED_LABEL
    const entry = totals.get(category) ?? { count: 0, amounts: [] }
    entry.count += 1
    entry.amounts.push(item.totalAmount)
    totals.set(category, entry)
  }
  return Array.from(totals.entries()).map(([category, { count, amounts }]) => ({
    category,
    count,
    total: sumMoney(amounts),
  }))
}
