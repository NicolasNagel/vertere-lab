import { useState } from 'react'
import { useSearchParams } from 'react-router'

import { ApiError } from '../../../shared/api/errors'
import { formatCurrencyBRL, formatDate } from '../../../shared/lib/formatters'
import { Button } from '../../../shared/ui/button'
import type { DropdownOption } from '../../../shared/ui/dropdown'
import { useAuth } from '../../auth/auth-context'
import { useAllClinicsQuery } from '../../clinics/api/use-clinics-query'
import { useClinicQuery } from '../../clinics/api/use-clinic-query'
import type { MonthlyClosure } from '../api/closures-api'
import { monthlyClosureExportUrl } from '../api/closures-api'
import { useClosureByPeriodQuery } from '../api/use-closure-by-period-query'
import { useClosurePreviewQuery } from '../api/use-closure-preview-query'
import { groupItemsByCategory } from '../lib/group-by-category'
import { ClosureCloseModal } from './closure-close-modal'
import { ClosureExistingView } from './closure-existing-view'
import { ClosureHistoryBrowser } from './closure-history-browser'
import { ClosureInvoicePanel } from './closure-invoice-panel'
import { ClosurePreviewFilters } from './closure-preview-filters'
import { ClosurePreviewItemsTable } from './closure-preview-items-table'
import { ClosurePreviewSummary } from './closure-preview-summary'
import './closure-page.css'

const NOW = new Date()

function toIsoDate(date: Date): string {
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

const DEFAULT_PERIOD_START = toIsoDate(new Date(NOW.getFullYear(), NOW.getMonth(), 1))
const DEFAULT_PERIOD_END = toIsoDate(new Date(NOW.getFullYear(), NOW.getMonth() + 1, 0))

/** Unified fechamento screen (Tela 15) — the single route
 * (`/financeiro/fechamento`) for browsing history, previewing, and closing.
 * Driven by `clinicId`/`periodStart`/`periodEnd` search params (a free
 * range, not just a calendar month — some clinics close quinzenalmente):
 * with no `clinicId`, shows the closures history (`ClosureHistoryBrowser`);
 * once a clinic is picked, looks up whether a closure already exists for
 * that clinic+período first, only falling back to the read-only prévia when
 * none is found. */
export function ClosurePage() {
  const { user } = useAuth()
  const permissions = user?.permissions ?? []
  const canRead = permissions.includes('closures.read')
  const canPreview = permissions.includes('closures.preview')
  const canClose = permissions.includes('closures.close')
  const canReopen = permissions.includes('closures.reopen')
  const canAdjust = permissions.includes('closures.adjust')

  const [searchParams, setSearchParams] = useSearchParams()
  const clinicId = searchParams.get('clinicId') ?? ''
  const periodStart = searchParams.get('periodStart') ?? DEFAULT_PERIOD_START
  const periodEnd = searchParams.get('periodEnd') ?? DEFAULT_PERIOD_END

  const [showCloseModal, setShowCloseModal] = useState(false)
  const [justClosed, setJustClosed] = useState<MonthlyClosure | null>(null)

  const clinicsQuery = useAllClinicsQuery()
  const clinicOptions: DropdownOption[] = (clinicsQuery.data?.items ?? []).map((clinic) => ({
    value: clinic.id,
    label: clinic.name,
  }))
  const selectedClinicName =
    clinicOptions.find((option) => option.value === clinicId)?.label ?? ''
  const clinicQuery = useClinicQuery(clinicId || null)

  function updateParams(next: { clinicId?: string; periodStart?: string; periodEnd?: string }) {
    const params = new URLSearchParams(searchParams)
    if (next.clinicId !== undefined) {
      if (next.clinicId) params.set('clinicId', next.clinicId)
      else params.delete('clinicId')
    }
    if (next.periodStart !== undefined) params.set('periodStart', next.periodStart)
    if (next.periodEnd !== undefined) params.set('periodEnd', next.periodEnd)
    setSearchParams(params, { replace: true })
    setJustClosed(null)
  }

  const periodIsValid = periodStart !== '' && periodEnd !== '' && periodEnd >= periodStart

  const closureQuery = useClosureByPeriodQuery(
    canRead && clinicId && periodIsValid ? { clinicId, periodStart, periodEnd } : null,
  )
  const closureNotFound = closureQuery.error instanceof ApiError && closureQuery.error.status === 404
  const closureIsForbidden =
    closureQuery.error instanceof ApiError && closureQuery.error.status === 403
  const closureIsGenericError = closureQuery.isError && !closureNotFound && !closureIsForbidden

  // Um fechamento REOPENED ainda tem um registro (o histórico do que foi
  // reaberto), mas seus atendimentos já foram liberados de volta — sem isto,
  // a tela ficaria travada mostrando só o reaberto, sem caminho para fechar
  // de novo (`.claude/rules/13-monthly-closure.md`: "nova versão CLOSED
  // quando fechar de novo").
  const isReopened = closureQuery.data?.status === 'REOPENED'
  const shouldPreview =
    clinicId !== '' && canPreview && (!canRead || closureNotFound || isReopened)
  const previewQuery = useClosurePreviewQuery(
    shouldPreview && periodIsValid ? { clinicId, periodStart, periodEnd } : null,
  )
  const previewIsForbidden =
    previewQuery.error instanceof ApiError && previewQuery.error.status === 403
  const previewIsGenericError = previewQuery.isError && !previewIsForbidden

  const titlePeriod = clinicId ? `${formatDate(periodStart)} – ${formatDate(periodEnd)}` : ''

  // O painel "Demonstrativo analítico" segue a mesma fonte que já está
  // visível no corpo da tela: prévia quando ela é a ação corrente (inclusive
  // pós-reabertura), senão o fechamento já existente.
  const invoiceSource =
    shouldPreview && previewQuery.data
      ? {
          periodStart: previewQuery.data.periodStart,
          periodEnd: previewQuery.data.periodEnd,
          categoryBreakdown: groupItemsByCategory(previewQuery.data.eligibleItems),
          onCallFeeTotal: previewQuery.data.onCallFeeTotal,
          grandTotal: previewQuery.data.grandTotal,
          exportUrl: null,
        }
      : closureQuery.data
        ? {
            periodStart: closureQuery.data.periodStart,
            periodEnd: closureQuery.data.periodEnd,
            categoryBreakdown: groupItemsByCategory(closureQuery.data.items),
            onCallFeeTotal: closureQuery.data.onCallFeeTotal,
            grandTotal: closureQuery.data.grandTotal,
            exportUrl: monthlyClosureExportUrl(closureQuery.data.id),
          }
        : null

  return (
    <div className="closure-page">
      <div className="closure-page__header">
        <div>
          <div className="closure-page__eyebrow">Financeiro</div>
          <h1 className="closure-page__title">
            Fechamento
            {selectedClinicName && <em className="closure-page__title-clinic"> {selectedClinicName}</em>}
            {titlePeriod && ` · ${titlePeriod}`}
          </h1>
        </div>
        {canClose && shouldPreview && previewQuery.data && (
          <div className="closure-page__actions">
            <Button
              type="button"
              disabled={previewQuery.data.itemCount === 0}
              onClick={() => setShowCloseModal(true)}
            >
              Fechar período
            </Button>
          </div>
        )}
      </div>

      <div className="closure-page__body">
        {!canRead && !canPreview ? (
          <p className="closure-page__forbidden">
            Você não tem permissão para visualizar fechamentos.
          </p>
        ) : (
          <div className="closure-page__columns">
          <div className="closure-page__main">
            <ClosurePreviewFilters
              clinicOptions={clinicOptions}
              clinicId={clinicId}
              periodStart={periodStart}
              periodEnd={periodEnd}
              onClinicChange={(value) => updateParams({ clinicId: value })}
              onPeriodStartChange={(value) => updateParams({ periodStart: value })}
              onPeriodEndChange={(value) => updateParams({ periodEnd: value })}
            />

            {!periodIsValid && (
              <p className="closure-page__error" role="alert">
                Data final não pode ser anterior à inicial.
              </p>
            )}

            {!clinicId && canRead && <ClosureHistoryBrowser />}

            {!clinicId && !canRead && (
              <p className="closure-page__hint">
                Selecione uma clínica para gerar a prévia do período.
              </p>
            )}

            {justClosed && (
              <p className="closure-page__success" role="status">
                Período {formatDate(justClosed.periodStart)} – {formatDate(justClosed.periodEnd)}{' '}
                fechado com sucesso — total {formatCurrencyBRL(justClosed.grandTotal)}.
              </p>
            )}

            {clinicId && canRead && closureQuery.isLoading && (
              <p className="closure-page__hint">Carregando…</p>
            )}

            {clinicId && closureIsForbidden && (
              <p className="closure-page__forbidden">
                Você não tem permissão para visualizar este fechamento.
              </p>
            )}

            {clinicId && closureIsGenericError && (
              <p className="closure-page__error">
                Não foi possível carregar o fechamento. Tente novamente.
              </p>
            )}

            {clinicId && canRead && closureQuery.data && (
              <ClosureExistingView
                closure={closureQuery.data}
                canReopen={canReopen}
                canAdjust={canAdjust}
              />
            )}

            {shouldPreview && (
              <>
                {!canPreview && (
                  <p className="closure-page__forbidden">
                    Você não tem permissão para visualizar a prévia de fechamento.
                  </p>
                )}

                {canPreview && previewQuery.isLoading && (
                  <p className="closure-page__hint">Carregando prévia…</p>
                )}

                {canPreview && previewIsForbidden && (
                  <p className="closure-page__forbidden">
                    Você não tem permissão para visualizar a prévia de fechamento.
                  </p>
                )}

                {canPreview && previewIsGenericError && (
                  <p className="closure-page__error">
                    Não foi possível carregar a prévia. Tente novamente.
                  </p>
                )}

                {canPreview && previewQuery.data && (
                  <>
                    <ClosurePreviewSummary preview={previewQuery.data} />
                    <ClosurePreviewItemsTable
                      eligibleItems={previewQuery.data.eligibleItems}
                      blockedItems={previewQuery.data.blockedItems}
                    />
                  </>
                )}
              </>
            )}
          </div>

          {invoiceSource && (
            <ClosureInvoicePanel
              clinicName={selectedClinicName}
              clinicTaxId={clinicQuery.data?.taxId ?? null}
              periodStart={invoiceSource.periodStart}
              periodEnd={invoiceSource.periodEnd}
              categoryBreakdown={invoiceSource.categoryBreakdown}
              onCallFeeTotal={invoiceSource.onCallFeeTotal}
              grandTotal={invoiceSource.grandTotal}
              exportUrl={invoiceSource.exportUrl}
            />
          )}
          </div>
        )}
      </div>

      {showCloseModal && previewQuery.data && (
        <ClosureCloseModal
          clinicName={selectedClinicName}
          preview={previewQuery.data}
          onClose={() => setShowCloseModal(false)}
          onClosed={(closure) => {
            setShowCloseModal(false)
            setJustClosed(closure)
          }}
        />
      )}
    </div>
  )
}
