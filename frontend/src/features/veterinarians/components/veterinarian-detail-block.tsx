import { useQueryClient } from '@tanstack/react-query'

import { BlockFooter } from '../../../shared/ui/detail-block'
import { veterinarianQueryKey } from '../api/use-veterinarian-query'

interface VeterinarianDetailFooterProps {
  veterinarianId: string
  reason: string
  onReasonChange: (value: string) => void
  canSave: boolean
  isPending: boolean
  error: unknown
  onSave: () => void
  onCancel: () => void
}

/** Rodapé dos blocos do veterinário: motivo obrigatório + Salvar/Cancelar do `BlockFooter`. */
export function VeterinarianDetailFooter({ veterinarianId, ...footer }: VeterinarianDetailFooterProps) {
  const queryClient = useQueryClient()
  return (
    <BlockFooter
      {...footer}
      reasonLabel="Motivo da alteração"
      reasonRequired
      reloadLabel="Recarregar veterinário"
      onReload={() => void queryClient.invalidateQueries({ queryKey: veterinarianQueryKey(veterinarianId) })}
    />
  )
}
