import { useState } from 'react'

import { formatCurrencyBRL, formatDate } from '../../../shared/lib/formatters'
import { Badge } from '../../../shared/ui/badge'
import { Checkbox } from '../../../shared/ui/checkbox'
import { KebabMenu, type KebabMenuItem } from '../../../shared/ui/kebab-menu'
import { Dropdown } from '../../../shared/ui/dropdown'
import { TextField } from '../../../shared/ui/text-field'
import { useAuth } from '../../auth/auth-context'
import type { ClinicFeeRule, FeeAttendanceType } from '../../attendances/api/clinic-fee-rules-api'
import {
  useClinicFeeRulesQuery,
  useCreateClinicFeeRuleMutation,
  useUpdateClinicFeeRuleMutation,
} from '../../attendances/api/use-clinic-fee-rules'
import { useAllClinicsQuery } from '../../clinics/api/use-clinics-query'
import { useExamsQuery } from '../api/use-exams-query'
import { FeeConditionFields } from './fee-condition-fields'
import { FeeDialog } from './fee-dialog'
import { FeeRowPopover } from './fee-row-popover'
import { conditionsSummary } from '../lib/fee-conditions'
import { normalizeMoney } from '../lib/normalize-money'
import '../../attendances/components/attendance-list-table.css'
import '../../attendances/components/attendance-list-page.css'
import './exam-table.css'
import './fees.css'

const RULES_KEY = ['clinic-fee-rules'] as const

interface RuleFormProps {
  /** `null` = nova taxa. */
  rule: ClinicFeeRule | null
  clinics: { value: string; label: string }[]
  exams: { value: string; label: string }[]
  /** Abre a edição já com "Taxa ativa" desmarcada (atalho do menu "Inativar taxa"). */
  startInactive?: boolean
  onClose: () => void
}

function RuleForm({ rule, clinics, exams, startInactive = false, onClose }: RuleFormProps) {
  const createMutation = useCreateClinicFeeRuleMutation()
  const updateMutation = useUpdateClinicFeeRuleMutation()
  const mutation = rule ? updateMutation : createMutation
  const [clinicId, setClinicId] = useState(rule?.clinicId ?? '')
  const [name, setName] = useState(rule?.name ?? '')
  const [amount, setAmount] = useState(rule?.feeAmount ?? '')
  const [validFrom, setValidFrom] = useState(rule?.validFrom ?? '')
  const [validTo, setValidTo] = useState(rule?.validTo ?? '')
  const [examIds, setExamIds] = useState<string[]>(rule?.examIds ?? [])
  const [attendanceTypes, setAttendanceTypes] = useState<FeeAttendanceType[]>(
    rule?.attendanceTypes ?? [],
  )
  const [isActive, setIsActive] = useState(startInactive ? false : (rule?.isActive ?? true))
  const [reason, setReason] = useState('')
  // Uma chave por diálogo aberto: clique duplo ou reenvio após falha de rede não cria duas taxas.
  const [idempotencyKey] = useState(() => crypto.randomUUID())

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
    isActive !== rule.isActive ||
    !sameSet(examIds, rule.examIds) ||
    !sameSet(attendanceTypes, rule.attendanceTypes)

  function save() {
    if (!normalized) return
    const values = {
      name: name.trim(),
      feeAmount: normalized,
      validFrom,
      validTo: validTo || null,
      examIds,
      attendanceTypes,
      reason: reason.trim(),
    }
    if (rule) {
      updateMutation.mutate(
        {
          id: rule.id,
          input: { ...values, isActive, expectedRowVersion: rule.rowVersion },
        },
        { onSuccess: onClose },
      )
    } else {
      createMutation.mutate({ ...values, clinicId, idempotencyKey }, { onSuccess: onClose })
    }
  }

  return (
    <FeeDialog
      titleId="clinic-fee-dialog"
      title={rule ? 'Editar taxa da clínica' : 'Nova taxa da clínica'}
      subtitle="Valor fixo somado ao atendimento quando as condições forem atendidas"
      canSave={valid && changed}
      isPending={mutation.isPending}
      error={mutation.error}
      reason={reason}
      onReasonChange={setReason}
      reloadKey={RULES_KEY}
      onClose={onClose}
      onSave={save}
    >
      <Dropdown
        variant="field"
        label="Clínica"
        placeholder="Selecione a clínica"
        options={clinics}
        searchable
        disabled={rule !== null}
        value={clinicId}
        onChange={setClinicId}
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
      <FeeConditionFields
        idPrefix="clinic-fee"
        exams={exams}
        examIds={examIds}
        attendanceTypes={attendanceTypes}
        onExamIdsChange={setExamIds}
        onAttendanceTypesChange={setAttendanceTypes}
      />
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

function sameSet(left: string[], right: string[]): boolean {
  return left.length === right.length && left.every((item) => right.includes(item))
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

interface ClinicFeeRulesPanelProps {
  /** Filtro de clínica e botão "Nova taxa" ficam no cabeçalho da tela, como na Operação. */
  clinicFilter: string
  creating: boolean
  onCreatingChange: (value: boolean) => void
}

/** Cadastro das taxas fixas por clínica; somam ao total do atendimento enquanto vigentes. */
export function ClinicFeeRulesPanel({
  clinicFilter,
  creating,
  onCreatingChange,
}: ClinicFeeRulesPanelProps) {
  const { user } = useAuth()
  const canRead = user?.permissions.includes('pricing.read') ?? false
  const canManage = user?.permissions.includes('pricing.manage') ?? false
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [editing, setEditing] = useState<{
    rule: ClinicFeeRule
    inactivate: boolean
  } | null>(null)
  const rulesQuery = useClinicFeeRulesQuery(clinicFilter || undefined)
  const clinicsQuery = useAllClinicsQuery({ status: 'ACTIVE' })
  const clinicOptions = (clinicsQuery.data?.items ?? []).map((clinic) => ({
    value: clinic.id,
    label: clinic.name,
  }))
  const clinicName = new Map(clinicOptions.map((option) => [option.value, option.label]))
  const examsQuery = useExamsQuery({ pageSize: 100 })
  const examOptions = (examsQuery.data?.items ?? []).map((exam) => ({
    value: exam.id,
    label: exam.name,
  }))
  const examName = new Map(examOptions.map((option) => [option.value, option.label]))

  if (!canRead) {
    return <p className="attendance-list-page__hint">Você não tem permissão para ver as taxas.</p>
  }
  const rules = rulesQuery.data ?? []
  const selected = rules.find((rule) => rule.id === selectedId) ?? null

  return (
    <>
      {rulesQuery.isLoading && <p className="attendance-list-page__hint">Carregando…</p>}
      {rulesQuery.isError && (
        <p role="alert" className="attendance-list-page__error">
          Não foi possível carregar as taxas das clínicas. Tente novamente.
        </p>
      )}
      {rulesQuery.data && rules.length === 0 && (
        <p className="attendance-list-page__hint">
          Nenhuma taxa cadastrada para as clínicas selecionadas.
        </p>
      )}
      {rules.length > 0 && (
        <div className="attendance-list-table">
          <table className="attendance-list-table__table exam-table__table">
            <thead>
              <tr>
                <th scope="col">Clínica</th>
                <th scope="col">Taxa</th>
                <th scope="col">Condições</th>
                <th scope="col">Vigência</th>
                <th scope="col" className="attendance-list-table__num">
                  Valor
                </th>
                <th scope="col">Status</th>
                <th scope="col" className="exam-table__actions-header">
                  Ações
                </th>
              </tr>
            </thead>
            <tbody>
              {rules.map((rule) => (
                <tr
                  key={rule.id}
                  data-selectable
                  data-selected={rule.id === selectedId || undefined}
                  data-inactive={!rule.isActive || undefined}
                  onClick={() => setSelectedId(rule.id)}
                >
                  <td>{clinicName.get(rule.clinicId) ?? '—'}</td>
                  <td>
                    <button
                      type="button"
                      className="exam-table__name-link"
                      onClick={(event) => {
                        event.stopPropagation()
                        setSelectedId(rule.id)
                      }}
                    >
                      {rule.name}
                    </button>
                  </td>
                  <td className="exam-table__muted fees__wrap">{conditionsSummary(rule, examName)}</td>
                  <td className="exam-table__muted fees__wrap">{validity(rule)}</td>
                  <td className="attendance-list-table__num attendance-list-table__value">
                    {formatCurrencyBRL(rule.feeAmount)}
                  </td>
                  <td>
                    <Badge tone={ruleStatus(rule) === 'Ativa' ? 'success' : 'neutral'}>
                      {ruleStatus(rule)}
                    </Badge>
                  </td>
                  <td className="exam-table__actions" onClick={(event) => event.stopPropagation()}>
                    {canManage && (
                      <KebabMenu
                        label={`Ações para ${rule.name}`}
                        items={ruleMenu(rule, setEditing)}
                      />
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {selected && (
        <FeeRowPopover
          titleId="clinic-fee-popover-title"
          title={selected.name}
          badge={
            <Badge tone={ruleStatus(selected) === 'Ativa' ? 'success' : 'neutral'}>
              {ruleStatus(selected)}
            </Badge>
          }
          sub={clinicName.get(selected.clinicId) ?? undefined}
          canManage={canManage}
          editLabel="Editar taxa"
          menuItems={ruleMenu(selected, (value) => {
            setEditing(value)
            setSelectedId(null)
          }).filter((item) => item.destructive)}
          fields={[
            { label: 'Valor', value: formatCurrencyBRL(selected.feeAmount) },
            {
              label: 'Condições',
              value: conditionsSummary(selected, examName),
            },
            { label: 'Vigência', value: validity(selected) },
          ]}
          onEdit={() => {
            setEditing({ rule: selected, inactivate: false })
            setSelectedId(null)
          }}
          onClose={() => setSelectedId(null)}
        />
      )}
      {creating && (
        <RuleForm
          rule={null}
          clinics={clinicOptions}
          exams={examOptions}
          onClose={() => onCreatingChange(false)}
        />
      )}
      {editing && (
        <RuleForm
          rule={editing.rule}
          clinics={clinicOptions}
          exams={examOptions}
          startInactive={editing.inactivate}
          onClose={() => setEditing(null)}
        />
      )}
    </>
  )
}

function ruleMenu(
  rule: ClinicFeeRule,
  open: (value: { rule: ClinicFeeRule; inactivate: boolean }) => void,
): KebabMenuItem[] {
  const items: KebabMenuItem[] = [
    { label: 'Editar taxa', onSelect: () => open({ rule, inactivate: false }) },
  ]
  if (rule.isActive) {
    items.push({
      label: 'Inativar taxa',
      onSelect: () => open({ rule, inactivate: true }),
      destructive: true,
    })
  }
  return items
}
