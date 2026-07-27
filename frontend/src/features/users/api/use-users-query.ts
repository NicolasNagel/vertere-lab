import { useQuery } from '@tanstack/react-query'

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
