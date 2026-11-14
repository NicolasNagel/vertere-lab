import { useCallback, useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router'
import { useQueryClient } from '@tanstack/react-query'

import { ApiError } from '../../../shared/api/errors'
import { Button } from '../../../shared/ui/button'
import { Dropdown, type DropdownOption } from '../../../shared/ui/dropdown'
import { PageHeader } from '../../../shared/ui/page-header'
import { TextField } from '../../../shared/ui/text-field'
import { useAuth } from '../../auth/auth-context'
import { useAllClinicsQuery } from '../../clinics/api/use-clinics-query'
import type { Patient } from '../../patients/api/patients-api'
import { useAllVeterinariansQuery } from '../../veterinarians/api/use-veterinarians-query'
import { attendanceQueryKey, useAttendanceQuery } from '../api/use-attendance-query'
import { useAttendanceExamSelections } from '../api/use-attendance-exam-selections'
import { useCreateAttendanceDraftMutation } from '../api/use-create-attendance-draft-mutation'
import { useUpdateAttendanceMutation } from '../api/use-update-attendance-mutation'
import {
  SERVICE_LEVEL_LABELS,
  type AttendanceUpdateInput,
  type CollectionMethod,
  type ServiceLevel,
} from '../api/attendances-api'
import { AttendanceExamSelectionList } from './attendance-exam-selection-list'
import { AttendancePatientSection } from './attendance-patient-section'
import { AttendanceSummaryPanel } from './attendance-summary-panel'
import './attendance-draft-page.css'

const COLLECTION_METHOD_OPTIONS: { value: CollectionMethod; label: string }[] = [
  { value: 'INTERNAL', label: 'Internos' },
  { value: 'COURIER', label: 'Motoboy' },
  { value: 'UBER', label: 'Uber' },
  { value: 'HELITO_NICOLAS', label: 'Helito/Nicolas' },
  { value: 'MARLI', label: 'Marli' },
]

const SERVICE_LEVEL_OPTIONS: { value: ServiceLevel; subtitle: string }[] = [
  { value: 'NORMAL', subtitle: 'Horário comercial' },
  { value: 'PLANTAO_NORMAL', subtitle: '+R$ 100,00' },
  { value: 'PLANTAO_ESPECIAL', subtitle: '+R$ 150,00' },
]

function describeError(error: unknown): string | null {
  if (error === null || error === undefined) return null
  if (error instanceof ApiError) return error.message
  return 'Falha de conexão. Verifique sua internet e tente novamente.'
}

/** Tela única de abertura de protocolo (Solicitante/Paciente/Exames/
 * Atendimento/Valor sempre visíveis, igual ao mockup "Tela 4") — layout
 * estático desde o início: as seções de Exames e Valor já aparecem
 * desabilitadas antes de o rascunho existir, pra tela não "pular" de
 * estrutura quando ele é criado.
 *
 * Clínica/veterinário/paciente/atendimento continuam controlados por
 * estado local o tempo todo (nunca trocam de fonte de verdade); uma vez
 * que o rascunho existe, cada mudança também dispara `PATCH` em segundo
 * plano (`useUpdateAttendanceMutation`, com o `rowVersion` mais recente do
 * cache) — o rascunho já criado nunca fica fora de sincronia com o que a
 * tela mostra. */
export function AttendanceDraftPage() {
  const { user } = useAuth()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const canCreate = user?.permissions.includes('attendances.create') ?? false
  const canOverridePrice = user?.permissions.includes('attendances.override_price') ?? false

  const [clinicId, setClinicId] = useState('')
  const [veterinarianId, setVeterinarianId] = useState('')
  const [patient, setPatient] = useState<Patient | null>(null)
  const [serviceDate, setServiceDate] = useState('')
  const [collectionMethod, setCollectionMethod] = useState<CollectionMethod>('INTERNAL')
  const [serviceLevel, setServiceLevel] = useState<ServiceLevel>('NORMAL')
  const [notes, setNotes] = useState('')

  const [draftAttendanceId, setDraftAttendanceId] = useState<string | null>(null)
  const draftAttendanceQuery = useAttendanceQuery(draftAttendanceId)
  const attendance = draftAttendanceQuery.data ?? null

  const clinicsQuery = useAllClinicsQuery({ status: 'ACTIVE' })
  const veterinariansQuery = useAllVeterinariansQuery({
    status: 'ACTIVE',
    availableForClinicId: clinicId || undefined,
  })
  const createDraftMutation = useCreateAttendanceDraftMutation()
  const updateMutation = useUpdateAttendanceMutation()
  const draftRequestedRef = useRef(false)

  const examSelections = useAttendanceExamSelections(attendance, () => navigate('/operacao'))

  const clinicOptions: DropdownOption[] = (clinicsQuery.data?.items ?? []).map((clinic) => ({
    value: clinic.id,
    label: clinic.name,
  }))
  const veterinarianOptions: DropdownOption[] = (veterinariansQuery.data?.items ?? []).map(
    (veterinarian) => ({ value: veterinarian.id, label: veterinarian.name }),
  )
  const selectedVeterinarian = veterinariansQuery.data?.items.find(
    (veterinarian) => veterinarian.id === veterinarianId,
  )

  const attemptCreateDraft = useCallback(() => {
    if (draftRequestedRef.current) return
    if (!clinicId || !veterinarianId || !patient) return
    draftRequestedRef.current = true
    createDraftMutation.mutate(
      {
        clinicId,
        veterinarianId,
        patientId: patient.id,
        serviceDate: serviceDate || null,
        collectionMethod,
        serviceLevel,
        notes: notes.trim() || null,
      },
      {
        onSuccess: (created) => {
          queryClient.setQueryData(attendanceQueryKey(created.id), created)
          setDraftAttendanceId(created.id)
        },
        onError: () => {
          draftRequestedRef.current = false
        },
      },
    )
    // eslint-disable-next-line react-hooks/exhaustive-deps -- mutation/queryClient identity churn shouldn't re-trigger the effect below
  }, [clinicId, veterinarianId, patient, serviceDate, collectionMethod, serviceLevel, notes])

  useEffect(() => {
    attemptCreateDraft()
  }, [attemptCreateDraft])

  // Uma vez que o rascunho existe, toda mudança nos campos de cabeçalho
  // também vira um PATCH real (auditável, com row_version) — nunca só
  // estado local solto (`.claude/rules/12-attendance.md`: "DRAFT: edição
  // ampla"). Antes do rascunho existir, isso é no-op (`attendance` é null).
  function syncHeaderField(patch: AttendanceUpdateInput) {
    if (!attendance) return
    updateMutation.mutate({ attendanceId: attendance.id, rowVersion: attendance.rowVersion, input: patch })
  }

  function handleClinicChange(value: string) {
    setClinicId(value)
    setVeterinarianId('')
  }

  function handleVeterinarianChange(value: string) {
    setVeterinarianId(value)
    if (clinicId) syncHeaderField({ clinicId, veterinarianId: value })
  }

  function handlePatientSelect(selected: Patient) {
    setPatient(selected)
    syncHeaderField({ patientId: selected.id })
  }

  function handleCollectionMethodChange(value: CollectionMethod) {
    setCollectionMethod(value)
    syncHeaderField({ collectionMethod: value })
  }

  function handleServiceLevelChange(value: ServiceLevel) {
    setServiceLevel(value)
    syncHeaderField({ serviceLevel: value })
  }

  function handleServiceDateBlur() {
    if (attendance && serviceDate !== (attendance.serviceDate ?? '')) {
      syncHeaderField({ serviceDate: serviceDate || null })
    }
  }

  function handleNotesBlur() {
    if (attendance && notes.trim() !== (attendance.notes ?? '')) {
      syncHeaderField({ notes: notes.trim() })
    }
  }

  function handleReloadAfterConflict() {
    if (!draftAttendanceId) return
    void queryClient.invalidateQueries({ queryKey: attendanceQueryKey(draftAttendanceId) })
  }

  const createErrorMessage = describeError(createDraftMutation.error)
  const updateErrorMessage = describeError(updateMutation.error)
  const isUpdateConflict =
    updateMutation.error instanceof ApiError && updateMutation.error.status === 409
  const fieldsDisabled = createDraftMutation.isPending || updateMutation.isPending

  return (
    <div className="attendance-draft-page">
      <PageHeader title="Abertura de protocolo" />

      <div className="attendance-draft-page__body">
        {!canCreate ? (
          <p className="attendance-draft-page__forbidden">
            Você não tem permissão para criar atendimentos.
          </p>
        ) : (
          <div className="attendance-draft-page__columns">
            <div className="attendance-draft-page__column">
              <section className="attendance-draft-page__section">
                <h2 className="attendance-draft-page__section-title">
                  Solicitante
                </h2>
                <div className="attendance-draft-page__row">
                  <Dropdown
                    variant="field"
                    label="Clínica solicitante"
                    placeholder={clinicsQuery.isLoading ? 'Carregando…' : 'Selecione a clínica'}
                    options={clinicOptions}
                    searchable
                    disabled={fieldsDisabled}
                    value={clinicId}
                    onChange={handleClinicChange}
                  />
                  <div className="attendance-draft-page__field-group">
                    <Dropdown
                      variant="field"
                      label="Veterinário responsável"
                      placeholder={
                        !clinicId
                          ? 'Escolha a clínica primeiro'
                          : veterinariansQuery.isLoading
                            ? 'Carregando…'
                            : 'Selecione o veterinário'
                      }
                      options={veterinarianOptions}
                      searchable
                      disabled={fieldsDisabled || !clinicId}
                      value={veterinarianId}
                      onChange={handleVeterinarianChange}
                    />
                    {selectedVeterinarian && (
                      <p className="attendance-draft-page__hint attendance-draft-page__hint--compact attendance-draft-page__mono">
                        {selectedVeterinarian.crmv}
                        {selectedVeterinarian.email ? ` · ${selectedVeterinarian.email}` : ''}
                      </p>
                    )}
                  </div>
                </div>
                {clinicsQuery.isError && (
                  <p role="alert" className="attendance-draft-page__domain-error">
                    Não foi possível carregar as clínicas.
                  </p>
                )}
                {clinicId && veterinariansQuery.isError && (
                  <p role="alert" className="attendance-draft-page__domain-error">
                    Não foi possível carregar os veterinários.
                  </p>
                )}
              </section>

              <section className="attendance-draft-page__section">
                <h2 className="attendance-draft-page__section-title">
                  Dados do animal
                </h2>
                <AttendancePatientSection
                  clinicId={clinicId}
                  selectedPatient={patient}
                  disabled={fieldsDisabled}
                  onSelect={handlePatientSelect}
                  onClear={() => setPatient(null)}
                />
              </section>

              <section className="attendance-draft-page__section">
                <div className="attendance-draft-page__section-header">
                  <h2 className="attendance-draft-page__section-title">
                    Exames
                  </h2>
                  <span className="attendance-draft-page__count">
                    {examSelections.selections.length} selecionado
                    {examSelections.selections.length === 1 ? '' : 's'}
                  </span>
                </div>
                {!attendance && (
                  <p className="attendance-draft-page__hint">
                    Preencha clínica, veterinário e paciente para adicionar exames.
                  </p>
                )}
                <AttendanceExamSelectionList
                  selections={examSelections.selections}
                  canOverridePrice={canOverridePrice}
                  disabled={!attendance || examSelections.isPending}
                  onAdd={examSelections.addExam}
                  onRemove={examSelections.removeExam}
                  onUpdate={examSelections.updateSelection}
                />
              </section>
            </div>

            <div className="attendance-draft-page__column attendance-draft-page__column--side">
              <section className="attendance-draft-page__section">
                <h2 className="attendance-draft-page__section-title">
                  Atendimento
                </h2>

                <div
                  className="attendance-draft-page__toggle-group"
                  role="group"
                  aria-label="Tipo de atendimento"
                >
                  {SERVICE_LEVEL_OPTIONS.map((option) => (
                    <button
                      key={option.value}
                      type="button"
                      className="attendance-draft-page__toggle"
                      data-active={serviceLevel === option.value}
                      aria-pressed={serviceLevel === option.value}
                      disabled={fieldsDisabled}
                      onClick={() => handleServiceLevelChange(option.value)}
                    >
                      <span className="attendance-draft-page__toggle-title">
                        {SERVICE_LEVEL_LABELS[option.value]}
                      </span>
                      <span className="attendance-draft-page__toggle-subtitle">
                        {option.subtitle}
                      </span>
                    </button>
                  ))}
                </div>

                <span className="attendance-draft-page__label">Método de coleta</span>
                <div
                  className="attendance-draft-page__toggle-group attendance-draft-page__toggle-group--flat"
                  role="group"
                  aria-label="Método de coleta"
                >
                  {COLLECTION_METHOD_OPTIONS.map((option) => (
                    <button
                      key={option.value}
                      type="button"
                      className="attendance-draft-page__toggle attendance-draft-page__toggle--flat"
                      data-active={collectionMethod === option.value}
                      aria-pressed={collectionMethod === option.value}
                      disabled={fieldsDisabled}
                      onClick={() => handleCollectionMethodChange(option.value)}
                    >
                      {option.label}
                    </button>
                  ))}
                </div>

                <div className="attendance-draft-page__row">
                  <TextField
                    id="attendance-draft-service-date"
                    label="Data do atendimento"
                    type="date"
                    disabled={fieldsDisabled}
                    value={serviceDate}
                    onChange={(event) => setServiceDate(event.target.value)}
                    onBlur={handleServiceDateBlur}
                  />
                  <TextField
                    id="attendance-draft-notes"
                    label="Observações"
                    disabled={fieldsDisabled}
                    value={notes}
                    onChange={(event) => setNotes(event.target.value)}
                    onBlur={handleNotesBlur}
                  />
                </div>
              </section>

              <AttendanceSummaryPanel
                items={examSelections.previewQuery.data?.items ?? []}
                subtotal={examSelections.previewQuery.data?.subtotal ?? '0.00'}
                discountTotal={examSelections.previewQuery.data?.discountTotal ?? '0.00'}
                onCallFee={examSelections.previewQuery.data?.onCallFee ?? '0.00'}
                grandTotal={examSelections.previewQuery.data?.grandTotal ?? '0.00'}
                isLoading={
                  examSelections.selections.length > 0 && examSelections.previewQuery.isLoading
                }
              />

              {createErrorMessage && (
                <p role="alert" className="attendance-draft-page__domain-error">
                  {createErrorMessage}{' '}
                  <button
                    type="button"
                    className="attendance-draft-page__retry-button"
                    onClick={attemptCreateDraft}
                  >
                    Tentar novamente
                  </button>
                </p>
              )}

              {updateErrorMessage && (
                <div className="attendance-draft-page__domain-error" role="alert">
                  <p>{updateErrorMessage}</p>
                  {isUpdateConflict && (
                    <button type="button" onClick={handleReloadAfterConflict}>
                      Recarregar
                    </button>
                  )}
                </div>
              )}

              {examSelections.errorMessage && (
                <div className="attendance-draft-page__domain-error" role="alert">
                  <p>{examSelections.errorMessage}</p>
                  {examSelections.isConflict && (
                    <button type="button" onClick={examSelections.handleReload}>
                      Recarregar
                    </button>
                  )}
                </div>
              )}

              <div className="attendance-draft-page__actions">
                <Button
                  type="button"
                  variant="ghost"
                  onClick={() => navigate('/operacao')}
                  disabled={examSelections.isPending}
                >
                  Cancelar
                </Button>
                <Button
                  type="button"
                  disabled={!examSelections.canConfirm}
                  onClick={examSelections.handleConfirm}
                >
                  {examSelections.isPending ? 'Abrindo…' : 'Abrir protocolo'}
                </Button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
