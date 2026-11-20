import { zodResolver } from '@hookform/resolvers/zod'
import { useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { Controller, useForm } from 'react-hook-form'
import type { z } from 'zod'

import { useSubmitGuard } from '../../../shared/lib/use-submit-guard'
import { BlockFooter } from '../../../shared/ui/detail-block'
import { Dropdown } from '../../../shared/ui/dropdown'
import { ClinicsIcon, PatientsIcon, UserIcon } from '../../../shared/ui/icons'
import { TextField } from '../../../shared/ui/text-field'
import { useAllClinicsQuery } from '../../clinics/api/use-clinics-query'
import type { Patient, PatientFormValues } from '../api/patients-api'
import { patientQueryKey } from '../api/use-patient-query'
import { useSpeciesQuery } from '../api/use-species-query'
import { useUpdatePatientMutation } from '../api/use-update-patient-mutation'
import { PatientAgeField } from './patient-age-field'
import { ageToApi } from './patient-age-schema'
import {
  clinicSchema,
  currentValues,
  identitySchema,
  notesSchema,
  ownerSchema,
  SEX_OPTIONS,
  toFormFields,
} from './patient-fields'

interface FormProps {
  patient: Patient
  onClose: () => void
}

/** O PATCH recebe o conjunto completo: o que o bloco não muda segue como está. */
function usePatientCorrection({ patient, onClose }: FormProps) {
  const mutation = useUpdatePatientMutation()
  const queryClient = useQueryClient()
  const guard = useSubmitGuard()

  function save(changes: Partial<PatientFormValues>, reason?: string) {
    guard((release) =>
      mutation.mutate(
        {
          id: patient.id,
          values: {
            ...currentValues(patient),
            status: patient.status,
            ...changes,
            expectedRowVersion: patient.rowVersion,
            reason,
          },
        },
        { onSuccess: onClose, onSettled: release },
      ),
    )
  }

  // Recarregar descarta o que foi digitado: volta à leitura com o dado novo, para que um novo
  // Salvar nunca reenvie o texto por cima do que outra pessoa gravou sem que o usuário o tenha visto.
  const reload = () => {
    void queryClient.invalidateQueries({ queryKey: patientQueryKey(patient.id) })
    onClose()
  }
  return { mutation, save, reload }
}

function Footer({
  api,
  canSave,
  onSave,
  onClose,
}: {
  api: ReturnType<typeof usePatientCorrection>
  canSave: boolean
  onSave: () => void
  onClose: () => void
}) {
  return (
    <BlockFooter
      canSave={canSave}
      isPending={api.mutation.isPending}
      error={api.mutation.error}
      onReload={api.reload}
      reloadLabel="Recarregar paciente"
      onSave={onSave}
      onCancel={onClose}
    />
  )
}

type IdentityFields = z.infer<typeof identitySchema>

export function IdentityForm(props: FormProps) {
  const { patient, onClose } = props
  const api = usePatientCorrection(props)
  const species = useSpeciesQuery()
  const defaults = toFormFields(patient)
  const {
    register,
    control,
    watch,
    setValue,
    handleSubmit,
    formState: { errors, isDirty },
  } = useForm<IdentityFields>({
    resolver: zodResolver(identitySchema),
    defaultValues: {
      name: defaults.name,
      speciesId: defaults.speciesId,
      sex: defaults.sex,
      breed: defaults.breed,
      ageValue: defaults.ageValue,
      ageUnit: defaults.ageUnit,
    },
  })
  const pending = api.mutation.isPending

  return (
    <div className="attendance-correction-block__form">
      <TextField
        id="patient-edit-name"
        label="Nome do paciente"
        disabled={pending}
        errorMessage={errors.name?.message}
        {...register('name')}
      />
      <Controller
        control={control}
        name="speciesId"
        render={({ field }) => (
          <Dropdown
            variant="field"
            icon={<PatientsIcon />}
            label="Espécie"
            placeholder={species.isLoading ? 'Carregando…' : 'Selecione a espécie'}
            options={(species.data ?? []).map((item) => ({ value: item.id, label: item.name }))}
            value={field.value}
            onChange={field.onChange}
            disabled={pending || species.isLoading}
            errorMessage={errors.speciesId?.message}
          />
        )}
      />
      <Controller
        control={control}
        name="sex"
        render={({ field }) => (
          <Dropdown
            variant="field"
            icon={<UserIcon />}
            label="Sexo"
            options={SEX_OPTIONS}
            value={field.value}
            onChange={field.onChange}
            disabled={pending}
          />
        )}
      />
      <TextField
        id="patient-edit-breed"
        label="Raça"
        disabled={pending}
        errorMessage={errors.breed?.message}
        {...register('breed')}
      />
      <PatientAgeField
        idPrefix="patient-edit"
        value={watch('ageValue')}
        unit={watch('ageUnit')}
        disabled={pending}
        errorMessage={errors.ageValue?.message}
        onValueChange={(value) => setValue('ageValue', value, { shouldDirty: true })}
        onUnitChange={(unit) => setValue('ageUnit', unit, { shouldDirty: true })}
      />
      <Footer
        api={api}
        canSave={isDirty}
        onClose={onClose}
        onSave={handleSubmit((fields) =>
          api.save({
            name: fields.name,
            speciesId: fields.speciesId,
            sex: fields.sex,
            breed: fields.breed || null,
            ...ageToApi(fields),
          }),
        )}
      />
    </div>
  )
}

type OwnerFields = z.infer<typeof ownerSchema>

export function OwnerForm(props: FormProps) {
  const { patient, onClose } = props
  const api = usePatientCorrection(props)
  const defaults = toFormFields(patient)
  const {
    register,
    handleSubmit,
    formState: { errors, isDirty },
  } = useForm<OwnerFields>({
    resolver: zodResolver(ownerSchema),
    defaultValues: {
      ownerName: defaults.ownerName,
      ownerPhone: defaults.ownerPhone,
      ownerDocument: defaults.ownerDocument,
    },
  })
  const pending = api.mutation.isPending

  return (
    <div className="attendance-correction-block__form">
      <TextField
        id="patient-edit-owner-name"
        label="Nome do tutor"
        disabled={pending}
        errorMessage={errors.ownerName?.message}
        {...register('ownerName')}
      />
      <TextField
        id="patient-edit-owner-phone"
        label="Telefone do tutor"
        disabled={pending}
        errorMessage={errors.ownerPhone?.message}
        {...register('ownerPhone')}
      />
      <TextField
        id="patient-edit-owner-document"
        label="Documento do tutor"
        disabled={pending}
        errorMessage={errors.ownerDocument?.message}
        {...register('ownerDocument')}
      />
      <Footer
        api={api}
        canSave={isDirty}
        onClose={onClose}
        onSave={handleSubmit((fields) =>
          api.save({
            ownerName: fields.ownerName,
            ownerPhone: fields.ownerPhone || null,
            ownerDocument: fields.ownerDocument || null,
          }),
        )}
      />
    </div>
  )
}

type NotesFields = z.infer<typeof notesSchema>

export function NotesForm(props: FormProps) {
  const { patient, onClose } = props
  const api = usePatientCorrection(props)
  const {
    register,
    handleSubmit,
    formState: { errors, isDirty },
  } = useForm<NotesFields>({
    resolver: zodResolver(notesSchema),
    defaultValues: { notes: patient.notes ?? '' },
  })

  return (
    <div className="attendance-correction-block__form">
      <TextField
        id="patient-edit-notes"
        label="Observação"
        disabled={api.mutation.isPending}
        errorMessage={errors.notes?.message}
        {...register('notes')}
      />
      <Footer
        api={api}
        canSave={isDirty}
        onClose={onClose}
        onSave={handleSubmit((fields) => api.save({ notes: fields.notes || null }))}
      />
    </div>
  )
}

/** Trocar a clínica exige motivo (auditado). Paciente legado sem clínica recebe uma sem motivo. */
export function ClinicForm(props: FormProps) {
  const { patient, onClose } = props
  const api = usePatientCorrection(props)
  const clinics = useAllClinicsQuery()
  const [clinicId, setClinicId] = useState(patient.clinicId ?? '')
  const [reason, setReason] = useState('')
  const isChange = patient.clinicId !== null && clinicId !== patient.clinicId
  // Mesmos limites do backend: um motivo longo não vira um 422 que o usuário só vê depois de enviar.
  const parsed = clinicSchema.safeParse({ clinicId, reason })
  const reasonError = parsed.success
    ? undefined
    : parsed.error.issues.find((issue) => issue.path[0] === 'reason')?.message
  // Destinos: clínicas ativas e, se estiver inativa, a clínica atual (senão o campo aparece vazio).
  const clinicOptions = (clinics.data?.items ?? [])
    .filter((clinic) => clinic.status === 'ACTIVE' || clinic.id === patient.clinicId)
    .map((clinic) => ({ value: clinic.id, label: clinic.name }))

  return (
    <div className="attendance-correction-block__form">
      <Dropdown
        variant="field"
        searchable
        icon={<ClinicsIcon />}
        label="Clínica"
        placeholder={clinics.isLoading ? 'Carregando…' : 'Selecione a clínica'}
        options={clinicOptions}
        value={clinicId}
        onChange={setClinicId}
        disabled={api.mutation.isPending || clinics.isLoading}
      />
      {isChange && (
        <p className="attendance-readonly-detail__hint">
          Os atendimentos já feitos continuam na clínica em que foram registrados.
        </p>
      )}
      <BlockFooter
        reasonLabel={isChange ? 'Motivo da troca de clínica' : undefined}
        reason={reason}
        onReasonChange={setReason}
        reasonRequired={isChange}
        reasonError={reasonError}
        canSave={clinicId !== '' && clinicId !== (patient.clinicId ?? '') && !reasonError}
        isPending={api.mutation.isPending}
        error={api.mutation.error}
        onReload={api.reload}
        reloadLabel="Recarregar paciente"
        onSave={() => api.save({ clinicId }, isChange ? reason.trim() : undefined)}
        onCancel={onClose}
      />
    </div>
  )
}
