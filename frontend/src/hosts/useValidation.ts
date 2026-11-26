import { useQuery } from '@tanstack/react-query'
import { api } from '../api/client'
import type { Validation } from '../api/types'

export function useValidation(id: string | null) {
  return useQuery({
    queryKey: ['validation', id],
    queryFn: () => api<Validation>(`/hosts/validations/${id}`),
    enabled: !!id,
    refetchInterval: (q) => (q.state.data?.status === 'running' ? 700 : false),
  })
}
