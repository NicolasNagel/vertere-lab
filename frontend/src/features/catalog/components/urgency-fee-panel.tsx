import { useState } from 'react'

import { formatCurrencyBRL } from '../../../shared/lib/formatters'
import { Button } from '../../../shared/ui/button'
import { TextField } from '../../../shared/ui/text-field'
import { useAuth } from '../../auth/auth-context'
import type { UrgencyFeeSetting } from '../../attendances/api/urgency-fee-api'
import {
  URGENCY_FEE_QUERY_KEY,
  useUpdateUrgencyFeeMutation,
  useUrgencyFeeQuery,
} from '../../attendances/api/use-urgency-fee-query'
import { FeeDialog } from './fee-dialog'
import { normalizeMoney } from '../lib/normalize-money'
import './exam-table.css'
import './fees.css'

function EditForm({ setting, onClose }: { setting: UrgencyFeeSetting; onClose: () => void }) {
  const mutation = useUpdateUrgencyFeeMutation()
  const [amount, setAmount] = useState(setting.feeAmount)
  const [schedule, setSchedule] = useState(setting.scheduleLabel)
  const [reason, setReason] = useState('')
  const normalized = normalizeMoney(amount)
  const changed = normalized !== setting.feeAmount || schedule.trim() !== setting.scheduleLabel

  return (
    <FeeDialog
      titleId="urgency-fee-dialog"
      title="Editar taxa de urgência"
      subtitle="Valor fixo por atendimento urgente"
      canSave={normalized !== null && changed}
      isPending={mutation.isPending}
      error={mutation.error}
      reason={reason}
      onReasonChange={setReason}
      reloadKey={URGENCY_FEE_QUERY_KEY}
      onClose={onClose}
      onSave={() =>
        normalized &&
        mutation.mutate(
          {
            feeAmount: normalized,
            scheduleLabel: schedule.trim(),
            reason: reason.trim(),
            expectedRowVersion: setting.rowVersion,
          },
          { onSuccess: onClose },
        )
      }
    >
      <div className="fees__row">
        <TextField
          id="urgency-fee-amount"
          label="Valor da taxa (R$)"
          inputMode="decimal"
          value={amount}
          errorMessage={normalized === null ? 'Informe um valor, ex.: 30,00' : undefined}
          onChange={(event) => setAmount(event.target.value)}
        />
        <TextField
          id="urgency-fee-schedule"
          label="Quando se aplica (informativo)"
          placeholder="Ex.: Pedido fora da rotina de coleta"
          value={schedule}
          onChange={(event) => setSchedule(event.target.value)}
        />
      </div>
    </FeeDialog>
  )
}

/** Cadastro da taxa de urgência: um valor fixo, somado quando o atendimento é marcado urgente. */
export function UrgencyFeePanel() {
  const { user } = useAuth()
  const canRead = user?.permissions.includes('pricing.read') ?? false
  const canManage = user?.permissions.includes('pricing.manage') ?? false
  const query = useUrgencyFeeQuery(canRead)
  const [editing, setEditing] = useState(false)

  if (!canRead) return <p className="fees__hint">Você não tem permissão para ver as taxas.</p>
  if (query.isLoading) return <p className="fees__hint">Carregando…</p>
  if (query.isError || !query.data) {
    return (
      <p role="alert" className="fees__hint fees__hint--error">
        Não foi possível carregar a taxa de urgência. Tente novamente.
      </p>
    )
  }
  const setting = query.data

  return (
    <>
      <p className="fees__intro">
        Cobrada uma vez em todo atendimento marcado como urgente. Soma-se ao plantão e às taxas da
        clínica.
      </p>
      <div className="exam-table">
        <table className="exam-table__table">
          <thead>
            <tr>
              <th scope="col">Taxa</th>
              <th scope="col">Quando se aplica (informativo)</th>
              <th scope="col" className="exam-table__num">
                Valor
              </th>
              <th scope="col" className="exam-table__actions-header">
                Ações
              </th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td>
                <b>Urgência</b>
              </td>
              <td className="exam-table__muted">{setting.scheduleLabel || '—'}</td>
              <td className="exam-table__num exam-table__price">
                {formatCurrencyBRL(setting.feeAmount)}
              </td>
              <td className="exam-table__actions">
                {canManage && (
                  <Button
                    type="button"
                    variant="secondary"
                    size="sm"
                    aria-label="Editar taxa de urgência"
                    onClick={() => setEditing(true)}
                  >
                    Editar
                  </Button>
                )}
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      {editing && <EditForm setting={setting} onClose={() => setEditing(false)} />}
    </>
  )
}
