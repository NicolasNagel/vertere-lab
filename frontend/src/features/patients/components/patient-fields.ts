import { z } from 'zod'

import type { Patient, PatientFormValues } from '../api/patients-api'
import { ageFieldsShape, ageToApi, validateAge } from './patient-age-schema'

/** Mesmos limites do backend (`PatientName`, `OwnerName`, ...): o formulário não envia o que a API recusa. */
const MAX_NAME = 200
const MAX_SHORT_TEXT = 100
const MAX_CONTACT = 30
const MAX_NOTES = 2000
const MAX_REASON = 500

const tooLong = (limit: number) => `Use até ${limit} caracteres.`

export const patientBaseSchema = z.object({
  clinicId: z.string().trim().min(1, 'Selecione a clínica.'),
  name: z.string().trim().min(1, 'Informe o nome do paciente.').max(MAX_NAME, tooLong(MAX_NAME)),
  speciesId: z.string().trim().min(1, 'Selecione a espécie.'),
  sex: z.enum(['MALE', 'FEMALE']),
  breed: z.string().trim().max(MAX_SHORT_TEXT, tooLong(MAX_SHORT_TEXT)),
  ...ageFieldsShape,
  ownerName: z.string().trim().min(1, 'Informe o nome do tutor.').max(MAX_NAME, tooLong(MAX_NAME)),
  ownerPhone: z.string().trim().max(MAX_CONTACT, tooLong(MAX_CONTACT)),
  ownerDocument: z.string().trim().max(MAX_CONTACT, tooLong(MAX_CONTACT)),
  status: z.enum(['ACTIVE', 'INACTIVE']),
  notes: z.string().trim().max(MAX_NOTES, tooLong(MAX_NOTES)),
})

export const patientSchema = patientBaseSchema.superRefine(validateAge)
export type PatientFormFields = z.infer<typeof patientSchema>

export const identitySchema = patientBaseSchema
  .pick({ name: true, speciesId: true, sex: true, breed: true, ageValue: true, ageUnit: true })
  .superRefine(validateAge)
export const ownerSchema = patientBaseSchema.pick({
  ownerName: true,
  ownerPhone: true,
  ownerDocument: true,
})
export const notesSchema = patientBaseSchema.pick({ notes: true })
export const clinicSchema = z.object({
  clinicId: z.string().trim().min(1, 'Selecione a clínica.'),
  reason: z.string().trim().max(MAX_REASON, tooLong(MAX_REASON)),
})

export const SEX_OPTIONS: { value: 'MALE' | 'FEMALE'; label: string }[] = [
  { value: 'MALE', label: 'Macho' },
  { value: 'FEMALE', label: 'Fêmea' },
]

export function toFormFields(patient: Patient | null): PatientFormFields {
  return {
    clinicId: patient?.clinicId ?? '',
    name: patient?.name ?? '',
    speciesId: patient?.speciesId ?? '',
    sex: patient?.sex ?? 'MALE',
    breed: patient?.breed ?? '',
    ageValue:
      patient?.ageValue === null || patient?.ageValue === undefined ? '' : String(patient.ageValue),
    ageUnit: patient?.ageUnit ?? 'YEARS',
    ownerName: patient?.ownerName ?? '',
    ownerPhone: patient?.ownerPhone ?? '',
    ownerDocument: patient?.ownerDocument ?? '',
    status: patient?.status ?? 'ACTIVE',
    notes: patient?.notes ?? '',
  }
}

export function toApiValues(fields: PatientFormFields): PatientFormValues {
  return {
    clinicId: fields.clinicId,
    name: fields.name,
    speciesId: fields.speciesId,
    sex: fields.sex,
    breed: fields.breed || null,
    ...ageToApi(fields),
    ownerName: fields.ownerName,
    ownerPhone: fields.ownerPhone || null,
    ownerDocument: fields.ownerDocument || null,
    notes: fields.notes || null,
  }
}

/** Valores atuais do paciente no formato do PATCH, que recebe sempre o conjunto completo. */
export function currentValues(patient: Patient): PatientFormValues {
  return toApiValues(toFormFields(patient))
}
