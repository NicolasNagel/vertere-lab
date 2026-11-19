import { ApiError } from '../../../shared/api/errors'
import type { Patient } from '../api/patients-api'

export const PATIENT_STATUS_LABELS: Record<Patient['status'], string> = {
  ACTIVE: 'Ativo',
  INACTIVE: 'Inativo',
}

export const PATIENT_SEX_LABELS: Record<Patient['sex'], string> = {
  MALE: 'Macho',
  FEMALE: 'Fêmea',
}

/** 403 não é "falha de rede": quem não tem `patients.read` precisa saber que é permissão. */
export function patientListErrorMessage(error: unknown): string {
  return error instanceof ApiError && error.status === 403
    ? 'Você não tem permissão para ver pacientes.'
    : 'Não foi possível carregar os pacientes.'
}

/** Falha ao abrir um paciente: 403 (sem `patients.read`) é diferente de 404 (inexistente ou fora
 * do escopo, que o backend não distingue de propósito). */
export function patientLoadErrorMessage(error: unknown): string {
  return error instanceof ApiError && error.status === 403
    ? 'Você não tem permissão para ver este paciente.'
    : 'Paciente não encontrado.'
}

