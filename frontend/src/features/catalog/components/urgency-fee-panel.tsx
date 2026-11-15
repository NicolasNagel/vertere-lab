import { useState } from 'react'

import { formatCurrencyBRL } from '../../../shared/lib/formatters'
import { KebabMenu } from '../../../shared/ui/kebab-menu'
import { CalendarIcon, ClockIcon } from '../../../shared/ui/icons'
import { TextField } from '../../../shared/ui/text-field'
import { useAuth } from '../../auth/auth-context'
import type { UrgencyFeeSetting } from '../../attendances/api/urgency-fee-api'
import {
  URGENCY_FEE_QUERY_KEY,
  useUpdateUrgencyFeeMutation,
  useUrgencyFeeQuery,
} from '../../attendances/api/use-urgency-fee-query'
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

function EditForm({ setting, onClose }: { setting: UrgencyFeeSetting; onClose: () => void }) {
  const mutation = useUpdateUrgencyFeeMutation()
  const [amount, setAmount] = useState(setting.feeAmount)
  const [schedule, setSchedule] = useState(setting.schedule)
  const [reason, setReason] = useState('')
  const normalized = normalizeMoney(amount)
  const changed = normalized !== setting.feeAmount || !sameSchedule(schedule, setting.schedule)
  const invalid = normalized === null || scheduleError(schedule) !== undefined

  return (
    <FeeDialog
      titleId="urgency-fee-dialog"
      title="Editar taxa de urgência"
      subtitle="Valor fixo por atendimento urgente"
      canSave={!invalid && changed}
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
            schedule,
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
      </div>
      {setting.scheduleLabel &&
        setting.schedule.weekdays.length === 0 &&
        !setting.schedule.startTime && (
          <p className="fees__note">
            Texto anterior: {setting.scheduleLabel}. Ao salvar, ele é substituído pelos campos
            abaixo.
          </p>
        )}
      <FeeScheduleFields idPrefix="urgency-fee" value={schedule} onChange={setSchedule} />
    </FeeDialog>
  )
}

/** Cadastro da taxa de urgência: um valor fixo, somado quando o atendimento é marcado urgente. */
export function UrgencyFeePanel() {
  const { user } = useAuth()
  const canRead = user?.permissions.includes('pricing.read') ?? false
  const canManage = user?.permissions.includes('pricing.manage') ?? false
  const query = useUrgencyFeeQuery(canRead)
  const [selected, setSelected] = useState(false)
  const [editing, setEditing] = useState(false)

  if (!canRead) {
    return <p className="attendance-list-page__hint">Você não tem permissão para ver as taxas.</p>
  }
  if (query.isLoading) return <p className="attendance-list-page__hint">Carregando…</p>
  if (query.isError || !query.data) {
    return (
      <p role="alert" className="attendance-list-page__error">
        Não foi possível carregar a taxa de urgência. Tente novamente.
      </p>
    )
  }
  const setting = query.data

  return (
    <>
      <p className="attendance-list-page__hint">
        Cobrada uma vez em todo atendimento marcado como urgente. Soma-se ao plantão e às taxas da
        clínica.
      </p>
      <div className="attendance-list-table">
        <table className="attendance-list-table__table exam-table__table">
          <thead>
            <tr>
              <th scope="col">Taxa</th>
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
            <tr
              data-selectable
              data-selected={selected || undefined}
              onClick={() => setSelected(true)}
            >
              <td>
                <button
                  type="button"
                  className="exam-table__name-link"
                  onClick={(event) => {
                    event.stopPropagation()
                    setSelected(true)
                  }}
                >
                  Urgência
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
                    label="Ações para Urgência"
                    items={[{ label: 'Editar taxa', onSelect: () => setEditing(true) }]}
                  />
                )}
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      {selected && (
        <FeeRowPopover
          titleId="urgency-fee-popover-title"
          title="Taxa de urgência"
          sub="Valor fixo por atendimento urgente"
          canManage={canManage}
          editLabel="Editar taxa"
          fields={[
            { label: 'Valor', value: formatCurrencyBRL(setting.feeAmount) },
            { label: 'Dias', value: <ScheduleDays setting={setting} /> },
            { label: 'Horário', value: hoursLabel(setting.schedule) || '—' },
          ]}
          onEdit={() => {
            setEditing(true)
            setSelected(false)
          }}
          onClose={() => setSelected(false)}
        />
      )}
      {editing && <EditForm setting={setting} onClose={() => setEditing(false)} />}
    </>
  )
}
