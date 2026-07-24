export interface ApiErrorBody {
  error?: {
    code?: string
    message?: string
    details?: { field: string; reason: string }[]
  }
}

/** Erro de domínio vindo do backend — nunca confundir com falha de rede. */
export class ApiError extends Error {
  readonly status: number
  readonly code: string
  readonly details: { field: string; reason: string }[]

  constructor(
    status: number,
    code: string,
    message: string,
    details: { field: string; reason: string }[] = [],
  ) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
    this.details = details
  }
}

export async function throwIfNotOk(response: Response): Promise<void> {
  if (response.ok) {
    return
  }
  const body = (await response.json().catch(() => null)) as ApiErrorBody | null
  throw new ApiError(
    response.status,
    body?.error?.code ?? 'UNKNOWN',
    body?.error?.message ?? 'Erro desconhecido.',
    body?.error?.details ?? [],
  )
}
