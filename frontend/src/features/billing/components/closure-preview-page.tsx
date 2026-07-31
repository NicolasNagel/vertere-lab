import { useState } from 'react'

import { ApiError } from '../../../shared/api/errors'
import { formatCompetence, formatCurrencyBRL } from '../../../shared/lib/formatters'
import { Button } from '../../../shared/ui/button'
import type { SelectOption } from '../../../shared/ui/select'
import { useAuth } from '../../auth/auth-context'
import { useClinicsQuery } from '../../clinics/api/use-clinics-query'
import { useClosurePreviewQuery } from '../api/use-closure-preview-query'
import type { MonthlyClosure } from '../api/closures-api'
import { ClosureCloseModal } from './closure-close-modal'
import { ClosurePreviewFilters } from './closure-preview-filters'
import { ClosurePreviewItemsTable } from './closure-preview-items-table'
import { ClosurePreviewSummary } from './closure-preview-summary'
import './closure-preview-page.css'

const NOW = new Date()

export function ClosurePreviewPage() {
  const { user } = useAuth()
  const canPreview = user?.permissions.includes('closures.preview') ?? false
  const canClose = user?.permissions.includes('closures.close') ?? false

  const [clinicId, setClinicId] = useState('')
  const [year, setYear] = useState(NOW.getFullYear())
  const [month, setMonth] = useState(NOW.getMonth() + 1)
  const [showCloseModal, setShowCloseModal] = useState(false)
  const [justClosed, setJustClosed] = useState<MonthlyClosure | null>(null)

  const clinicsQuery = useClinicsQuery({ pageSize: 100 })
  const clinicOptions: SelectOption[] = (clinicsQuery.data?.items ?? []).map((clinic) => ({
    value: clinic.id,
    label: clinic.name,
  }))
  const selectedClinicName =
    clinicOptions.find((option) => option.value === clinicId)?.label ?? ''

  const previewQuery = useClosurePreviewQuery(
    canPreview && clinicId ? { clinicId, year, month } : null,
  )

  const isForbidden = previewQuery.error instanceof ApiError && previewQuery.error.status === 403
  const isGenericError = previewQuery.isError && !isForbidden

  function resetClosedBanner() {
    setJustClosed(null)
  }

  return (
    <div className="closure-preview-page">
      <div className="closure-preview-page__header">
        <div>
          <div className="closure-preview-page__eyebrow">Financeiro</div>
          <h1 className="closure-preview-page__title">Prévia de Fechamento</h1>
        </div>
      </div>

      <div className="closure-preview-page__body">
        {!canPreview ? (
          <p className="closure-preview-page__forbidden">
            Você não tem permissão para visualizar a prévia de fechamento.
          </p>
        ) : (
          <>
            <ClosurePreviewFilters
              clinicOptions={clinicOptions}
              clinicId={clinicId}
              year={year}
              month={month}
              onClinicChange={(value) => {
                setClinicId(value)
                resetClosedBanner()
              }}
              onYearChange={(value) => {
                setYear(value)
                resetClosedBanner()
              }}
              onMonthChange={(value) => {
                setMonth(value)
                resetClosedBanner()
              }}
            />

            {!clinicId && (
              <p className="closure-preview-page__hint">
                Selecione uma clínica para gerar a prévia da competência.
              </p>
            )}

            {clinicId && previewQuery.isLoading && (
              <p className="closure-preview-page__hint">Carregando prévia…</p>
            )}

            {clinicId && isForbidden && (
              <p className="closure-preview-page__forbidden">
                Você não tem permissão para visualizar a prévia de fechamento.
              </p>
            )}

            {clinicId && isGenericError && (
              <p className="closure-preview-page__error">
                Não foi possível carregar a prévia. Tente novamente.
              </p>
            )}

            {justClosed && (
              <p className="closure-preview-page__success" role="status">
                Competência {formatCompetence(justClosed.competenceYear, justClosed.competenceMonth)}{' '}
                fechada com sucesso — total {formatCurrencyBRL(justClosed.grandTotal)}.
              </p>
            )}

            {clinicId && previewQuery.data && (
              <>
                {canClose && (
                  <div className="closure-preview-page__actions">
                    <Button
                      type="button"
                      disabled={previewQuery.data.itemCount === 0}
                      onClick={() => setShowCloseModal(true)}
                    >
                      Fechar competência
                    </Button>
                  </div>
                )}
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
