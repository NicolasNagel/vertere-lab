import { useQueryClient } from '@tanstack/react-query'

import { BlockFooter } from '../../../shared/ui/detail-block'
import { attendanceQueryKey } from '../api/use-attendance-query'

interface CorrectionFooterProps {
  attendanceId: string
  reason: string
  onReasonChange: (value: string) => void
  canSave: boolean
  isPending: boolean
  error: unknown
  onSave: () => void
  onCancel: () => void
}

/** Rodapé das correções do atendimento: motivo obrigatório + Salvar/Cancelar do `BlockFooter`. */
export function CorrectionFooter({ attendanceId, ...footer }: CorrectionFooterProps) {
  const queryClient = useQueryClient()
  return (
    <BlockFooter
      {...footer}
      reasonLabel="Motivo da alteração"
      reasonRequired
      reloadLabel="Recarregar atendimento"
      onReload={() => void queryClient.invalidateQueries({ queryKey: attendanceQueryKey(attendanceId) })}
    />
  )
}
