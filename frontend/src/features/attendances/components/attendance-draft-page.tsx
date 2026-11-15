import { useCallback, useEffect, useRef, useState } from 'react'
import { Link, useNavigate } from 'react-router'
import { useQueryClient } from '@tanstack/react-query'

import { ApiError } from '../../../shared/api/errors'
import { formatCurrencyBRL } from '../../../shared/lib/formatters'
import { Button } from '../../../shared/ui/button'
import { Checkbox } from '../../../shared/ui/checkbox'
import { Dropdown, type DropdownOption } from '../../../shared/ui/dropdown'
import { ArrowLeftIcon } from '../../../shared/ui/icons'
import { PageHeader } from '../../../shared/ui/page-header'
import { TextField } from '../../../shared/ui/text-field'
import { useAuth } from '../../auth/auth-context'
import { useAllClinicsQuery } from '../../clinics/api/use-clinics-query'
import type { Patient } from '../../patients/api/patients-api'
import { usePatientQuery } from '../../patients/api/use-patient-query'
import { useAllVeterinariansQuery } from '../../veterinarians/api/use-veterinarians-query'
import { attendanceQueryKey, useAttendanceQuery } from '../api/use-attendance-query'
import { useAttendanceExamSelections } from '../api/use-attendance-exam-selections'
import { useOnCallFeeSettingsQuery } from '../api/use-on-call-fee-settings-query'
import { useUrgencyFeeQuery } from '../api/use-urgency-fee-query'
import { feeRows } from '../lib/attendance-fees'
import { useCreateAttendanceDraftMutation } from '../api/use-create-attendance-draft-mutation'
import { useUpdateAttendanceMutation } from '../api/use-update-attendance-mutation'
import {
  CANCELLABLE_STATUSES,
  SERVICE_LEVEL_LABELS,
  type Attendance,
  type AttendanceUpdateInput,
  type CollectionMethod,
  type ServiceLevel,
} from '../api/attendances-api'
import { useActiveExamCategoriesQuery } from '../../catalog/api/use-active-exam-categories-query'
import { useAllActiveExamsQuery } from '../../catalog/api/use-all-active-exams-query'
import { AttendanceCancelModal } from './attendance-cancel-modal'
import { ExamCartGrid } from './exam-cart-grid'
import { AttendancePatientSection } from './attendance-patient-section'
import { AttendanceSummaryBar } from './attendance-summary-bar'
import '../../../shared/ui/button.css'
import './attendance-draft-page.css'

const COLLECTION_METHOD_OPTIONS: { value: CollectionMethod; label: string }[] = [
  { value: 'INTERNAL', label: 'Internos' },
  { value: 'COURIER', label: 'Motoboy' },
  { value: 'UBER', label: 'Uber' },
  { value: 'HELITO_NICOLAS', label: 'Helito/Nicolas' },
  { value: 'MARLI', label: 'Marli' },
]

const SERVICE_LEVELS: ServiceLevel[] = ['NORMAL', 'PLANTAO_NORMAL', 'PLANTAO_ESPECIAL']

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
interface AttendanceDraftPageProps {
  /** Rascunho já existente (aberto pela lista): a tela abre preenchida e segue dele. */
  resumeAttendance?: Attendance
}

export function AttendanceDraftPage({ resumeAttendance }: AttendanceDraftPageProps = {}) {
  const { user } = useAuth()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const canCreate = user?.permissions.includes('attendances.create') ?? false
  const canOverridePrice = user?.permissions.includes('attendances.override_price') ?? false
  const showMoney = user?.permissions.includes('pricing.read') ?? false

  const [clinicId, setClinicId] = useState(resumeAttendance?.clinicId ?? '')
  const [veterinarianId, setVeterinarianId] = useState(resumeAttendance?.veterinarianId ?? '')
  const [patient, setPatient] = useState<Patient | null>(null)
  const [serviceDate, setServiceDate] = useState(resumeAttendance?.serviceDate ?? '')
  const [collectionMethod, setCollectionMethod] = useState<CollectionMethod>(
    resumeAttendance?.collectionMethod ?? 'INTERNAL',
  )
  const [serviceLevel, setServiceLevel] = useState<ServiceLevel>(
    resumeAttendance?.serviceLevel ?? 'NORMAL',
  )
  const [isUrgent, setIsUrgent] = useState(resumeAttendance?.isUrgent ?? false)
  const [notes, setNotes] = useState(resumeAttendance?.notes ?? '')
  const [showDiscardModal, setShowDiscardModal] = useState(false)

  const [draftAttendanceId, setDraftAttendanceId] = useState<string | null>(
    resumeAttendance?.id ?? null,
  )
  const draftAttendanceQuery = useAttendanceQuery(draftAttendanceId)
  const attendance = draftAttendanceQuery.data ?? null

  const clinicsQuery = useAllClinicsQuery({ status: 'ACTIVE' })
  const veterinariansQuery = useAllVeterinariansQuery({
    status: 'ACTIVE',
    availableForClinicId: clinicId || undefined,
  })
  const feeSettingsQuery = useOnCallFeeSettingsQuery(showMoney)
  const urgencyFeeQuery = useUrgencyFeeQuery(showMoney)
  const examsQuery = useAllActiveExamsQuery()
  const examCategoriesQuery = useActiveExamCategoriesQuery()
  const createDraftMutation = useCreateAttendanceDraftMutation()
  const updateMutation = useUpdateAttendanceMutation()
  const draftRequestedRef = useRef(Boolean(resumeAttendance))
  const resumedPatientQuery = usePatientQuery(resumeAttendance?.patientId ?? null)
  const canDiscard = user?.permissions.includes('attendances.cancel') ?? false

  const examSelections = useAttendanceExamSelections(attendance, () => navigate('/operacao'))

  const missingForExams = [
    !clinicId && 'clínica',
    !veterinarianId && 'veterinário',
    !patient && 'paciente',
  ].filter((label): label is string => Boolean(label))

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

  const urgencyFeeLabel =
    urgencyFeeQuery.data && Number(urgencyFeeQuery.data.feeAmount) > 0
      ? `+ ${formatCurrencyBRL(urgencyFeeQuery.data.feeAmount)}`
      : ''
  const feeByLevel = new Map(
    (feeSettingsQuery.data ?? []).map((setting) => [setting.serviceLevel, setting]),
  )
  function describeServiceLevel(level: ServiceLevel): string {
    if (level === 'NORMAL') return 'Horário comercial'
    const setting = feeByLevel.get(level)
    if (!setting) return ''
    return [showMoney ? `+ ${formatCurrencyBRL(setting.feeAmount)}` : '', setting.scheduleLabel]
      .filter(Boolean)
      .join(' · ')
  }

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
        isUrgent,
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
  }, [
    clinicId,
    veterinarianId,
    patient,
    serviceDate,
    collectionMethod,
    serviceLevel,
    isUrgent,
    notes,
  ])

  useEffect(() => {
    attemptCreateDraft()
  }, [attemptCreateDraft])

  // Rascunho retomado: o paciente chega por consulta própria e preenche a tela uma vez.
  useEffect(() => {
    if (resumeAttendance && resumedPatientQuery.data) {
      setPatient((current) => current ?? resumedPatientQuery.data)
    }
  }, [resumeAttendance, resumedPatientQuery.data])

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

  function handleUrgentChange(value: boolean) {
    setIsUrgent(value)
    syncHeaderField({ isUrgent: value })
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

  const preview = examSelections.previewQuery.data

  return (
    <div className="attendance-draft-page">
      <PageHeader
        title={resumeAttendance ? 'Rascunho de protocolo' : 'Novo protocolo'}
        actions={
          resumeAttendance ? (
            <>
              <Link to="/operacao" className="button button--secondary">
                <ArrowLeftIcon />
                Voltar
              </Link>
              {canDiscard && CANCELLABLE_STATUSES.has(resumeAttendance.status) && (
                <Button type="button" variant="cancel" onClick={() => setShowDiscardModal(true)}>
                  Descartar rascunho
                </Button>
              )}
            </>
          ) : undefined
        }
      />

      {!canCreate ? (
        <div className="attendance-draft-page__body">
          <p className="attendance-draft-page__forbidden">
            Você não tem permissão para criar atendimentos.
          </p>
        </div>
      ) : (
        <>
          <div className="attendance-draft-page__body">
            <div className="attendance-draft-page__stack">
              <section className="attendance-draft-page__section" aria-labelledby="draft-requester">
                <h2 id="draft-requester" className="attendance-draft-page__section-title">
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

              <section className="attendance-draft-page__section" aria-labelledby="draft-patient">
                <h2 id="draft-patient" className="attendance-draft-page__section-title">
                  Paciente
                </h2>
                <AttendancePatientSection
                  clinicId={clinicId}
                  selectedPatient={patient}
                  disabled={fieldsDisabled}
                  onSelect={handlePatientSelect}
                  onClear={() => setPatient(null)}
                />
              </section>

              <section className="attendance-draft-page__section" aria-labelledby="draft-service">
                <h2 id="draft-service" className="attendance-draft-page__section-title">
                  Atendimento
                </h2>

                <div className="attendance-draft-page__field-group">
                  <span className="attendance-draft-page__label" id="draft-service-level-label">
                    Tipo de atendimento
                  </span>
                  <div
                    className="attendance-draft-page__toggle-group"
                    role="group"
                    aria-labelledby="draft-service-level-label"
                  >
                    {SERVICE_LEVELS.map((level) => (
                      <button
                        key={level}
                        type="button"
                        className="attendance-draft-page__toggle"
                        data-active={serviceLevel === level}
                        aria-pressed={serviceLevel === level}
                        disabled={fieldsDisabled}
                        onClick={() => handleServiceLevelChange(level)}
                      >
                        <span className="attendance-draft-page__toggle-title">
                          {SERVICE_LEVEL_LABELS[level]}
                        </span>
                        <span className="attendance-draft-page__toggle-subtitle">
                          {describeServiceLevel(level)}
                        </span>
                      </button>
                    ))}
                  </div>
                </div>

                <div className="attendance-draft-page__field-group">
                  <Checkbox
                    id="draft-urgent"
                    label={`Atendimento urgente${showMoney && urgencyFeeLabel ? ` · ${urgencyFeeLabel}` : ''}`}
                    checked={isUrgent}
                    disabled={fieldsDisabled}
                    onChange={(event) => handleUrgentChange(event.target.checked)}
                  />
                </div>

                <div className="attendance-draft-page__field-group">
                  <span className="attendance-draft-page__label" id="draft-collection-label">
                    Forma de coleta
                  </span>
                  <div
                    className="attendance-draft-page__toggle-group attendance-draft-page__toggle-group--flat"
                    role="group"
                    aria-labelledby="draft-collection-label"
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

              <section className="attendance-draft-page__section" aria-labelledby="draft-exams">
                <div className="attendance-draft-page__section-header">
                  <h2 id="draft-exams" className="attendance-draft-page__section-title">
                    Exames
                  </h2>
                  <span className="attendance-draft-page__count">
                    {examSelections.selections.length} selecionado
                    {examSelections.selections.length === 1 ? '' : 's'}
                  </span>
                </div>
                {attendance ? (
                  <>
                    <ExamCartGrid
                      exams={examsQuery.data?.items ?? []}
                      categories={examCategoriesQuery.data ?? []}
                      selections={examSelections.selections}
                      showMoney={showMoney}
                      canDiscount={canOverridePrice}
                      patientSpeciesId={patient?.speciesId ?? null}
                      isLoading={examsQuery.isLoading || examCategoriesQuery.isLoading}
                      isError={examsQuery.isError || examCategoriesQuery.isError}
                      disabled={!attendance || examSelections.isPending}
                      onAdd={examSelections.addExam}
                      onRemove={examSelections.removeExam}
                      onUpdate={examSelections.updateSelection}
                    />
                  </>
                ) : (
                  <p className="attendance-draft-page__hint" role="status">
                    {missingForExams.length > 0
                      ? `Para marcar exames, falta informar: ${missingForExams.join(', ')}.`
                      : 'Preparando o rascunho…'}
                  </p>
                )}
              </section>

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
            </div>
          </div>

          <AttendanceSummaryBar
            examCount={examSelections.selections.length}
            showMoney={showMoney}
            subtotal={preview?.subtotal ?? '0.00'}
            discountTotal={preview?.discountTotal ?? '0.00'}
            fees={preview ? feeRows(preview) : []}
            grandTotal={preview?.grandTotal ?? '0.00'}
            isCalculating={
              examSelections.selections.length > 0 && examSelections.previewQuery.isLoading
            }
            calculationError={describeError(examSelections.previewQuery.error)}
          >
            <Button
              type="button"
              variant="cancel"
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
          </AttendanceSummaryBar>
        </>
      )}

      {showDiscardModal && attendance && (
        <AttendanceCancelModal
          attendance={attendance}
          onClose={() => setShowDiscardModal(false)}
          onCancelled={() => navigate('/operacao')}
        />
      )}
    </div>
  )
}
