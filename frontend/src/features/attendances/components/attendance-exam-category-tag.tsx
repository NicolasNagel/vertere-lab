import { useExamCategoryQuery } from '../../catalog/api/use-exam-category-query'
import { useExamQuery } from '../../catalog/api/use-exam-query'
import './attendance-exam-category-tag.css'

interface AttendanceExamCategoryTagProps {
  examId: string
}

/** `AttendanceExamItem` só carrega `examId`/`examCode`/`examName` (snapshot
 * financeiro) — a categoria não faz parte do snapshot, então é resolvida a
 * partir do catálogo atual (`useExamQuery` → `categoryId` →
 * `useExamCategoryQuery`), igual ao padrão já usado em `exam-table.tsx`.
 * Se o exame ou a categoria não puder ser resolvido (catálogo mudou desde
 * então), não mostra nada em vez de uma tag vazia/errada. */
export function AttendanceExamCategoryTag({ examId }: AttendanceExamCategoryTagProps) {
  const examQuery = useExamQuery(examId)
  const categoryQuery = useExamCategoryQuery(examQuery.data?.categoryId ?? null)

  if (!categoryQuery.data) return null

  return <span className="attendance-exam-category-tag">{categoryQuery.data.name}</span>
}
