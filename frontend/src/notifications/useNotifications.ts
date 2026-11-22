import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '../api/client'
import type { Notification } from '../api/types'

export function useNotificationCount() {
  return useQuery({
    queryKey: ['notifications', 'count'],
    queryFn: () => api<{ new: number }>('/notifications/count'),
    refetchInterval: 15_000,
  })
}

export function useNotifications(history = false) {
  const qc = useQueryClient()
  const list = useQuery({
    queryKey: ['notifications', history ? 'history' : 'new'],
    queryFn: () => api<Notification[]>(history ? '/notifications/history' : '/notifications'),
    refetchInterval: history ? false : 15_000,
  })
  const invalidate = () => void qc.invalidateQueries({ queryKey: ['notifications'] })
  const seen = useMutation({ mutationFn: (id: string) => api(`/notifications/${id}/seen`, { method: 'POST' }), onSuccess: invalidate })
  const seenAll = useMutation({ mutationFn: () => api('/notifications/seen-all', { method: 'POST' }), onSuccess: invalidate })
  return { list, seen, seenAll }
}
