import { useState } from 'react'

import { useAuth } from '../../auth/auth-context'
import { useSubmitGuard } from '../../../shared/lib/use-submit-guard'
import { Button } from '../../../shared/ui/button'
import { PlusIcon } from '../../../shared/ui/icons'
import { useCreatePatientMutation } from '../api/use-create-patient-mutation'
import { useDeactivatePatientMutation } from '../api/use-deactivate-patient-mutation'
import { useReactivatePatientMutation } from '../api/use-reactivate-patient-mutation'
import { usePatientQuery } from '../api/use-patient-query'
import { usePatientsQuery } from '../api/use-patients-query'
import { useUpdatePatientMutation } from '../api/use-update-patient-mutation'
import { PatientDetail } from './patient-detail'
import { PatientForm } from './patient-form'
import { PatientList } from './patient-list'
import './patients-page.css'

type PanelMode = 'view' | 'create' | 'edit'

export function PatientsPage() {
  const { user } = useAuth()
  const canManage = user?.permissions.includes('patients.manage') ?? false

  const [search, setSearch] = useState('')
  const [page, setPage] = useState(1)
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [mode, setMode] = useState<PanelMode>('view')

  const listQuery = usePatientsQuery({ search: search || undefined, page, pageSize: 25 })
  const detailQuery = usePatientQuery(mode === 'create' ? null : selectedId)

  const createMutation = useCreatePatientMutation()
  const guardCreate = useSubmitGuard()
  const updateMutation = useUpdatePatientMutation()
  const deactivateMutation = useDeactivatePatientMutation()
  const reactivateMutation = useReactivatePatientMutation()

  const patients = listQuery.data?.items ?? []
  const activeCount = patients.filter((patient) => patient.status === 'ACTIVE').length

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
    <div className="patients-page">
      <div className="patients-page__header">
        <div>
          <div className="patients-page__eyebrow">Cadastros</div>
          <h1 className="patients-page__title">Pacientes</h1>
        </div>
        {canManage && (
          <Button type="button" className="patients-page__new-button" onClick={handleStartCreate}>
            <PlusIcon /> Novo paciente
          </Button>
        )}
      </div>

      <div className="patients-page__body">
        <PatientList
          patients={patients}
          activeCount={activeCount}
          selectedId={mode === 'create' ? null : selectedId}
          search={search}
          isLoading={listQuery.isLoading}
          isError={listQuery.isError}
          onSearchChange={(value) => {
            setSearch(value)
            setPage(1)
          }}
          onSelect={handleSelect}
          page={listQuery.data?.page ?? page}
          pageSize={listQuery.data?.pageSize ?? 25}
          total={listQuery.data?.total ?? 0}
          onPageChange={setPage}
        />

        {mode === 'create' ? (
          <div className="patients-page__create-panel">
            <h2 className="patients-page__create-title">Novo paciente</h2>
            <PatientForm
              patient={null}
              submitting={createMutation.isPending}
              error={createMutation.error}
              onCancel={() => setMode('view')}
              onSubmitCreate={(values) =>
                guardCreate((release) =>
                  createMutation.mutate(values, {
                    onSuccess: (patient) => {
                      setSelectedId(patient.id)
                      setMode('view')
                    },
                    onSettled: release,
                  }),
                )
              }
            />
          </div>
        ) : (
          <PatientDetail
            patient={detailQuery.data ?? null}
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
            onReactivate={() => selectedId && reactivateMutation.mutate(selectedId)}
          />
        )}
      </div>
    </div>
  )
}
