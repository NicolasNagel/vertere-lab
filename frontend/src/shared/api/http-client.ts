import { throwIfNotOk } from './errors'

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? '/api/v1'

export interface ApiRequestOptions extends Omit<RequestInit, 'body'> {
  body?: unknown
}

export async function apiRequest<T>(path: string, options: ApiRequestOptions = {}): Promise<T> {
  const headers = new Headers(options.headers)
  const hasBody = options.body !== undefined
  if (hasBody && !(options.body instanceof FormData)) {
    headers.set('Content-Type', 'application/json')
  }

  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers,
    credentials: 'include',
    body: hasBody
      ? options.body instanceof FormData
        ? options.body
        : JSON.stringify(options.body)
      : undefined,
  })
  await throwIfNotOk(response)
  if (response.status === 204) {
    return undefined as T
  }
  return (await response.json()) as T
}

export function apiUrl(path: string): string {
  return `${API_BASE}${path}`
}
