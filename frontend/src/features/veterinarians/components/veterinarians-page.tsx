import { useState } from 'react'

import { useAuth } from '../../auth/auth-context'
import { Button } from '../../../shared/ui/button'
import { PlusIcon } from '../../../shared/ui/icons'
import { useCreateVeterinarianMutation } from '../api/use-create-veterinarian-mutation'
import { useDeactivateVeterinarianMutation } from '../api/use-deactivate-veterinarian-mutation'
import { useUpdateVeterinarianMutation } from '../api/use-update-veterinarian-mutation'
import { useVeterinarianQuery } from '../api/use-veterinarian-query'
import { useVeterinariansQuery } from '../api/use-veterinarians-query'
import { VeterinarianDetail } from './veterinarian-detail'
import { VeterinarianForm } from './veterinarian-form'
import { VeterinarianList, type VeterinarianTypeFilter } from './veterinarian-list'
import './veterinarians-page.css'

type PanelMode = 'view' | 'create' | 'edit'

export function VeterinariansPage() {
  const { user } = useAuth()
  const canManage = user?.permissions.includes('veterinarians.manage') ?? false

  const [search, setSearch] = useState('')
  const [page, setPage] = useState(1)
  const [typeFilter, setTypeFilter] = useState<VeterinarianTypeFilter>('all')
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [mode, setMode] = useState<PanelMode>('view')

  // "Vinculados" não é filtrável na listagem — a API não expõe esse filtro no
  // GET /veterinarians (só is_autonomous); o vínculo em si já existe e é
  // gerenciado no formulário/detalhe. Trata como "todos" até um filtro de
  // lista ser justificado por uso real.
  const isAutonomous = typeFilter === 'autonomous' ? true : undefined

  const listQuery = useVeterinariansQuery({
    search: search || undefined,
    isAutonomous,
    page,
    pageSize: 25,
  })
  const detailQuery = useVeterinarianQuery(mode === 'create' ? null : selectedId)

  const createMutation = useCreateVeterinarianMutation()
  const updateMutation = useUpdateVeterinarianMutation()
  const deactivateMutation = useDeactivateVeterinarianMutation()

  const veterinarians = listQuery.data?.items ?? []
  const activeCount = veterinarians.filter((veterinarian) => veterinarian.status === 'ACTIVE').length

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
    <div className="veterinarians-page">
      <div className="veterinarians-page__header">
        <div>
          <div className="veterinarians-page__eyebrow">Cadastros</div>
          <h1 className="veterinarians-page__title">Veterinários</h1>
        </div>
        {canManage && (
          <Button
            type="button"
            className="veterinarians-page__new-button"
            onClick={handleStartCreate}
          >
            <PlusIcon /> Novo vet
          </Button>
        )}
      </div>

      <div className="veterinarians-page__body">
        <VeterinarianList
          veterinarians={veterinarians}
          activeCount={activeCount}
          selectedId={mode === 'create' ? null : selectedId}
          search={search}
          typeFilter={typeFilter}
          isLoading={listQuery.isLoading}
          onSearchChange={(value) => {
            setSearch(value)
            setPage(1)
          }}
          onTypeFilterChange={(value) => {
            setTypeFilter(value)
            setPage(1)
          }}
          onSelect={handleSelect}
          page={listQuery.data?.page ?? page}
          pageSize={listQuery.data?.pageSize ?? 25}
          total={listQuery.data?.total ?? 0}
          onPageChange={setPage}
        />

        {mode === 'create' ? (
          <div className="veterinarians-page__create-panel">
            <h2 className="veterinarians-page__create-title">Novo vet</h2>
            <VeterinarianForm
              veterinarian={null}
              submitting={createMutation.isPending}
              error={createMutation.error}
              onCancel={() => setMode('view')}
              onSubmitCreate={(values, clinicIds) =>
                createMutation.mutate(
                  { values, clinicIds },
                  {
                    onSuccess: (veterinarian) => {
                      setSelectedId(veterinarian.id)
                      setMode('view')
                    },
                  },
                )
              }
            />
          </div>
        ) : (
          <VeterinarianDetail
            veterinarian={detailQuery.data ?? null}
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
