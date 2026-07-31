import { useQuery } from '@tanstack/react-query'

import { fetchAllPages } from '../../../shared/api/fetch-all-pages'
import { fetchUsers, type UserListParams } from './users-api'

export function usersQueryKey(params: UserListParams) {
  return ['users', params] as const
}

export function useUsersQuery(params: UserListParams = {}) {
  return useQuery({
    queryKey: usersQueryKey(params),
    queryFn: () => fetchUsers(params),
  })
}

export function useAllUsersQuery(params: UserListParams = {}) {
  return useQuery({
    queryKey: ['users', 'all', params],
    queryFn: () => fetchAllPages(fetchUsers, params),
  })
}
