import { useState } from 'react'

import { formatCurrencyBRL } from '../../../shared/lib/formatters'
import { KebabMenu } from '../../../shared/ui/kebab-menu'
import { CalendarIcon, ClockIcon } from '../../../shared/ui/icons'
import { TextField } from '../../../shared/ui/text-field'
import { useAuth } from '../../auth/auth-context'
import type {
  OnCallFeeSetting,
  OnCallServiceLevel,
} from '../../attendances/api/on-call-fee-settings-api'
import { useOnCallFeeSettingsQuery } from '../../attendances/api/use-on-call-fee-settings-query'
import { useUpdateOnCallFeeSettingMutation } from '../../attendances/api/use-update-on-call-fee-setting-mutation'
import { FeeDialog } from './fee-dialog'
import { FeeRowPopover } from './fee-row-popover'
import { FeeScheduleFields } from './fee-schedule-fields'
import { ScheduleDays } from './schedule-days'
import { hoursLabel, sameSchedule, scheduleError } from '../lib/fee-schedule'
import { normalizeMoney } from '../lib/normalize-money'
import '../../attendances/components/attendance-list-table.css'
import '../../attendances/components/attendance-list-page.css'
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
  const [schedule, setSchedule] = useState(setting.schedule)
  const [reason, setReason] = useState('')
  const normalized = normalizeMoney(amount)
  const changed = normalized !== setting.feeAmount || !sameSchedule(schedule, setting.schedule)
  const invalid = normalized === null || scheduleError(schedule) !== undefined

  return (
    <FeeDialog
      titleId="on-call-fee-dialog"
      title={`Editar ${TIER_LABELS[setting.serviceLevel].toLowerCase()}`}
      subtitle="Valor fixo por atendimento"
      canSave={!invalid && changed}
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
              schedule,
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
      </div>
      {setting.scheduleLabel &&
        setting.schedule.weekdays.length === 0 &&
        !setting.schedule.startTime && (
          <p className="fees__note">
            Texto anterior: {setting.scheduleLabel}. Ao salvar, ele é substituído pelos campos
            abaixo.
          </p>
        )}
      <FeeScheduleFields idPrefix="on-call-fee" value={schedule} onChange={setSchedule} />
    </FeeDialog>
  )
}

/** Cadastro das taxas de plantão: uma linha por tipo; clicar abre o resumo, editar sempre possível com motivo. */
export function OnCallFeeSettingsPanel() {
  const { user } = useAuth()
  const canRead = user?.permissions.includes('pricing.read') ?? false
  const canManage = user?.permissions.includes('pricing.manage') ?? false
  const query = useOnCallFeeSettingsQuery(canRead)
  const [selectedLevel, setSelectedLevel] = useState<OnCallServiceLevel | null>(null)
  const [editing, setEditing] = useState<OnCallFeeSetting | null>(null)

  if (!canRead) {
    return <p className="attendance-list-page__hint">Você não tem permissão para ver as taxas.</p>
  }
  if (query.isLoading) return <p className="attendance-list-page__hint">Carregando…</p>
  if (query.isError) {
    return (
      <p role="alert" className="attendance-list-page__error">
        Não foi possível carregar as taxas de plantão. Tente novamente.
      </p>
    )
  }
  const selected = (query.data ?? []).find((setting) => setting.serviceLevel === selectedLevel)

  return (
    <>
      <p className="attendance-list-page__hint">
        Cobrada uma vez por atendimento de plantão. Dias e horário são só informativos: o tipo do
        atendimento é escolhido na hora do registro.
      </p>
      <div className="attendance-list-table">
        <table className="attendance-list-table__table exam-table__table">
          <thead>
            <tr>
              <th scope="col">Tipo</th>
              <th scope="col">
                <span className="fees__th-icon">
                  <CalendarIcon /> Dias
                </span>
              </th>
              <th scope="col">
                <span className="fees__th-icon">
                  <ClockIcon /> Horário
                </span>
              </th>
              <th scope="col" className="attendance-list-table__num">
                Valor
              </th>
              <th scope="col" className="exam-table__actions-header">
                Ações
              </th>
            </tr>
          </thead>
          <tbody>
            {(query.data ?? []).map((setting) => (
              <tr
                key={setting.id}
                data-selectable
                data-selected={setting.serviceLevel === selectedLevel || undefined}
                onClick={() => setSelectedLevel(setting.serviceLevel)}
              >
                <td>
                  <button
                    type="button"
                    className="exam-table__name-link"
                    onClick={(event) => {
                      event.stopPropagation()
                      setSelectedLevel(setting.serviceLevel)
                    }}
                  >
                    {TIER_LABELS[setting.serviceLevel]}
                  </button>
                </td>
                <td className="exam-table__muted">
                  <ScheduleDays setting={setting} />
                </td>
                <td className="exam-table__muted">{hoursLabel(setting.schedule) || '—'}</td>
                <td className="attendance-list-table__num attendance-list-table__value">
                  {formatCurrencyBRL(setting.feeAmount)}
                </td>
                <td className="exam-table__actions" onClick={(event) => event.stopPropagation()}>
                  {canManage && (
                    <KebabMenu
                      label={`Ações para ${TIER_LABELS[setting.serviceLevel]}`}
                      items={[
                        {
                          label: 'Editar taxa',
                          onSelect: () => setEditing(setting),
                        },
                      ]}
                    />
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {selected && (
        <FeeRowPopover
          titleId="on-call-fee-popover-title"
          title={TIER_LABELS[selected.serviceLevel]}
          sub="Valor fixo por atendimento"
          canManage={canManage}
          editLabel="Editar taxa"
          fields={[
            { label: 'Valor', value: formatCurrencyBRL(selected.feeAmount) },
            { label: 'Dias', value: <ScheduleDays setting={selected} /> },
            { label: 'Horário', value: hoursLabel(selected.schedule) || '—' },
          ]}
          onEdit={() => {
            setEditing(selected)
            setSelectedLevel(null)
          }}
          onClose={() => setSelectedLevel(null)}
        />
      )}
      {editing && <EditForm setting={editing} onClose={() => setEditing(null)} />}
    </>
  )
}
