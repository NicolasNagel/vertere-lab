import { useState } from 'react'

import { formatCurrencyBRL } from '../../../shared/lib/formatters'
import { Button } from '../../../shared/ui/button'
import { TextField } from '../../../shared/ui/text-field'
import { useAuth } from '../../auth/auth-context'
import type {
  OnCallFeeSetting,
  OnCallServiceLevel,
} from '../../attendances/api/on-call-fee-settings-api'
import { useOnCallFeeSettingsQuery } from '../../attendances/api/use-on-call-fee-settings-query'
import { useUpdateOnCallFeeSettingMutation } from '../../attendances/api/use-update-on-call-fee-setting-mutation'
import { FeeDialog } from './fee-dialog'
import { normalizeMoney } from '../lib/normalize-money'
import './exam-table.css'
import './fees.css'

const TIER_LABELS: Record<OnCallServiceLevel, string> = {
  PLANTAO_NORMAL: 'Plantão normal',
  PLANTAO_ESPECIAL: 'Plantão especial / noturno',
}

interface EditFormProps {
  setting: OnCallFeeSetting
  onClose: () => void
}

function EditForm({ setting, onClose }: EditFormProps) {
  const mutation = useUpdateOnCallFeeSettingMutation()
  const [amount, setAmount] = useState(setting.feeAmount)
  const [schedule, setSchedule] = useState(setting.scheduleLabel)
  const [reason, setReason] = useState('')
  const normalized = normalizeMoney(amount)
  const changed = normalized !== setting.feeAmount || schedule.trim() !== setting.scheduleLabel

  return (
    <FeeDialog
      titleId="on-call-fee-dialog"
      title={`Editar ${TIER_LABELS[setting.serviceLevel].toLowerCase()}`}
      subtitle="Valor fixo por atendimento"
      canSave={normalized !== null && changed}
      isPending={mutation.isPending}
      error={mutation.error}
      reason={reason}
      onReasonChange={setReason}
      reloadKey={['on-call-fee-settings']}
      onClose={onClose}
      onSave={() =>
        normalized &&
        mutation.mutate(
          {
            serviceLevel: setting.serviceLevel,
            input: {
              feeAmount: normalized,
              scheduleLabel: schedule.trim(),
              reason: reason.trim(),
              expectedRowVersion: setting.rowVersion,
            },
          },
          { onSuccess: onClose },
        )
      }
    >
      <div className="fees__row">
        <TextField
          id="on-call-fee-amount"
          label="Valor da taxa (R$)"
          inputMode="decimal"
          value={amount}
          errorMessage={normalized === null ? 'Informe um valor, ex.: 100,00' : undefined}
          onChange={(event) => setAmount(event.target.value)}
        />
        <TextField
          id="on-call-fee-schedule"
          label="Horário de aplicação (informativo)"
          placeholder="Ex.: Seg–Sáb · 19h às 07h"
          value={schedule}
          onChange={(event) => setSchedule(event.target.value)}
        />
      </div>
    </FeeDialog>
  )
}

/** Cadastro das taxas de plantão: uma linha por tipo, edição sempre possível com motivo. */
export function OnCallFeeSettingsPanel() {
  const { user } = useAuth()
  const canRead = user?.permissions.includes('pricing.read') ?? false
  const canManage = user?.permissions.includes('pricing.manage') ?? false
  const query = useOnCallFeeSettingsQuery(canRead)
  const [editing, setEditing] = useState<OnCallFeeSetting | null>(null)

  if (!canRead) {
    return <p className="fees__hint">Você não tem permissão para ver as taxas.</p>
  }
  if (query.isLoading) return <p className="fees__hint">Carregando…</p>
  if (query.isError) {
    return (
      <p role="alert" className="fees__hint fees__hint--error">
        Não foi possível carregar as taxas de plantão. Tente novamente.
      </p>
    )
  }

  return (
    <>
      <p className="fees__intro">
        Cobrada uma vez por atendimento de plantão. O horário é só informativo: o tipo do
        atendimento é escolhido na hora do registro.
      </p>
      <div className="exam-table">
        <table className="exam-table__table">
          <thead>
            <tr>
              <th scope="col">Tipo</th>
              <th scope="col">Horário (informativo)</th>
              <th scope="col" className="exam-table__num">
                Valor
              </th>
              <th scope="col" className="exam-table__actions-header">
                Ações
              </th>
            </tr>
          </thead>
          <tbody>
            {(query.data ?? []).map((setting) => (
              <tr key={setting.id}>
                <td>
                  <b>{TIER_LABELS[setting.serviceLevel]}</b>
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
                      aria-label={`Editar ${TIER_LABELS[setting.serviceLevel]}`}
                      onClick={() => setEditing(setting)}
                    >
                      Editar
                    </Button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {editing && <EditForm setting={editing} onClose={() => setEditing(null)} />}
    </>
  )
}
