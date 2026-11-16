import { z } from 'zod'

import type { PatientAgeUnit } from '../api/patients-api'

export const AGE_LIMITS: Record<PatientAgeUnit, number> = { YEARS: 120, MONTHS: 1440 }

/** Campos de idade dos formulários: número inteiro (texto) + unidade. Vazio é permitido. */
export const ageFieldsShape = {
  ageValue: z.string().trim(),
  ageUnit: z.enum(['YEARS', 'MONTHS']),
}

export function validateAge(
  fields: { ageValue: string; ageUnit: PatientAgeUnit },
  context: z.RefinementCtx,
): void {
  if (fields.ageValue === '') return
  const number = Number(fields.ageValue)
  const limit = AGE_LIMITS[fields.ageUnit]
  if (!/^\d+$/.test(fields.ageValue) || number > limit) {
    context.addIssue({
      code: 'custom',
      path: ['ageValue'],
      message: `Informe um número inteiro de 0 a ${limit}.`,
    })
  }
}

export function ageToApi(fields: { ageValue: string; ageUnit: PatientAgeUnit }): {
  ageValue: number | null
  ageUnit: PatientAgeUnit | null
} {
  if (fields.ageValue === '') return { ageValue: null, ageUnit: null }
  return { ageValue: Number(fields.ageValue), ageUnit: fields.ageUnit }
}

