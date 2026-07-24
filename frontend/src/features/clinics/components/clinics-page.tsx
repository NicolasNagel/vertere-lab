import { useState } from 'react'

import { useAuth } from '../../auth/auth-provider'
import { Button } from '../../../shared/ui/button'
import { PlusIcon } from '../../../shared/ui/icons'
import { useClinicQuery } from '../api/use-clinic-query'
import { useClinicsQuery } from '../api/use-clinics-query'
import { useCreateClinicMutation } from '../api/use-create-clinic-mutation'
import { useDeactivateClinicMutation } from '../api/use-deactivate-clinic-mutation'
import { useUpdateClinicMutation } from '../api/use-update-clinic-mutation'
import { ClinicDetail } from './clinic-detail'
import { ClinicForm } from './clinic-form'
import { ClinicList } from './clinic-list'
import './clinics-page.css'

type PanelMode = 'view' | 'create' | 'edit'

export function ClinicsPage() {
  const { user } = useAuth()
  const canManage = user?.permissions.includes('clinics.manage') ?? false

  const [search, setSearch] = useState('')
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [mode, setMode] = useState<PanelMode>('view')

  const listQuery = useClinicsQuery({ search: search || undefined, pageSize: 100 })
  const detailQuery = useClinicQuery(mode === 'create' ? null : selectedId)

  const createMutation = useCreateClinicMutation()
  const updateMutation = useUpdateClinicMutation()
  const deactivateMutation = useDeactivateClinicMutation()

  const clinics = listQuery.data?.items ?? []
  const activeCount = clinics.filter((clinic) => clinic.status === 'ACTIVE').length

  function handleSelect(id: string) {
    setSelectedId(id)
    setMode('view')
  }

  function handleStartCreate() {
    setSelectedId(null)
    setMode('create')
  }

  function handleDeactivate() {
    if (!selectedId) return
    deactivateMutation.mutate(selectedId)
  }

  return (
    <div className="clinics-page">
      <div className="clinics-page__header">
        <div>
          <div className="clinics-page__eyebrow">Cadastros</div>
          <h1 className="clinics-page__title">Clínicas parceiras</h1>
        </div>
        {canManage && (
          <Button type="button" className="clinics-page__new-button" onClick={handleStartCreate}>
            <PlusIcon /> Nova clínica
          </Button>
        )}
      </div>

      <div className="clinics-page__body">
        <ClinicList
          clinics={clinics}
          activeCount={activeCount}
          selectedId={mode === 'create' ? null : selectedId}
          search={search}
          isLoading={listQuery.isLoading}
          onSearchChange={setSearch}
          onSelect={handleSelect}
        />

        {mode === 'create' ? (
          <div className="clinics-page__create-panel">
            <h2 className="clinics-page__create-title">Nova clínica</h2>
            <ClinicForm
              clinic={null}
              submitting={createMutation.isPending}
              error={createMutation.error}
              onCancel={() => setMode('view')}
              onSubmitCreate={(values) =>
                createMutation.mutate(values, {
                  onSuccess: (clinic) => {
                    setSelectedId(clinic.id)
                    setMode('view')
                  },
                })
              }
            />
          </div>
        ) : (
          <ClinicDetail
            clinic={detailQuery.data ?? null}
            isLoading={selectedId !== null && detailQuery.isLoading}
            isEditing={mode === 'edit'}
            canManage={canManage}
            submitting={updateMutation.isPending}
            submitError={updateMutation.error}
            onStartEdit={() => setMode('edit')}
            onCancelEdit={() => setMode('view')}
            onSubmitUpdate={(values) => {
              if (!selectedId || !detailQuery.data) return
              updateMutation.mutate(
                {
                  id: selectedId,
                  values: { ...values, expectedRowVersion: detailQuery.data.rowVersion },
                },
                { onSuccess: () => setMode('view') },
              )
            }}
            onDeactivate={handleDeactivate}
          />
        )}
      </div>
    </div>
  )
}
