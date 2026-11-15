import { useState } from 'react'

import { formatCurrencyBRL, formatDate } from '../../../shared/lib/formatters'
import { Badge } from '../../../shared/ui/badge'
import { Button } from '../../../shared/ui/button'
import { Checkbox } from '../../../shared/ui/checkbox'
import { Dropdown } from '../../../shared/ui/dropdown'
import { PlusIcon, TagIcon } from '../../../shared/ui/icons'
import { SelectField } from '../../../shared/ui/select'
import { TextField } from '../../../shared/ui/text-field'
import { useAuth } from '../../auth/auth-context'
import type { ClinicFeeRule } from '../../attendances/api/clinic-fee-rules-api'
import {
  useClinicFeeRulesQuery,
  useCreateClinicFeeRuleMutation,
  useUpdateClinicFeeRuleMutation,
} from '../../attendances/api/use-clinic-fee-rules'
import { useAllClinicsQuery } from '../../clinics/api/use-clinics-query'
import { FeeDialog } from './fee-dialog'
import { normalizeMoney } from '../lib/normalize-money'
import './exam-table.css'
import './fees.css'

const RULES_KEY = ['clinic-fee-rules'] as const

interface RuleFormProps {
  /** `null` = nova taxa. */
  rule: ClinicFeeRule | null
  clinics: { value: string; label: string }[]
  onClose: () => void
}

function RuleForm({ rule, clinics, onClose }: RuleFormProps) {
  const createMutation = useCreateClinicFeeRuleMutation()
  const updateMutation = useUpdateClinicFeeRuleMutation()
  const mutation = rule ? updateMutation : createMutation
  const [clinicId, setClinicId] = useState(rule?.clinicId ?? '')
  const [name, setName] = useState(rule?.name ?? '')
  const [amount, setAmount] = useState(rule?.feeAmount ?? '')
  const [validFrom, setValidFrom] = useState(rule?.validFrom ?? '')
  const [validTo, setValidTo] = useState(rule?.validTo ?? '')
  const [isActive, setIsActive] = useState(rule?.isActive ?? true)
  const [reason, setReason] = useState('')

  const normalized = normalizeMoney(amount)
  const rangeError = validTo !== '' && validFrom !== '' && validTo < validFrom
  const valid =
    clinicId !== '' && name.trim() !== '' && normalized !== null && validFrom !== '' && !rangeError
  const changed =
    !rule ||
    name.trim() !== rule.name ||
    normalized !== rule.feeAmount ||
    validFrom !== rule.validFrom ||
    (validTo || null) !== rule.validTo ||
    isActive !== rule.isActive

  function save() {
    if (!normalized) return
    const values = {
      name: name.trim(),
      feeAmount: normalized,
      validFrom,
      validTo: validTo || null,
      reason: reason.trim(),
    }
    if (rule) {
      updateMutation.mutate(
        { id: rule.id, input: { ...values, isActive, expectedRowVersion: rule.rowVersion } },
        { onSuccess: onClose },
      )
    } else {
      createMutation.mutate({ ...values, clinicId }, { onSuccess: onClose })
    }
  }

  return (
    <FeeDialog
      titleId="clinic-fee-dialog"
      title={rule ? 'Editar taxa da clínica' : 'Nova taxa da clínica'}
      subtitle="Valor fixo somado ao total de cada atendimento da clínica"
      canSave={valid && changed}
      isPending={mutation.isPending}
      error={mutation.error}
      reason={reason}
      onReasonChange={setReason}
      reloadKey={RULES_KEY}
      onClose={onClose}
      onSave={save}
    >
      <SelectField
        id="clinic-fee-clinic"
        label="Clínica"
        disabled={rule !== null}
        value={clinicId}
        options={[{ value: '', label: 'Selecione…' }, ...clinics]}
        onChange={(event) => setClinicId(event.target.value)}
      />
      <div className="fees__row">
        <TextField
          id="clinic-fee-name"
          label="Nome da taxa"
          maxLength={120}
          value={name}
          onChange={(event) => setName(event.target.value)}
        />
        <TextField
          id="clinic-fee-amount"
          label="Valor (R$)"
          inputMode="decimal"
          value={amount}
          errorMessage={amount && normalized === null ? 'Informe um valor, ex.: 5,00' : undefined}
          onChange={(event) => setAmount(event.target.value)}
        />
      </div>
      <div className="fees__row">
        <TextField
          id="clinic-fee-from"
          label="Vale a partir de"
          type="date"
          value={validFrom}
          onChange={(event) => setValidFrom(event.target.value)}
        />
        <TextField
          id="clinic-fee-to"
          label="Vale até (opcional)"
          type="date"
          value={validTo}
          errorMessage={rangeError ? 'O fim não pode ser antes do início.' : undefined}
          onChange={(event) => setValidTo(event.target.value)}
        />
      </div>
      {rule && (
        <Checkbox
          label="Taxa ativa"
          checked={isActive}
          onChange={(event) => setIsActive(event.target.checked)}
        />
      )}
    </FeeDialog>
  )
}

function validity(rule: ClinicFeeRule): string {
  const from = `desde ${formatDate(rule.validFrom)}`
  return rule.validTo ? `${from} até ${formatDate(rule.validTo)}` : from
}

function ruleStatus(rule: ClinicFeeRule): 'Ativa' | 'Inativa' | 'Encerrada' {
  if (!rule.isActive) return 'Inativa'
  const today = new Date().toISOString().slice(0, 10)
  return rule.validTo && rule.validTo < today ? 'Encerrada' : 'Ativa'
}

/** Cadastro das taxas fixas por clínica; somam ao total do atendimento enquanto vigentes. */
export function ClinicFeeRulesPanel() {
  const { user } = useAuth()
  const canRead = user?.permissions.includes('pricing.read') ?? false
  const canManage = user?.permissions.includes('pricing.manage') ?? false
  const [clinicFilter, setClinicFilter] = useState('')
  const [dialog, setDialog] = useState<{ rule: ClinicFeeRule | null } | null>(null)
  const rulesQuery = useClinicFeeRulesQuery(clinicFilter || undefined)
  const clinicsQuery = useAllClinicsQuery({ status: 'ACTIVE' })
  const clinicOptions = (clinicsQuery.data?.items ?? []).map((clinic) => ({
    value: clinic.id,
    label: clinic.name,
  }))
  const clinicName = new Map(clinicOptions.map((option) => [option.value, option.label]))

  if (!canRead) return <p className="fees__hint">Você não tem permissão para ver as taxas.</p>

  return (
    <>
      <div className="fees__toolbar">
        <Dropdown
          label="Clínica"
          icon={<TagIcon />}
          options={[{ value: '', label: 'Todas' }, ...clinicOptions]}
          value={clinicFilter}
          onChange={setClinicFilter}
        />
        <span className="fees__toolbar-spacer" />
        {canManage && (
          <Button
            type="button"
            variant="primary"
            className="fees__new"
            onClick={() => setDialog({ rule: null })}
          >
            <PlusIcon /> Nova taxa
          </Button>
        )}
      </div>
      {rulesQuery.isLoading && <p className="fees__hint">Carregando…</p>}
      {rulesQuery.isError && (
        <p role="alert" className="fees__hint fees__hint--error">
          Não foi possível carregar as taxas das clínicas. Tente novamente.
        </p>
      )}
      {rulesQuery.data && rulesQuery.data.length === 0 && (
        <p className="fees__hint">Nenhuma taxa cadastrada para as clínicas selecionadas.</p>
      )}
      {rulesQuery.data && rulesQuery.data.length > 0 && (
        <div className="exam-table">
          <table className="exam-table__table">
            <thead>
              <tr>
                <th scope="col">Clínica</th>
                <th scope="col">Taxa</th>
                <th scope="col">Vigência</th>
                <th scope="col" className="exam-table__num">
                  Valor
                </th>
                <th scope="col">Status</th>
                <th scope="col" className="exam-table__actions-header">
                  Ações
                </th>
              </tr>
            </thead>
            <tbody>
              {rulesQuery.data.map((rule) => (
                <tr key={rule.id} data-inactive={!rule.isActive || undefined}>
                  <td>{clinicName.get(rule.clinicId) ?? '—'}</td>
                  <td>
                    <b>{rule.name}</b>
                  </td>
                  <td className="exam-table__muted">{validity(rule)}</td>
                  <td className="exam-table__num exam-table__price">
                    {formatCurrencyBRL(rule.feeAmount)}
                  </td>
                  <td>
                    <Badge tone={ruleStatus(rule) === 'Ativa' ? 'success' : 'neutral'}>
                      {ruleStatus(rule)}
                    </Badge>
                  </td>
                  <td className="exam-table__actions">
                    {canManage && (
                      <Button
                        type="button"
                        variant="secondary"
                        size="sm"
                        aria-label={`Editar ${rule.name}`}
                        onClick={() => setDialog({ rule })}
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
      )}
      {dialog && (
        <RuleForm rule={dialog.rule} clinics={clinicOptions} onClose={() => setDialog(null)} />
      )}
    </>
  )
}
