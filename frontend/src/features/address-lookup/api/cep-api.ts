import { ApiError, throwIfNotOk } from '../../../shared/api/errors'

const API_BASE = '/api/v1'

export interface CepAddress {
  zipCode: string
  street: string | null
  neighborhood: string | null
  city: string | null
  state: string | null
}

interface ApiCepAddress {
  zip_code: string
  street: string | null
  neighborhood: string | null
  city: string | null
  state: string | null
}

function fromApiCepAddress(address: ApiCepAddress): CepAddress {
  return {
    zipCode: address.zip_code,
    street: address.street,
    neighborhood: address.neighborhood,
    city: address.city,
    state: address.state,
  }
}

/** `null` means the CEP was well-formed but not found — an expected result,
 * not an error the caller needs to distinguish from a network failure. */
export async function fetchCepAddress(cep: string): Promise<CepAddress | null> {
  const response = await fetch(`${API_BASE}/address-lookup/cep/${cep}`, {
    credentials: 'include',
  })
  try {
    await throwIfNotOk(response)
  } catch (error) {
    if (error instanceof ApiError && error.code === 'NOT_FOUND') {
      return null
    }
    throw error
  }
  return fromApiCepAddress((await response.json()) as ApiCepAddress)
}
