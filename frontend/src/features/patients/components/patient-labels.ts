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
 * do escopo, que o backend não distingue de propósito) e ambos diferem de uma falha do servidor. */
export function patientLoadErrorMessage(error: unknown): string {
  if (error instanceof ApiError && error.status === 403) {
    return 'Você não tem permissão para ver este paciente.'
  }
  if (error instanceof ApiError && error.status === 404) return 'Paciente não encontrado.'
  return 'Não foi possível carregar o paciente. Tente novamente.'
}

