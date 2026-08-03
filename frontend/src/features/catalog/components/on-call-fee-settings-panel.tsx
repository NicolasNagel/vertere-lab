import { useEffect, useState } from 'react'

import { ApiError } from '../../../shared/api/errors'
import { useAuth } from '../../auth/auth-context'
import type {
  OnCallFeeSetting,
  OnCallServiceLevel,
} from '../../attendances/api/on-call-fee-settings-api'
import { useOnCallFeeSettingsQuery } from '../../attendances/api/use-on-call-fee-settings-query'
import { useUpdateOnCallFeeSettingMutation } from '../../attendances/api/use-update-on-call-fee-setting-mutation'
import './on-call-fee-settings-panel.css'

interface TierDraft {
  feeAmount: string
  scheduleLabel: string
}

const TIER_ORDER: OnCallServiceLevel[] = ['PLANTAO_NORMAL', 'PLANTAO_ESPECIAL']

const TIER_LABELS: Record<OnCallServiceLevel, string> = {
  PLANTAO_NORMAL: 'Plantão normal',
  PLANTAO_ESPECIAL: 'Plantão especial / noturno',
}

function draftOf(setting: OnCallFeeSetting): TierDraft {
  return { feeAmount: setting.feeAmount, scheduleLabel: setting.scheduleLabel }
}

function describeError(error: unknown): string {
  if (error instanceof ApiError) return error.message
  return 'Falha de conexão. Verifique sua internet e tente novamente.'
}

export function OnCallFeeSettingsPanel() {
  const { user } = useAuth()
  const canRead = user?.permissions.includes('pricing.read') ?? false
  const canManage = user?.permissions.includes('pricing.manage') ?? false

  const settingsQuery = useOnCallFeeSettingsQuery()
  const updateMutation = useUpdateOnCallFeeSettingMutation()

  const [drafts, setDrafts] = useState<Partial<Record<OnCallServiceLevel, TierDraft>>>({})
  const [dirty, setDirty] = useState<Partial<Record<OnCallServiceLevel, boolean>>>({})
  const [fieldErrors, setFieldErrors] = useState<Partial<Record<OnCallServiceLevel, string>>>({})
  const [saved, setSaved] = useState(false)

  const settingsByTier = new Map(
    (settingsQuery.data ?? []).map((setting) => [setting.serviceLevel, setting]),
  )

  // Only adopt fresh server data for a tier the user hasn't started editing —
  // a background refetch must never clobber an in-progress edit.
  useEffect(() => {
    if (!settingsQuery.data) return
    setDrafts((current) => {
      const next = { ...current }
      for (const setting of settingsQuery.data) {
        if (!dirty[setting.serviceLevel]) {
          next[setting.serviceLevel] = draftOf(setting)
        }
      }
      return next
    })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [settingsQuery.data])

  if (!canRead) return null
  if (settingsQuery.isLoading) return null

  function updateDraft(serviceLevel: OnCallServiceLevel, patch: Partial<TierDraft>) {
    setDrafts((current) => ({
      ...current,
      [serviceLevel]: { ...current[serviceLevel], ...patch } as TierDraft,
    }))
    setDirty((current) => ({ ...current, [serviceLevel]: true }))
    setSaved(false)
  }

  async function handleSave() {
    setFieldErrors({})
    const tiersToSave = TIER_ORDER.filter((tier) => dirty[tier])
    if (tiersToSave.length === 0) return

    const results = await Promise.allSettled(
      tiersToSave.map((serviceLevel) => {
        const setting = settingsByTier.get(serviceLevel)
        const draft = drafts[serviceLevel]
        if (!setting || !draft) return Promise.resolve()
        return updateMutation.mutateAsync({
          serviceLevel,
          input: {
            feeAmount: draft.feeAmount,
            scheduleLabel: draft.scheduleLabel,
            expectedRowVersion: setting.rowVersion,
          },
        })
      }),
    )

    const errors: Partial<Record<OnCallServiceLevel, string>> = {}
    const succeeded: OnCallServiceLevel[] = []
    results.forEach((result, index) => {
      const tier = tiersToSave[index]
      if (!tier) return
      if (result.status === 'rejected') {
        errors[tier] = describeError(result.reason)
      } else {
        succeeded.push(tier)
      }
    })

    setFieldErrors(errors)
    setDirty((current) => {
      const next = { ...current }
      for (const tier of succeeded) next[tier] = false
      return next
    })
    setSaved(succeeded.length > 0 && Object.keys(errors).length === 0)
  }

  const anyDirty = TIER_ORDER.some((tier) => dirty[tier])

  return (
    <div className="on-call-fee-settings-panel">
      <div className="on-call-fee-settings-panel__header">
        <div>
          <div className="on-call-fee-settings-panel__eyebrow">Configuração</div>
          <div className="on-call-fee-settings-panel__title">Taxas de plantão</div>
        </div>
        {canManage && (
          <button
            type="button"
            className="on-call-fee-settings-panel__save"
            onClick={() => void handleSave()}
            disabled={!anyDirty || updateMutation.isPending}
          >
            {updateMutation.isPending ? 'salvando…' : 'salvar alterações'}
          </button>
        )}
        {saved && <span className="on-call-fee-settings-panel__saved">Alterações salvas.</span>}
      </div>

      <div className="on-call-fee-settings-panel__grid">
        {TIER_ORDER.map((tier) => {
          const setting = settingsByTier.get(tier)
          const draft = drafts[tier]
          if (!setting || !draft) return null

          return (
            <div key={tier} className="on-call-fee-settings-panel__card">
              <div className="on-call-fee-settings-panel__tier-label" data-tier={tier}>
                <span className="on-call-fee-settings-panel__dot" data-tier={tier} />
                {TIER_LABELS[tier]}
              </div>
              <div className="on-call-fee-settings-panel__row">
                <label className="on-call-fee-settings-panel__field">
                  <span className="on-call-fee-settings-panel__field-label">Valor da taxa</span>
                  <input
                    id={`on-call-fee-${tier}`}
                    className="on-call-fee-settings-panel__input on-call-fee-settings-panel__input--mono"
                    value={draft.feeAmount}
                    disabled={!canManage || updateMutation.isPending}
                    onChange={(event) => updateDraft(tier, { feeAmount: event.target.value })}
                  />
                </label>
                <div className="on-call-fee-settings-panel__field">
                  <span className="on-call-fee-settings-panel__field-label">Aplicação</span>
                  <div className="on-call-fee-settings-panel__static-value">Fixo por protocolo</div>
                </div>
              </div>
              <label className="on-call-fee-settings-panel__schedule">
                <input
                  id={`on-call-schedule-${tier}`}
                  className="on-call-fee-settings-panel__schedule-input"
                  placeholder="Horário de aplicação (informativo) — ex.: Seg–Sáb · 19h às 07h"
                  value={draft.scheduleLabel}
                  disabled={!canManage || updateMutation.isPending}
                  onChange={(event) => updateDraft(tier, { scheduleLabel: event.target.value })}
                />
              </label>
              {fieldErrors[tier] && (
                <p role="alert" className="on-call-fee-settings-panel__error">
                  {fieldErrors[tier]}
                </p>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}
