import { useQueryClient } from '@tanstack/react-query'

import { BlockFooter } from '../../../shared/ui/detail-block'
import { examQueryKey } from '../api/use-exam-query'

interface ExamDetailFooterProps {
  examId: string
  reason: string
  onReasonChange: (value: string) => void
  canSave: boolean
  isPending: boolean
  error: unknown
  onSave: () => void
  onCancel: () => void
}

/** Rodapé dos blocos do exame: motivo obrigatório + Salvar/Cancelar do `BlockFooter`. */
export function ExamDetailFooter({ examId, ...footer }: ExamDetailFooterProps) {
  const queryClient = useQueryClient()
  return (
    <BlockFooter
      {...footer}
      reasonLabel="Motivo da alteração"
      reasonRequired
      reloadLabel="Recarregar exame"
      onReload={() => void queryClient.invalidateQueries({ queryKey: examQueryKey(examId) })}
    />
  )
}
