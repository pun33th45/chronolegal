import { useCallback } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import toast from 'react-hot-toast'
import { chatApi } from '@/services/api'

export function useConversations() {
  const qc = useQueryClient()

  const { data: conversations = [], isLoading } = useQuery({
    queryKey: ['conversations'],
    queryFn: () => chatApi.getConversations(1, 50),
    staleTime: 30_000,
  })

  const renameMutation = useMutation({
    mutationFn: ({ id, title }: { id: string; title: string }) =>
      chatApi.updateConversation(id, { title }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['conversations'] }),
    onError: () => toast.error('Failed to rename'),
  })

  const deleteMutation = useMutation({
    mutationFn: (id: string) => chatApi.deleteConversation(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['conversations'] })
      toast.success('Conversation deleted')
    },
    onError: () => toast.error('Failed to delete'),
  })

  const archiveMutation = useMutation({
    mutationFn: (id: string) => chatApi.updateConversation(id, { is_archived: true }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['conversations'] }),
  })

  const rename = useCallback(
    (id: string, title: string) => renameMutation.mutate({ id, title }),
    [renameMutation],
  )

  const remove = useCallback(
    (id: string) => deleteMutation.mutate(id),
    [deleteMutation],
  )

  const archive = useCallback(
    (id: string) => archiveMutation.mutate(id),
    [archiveMutation],
  )

  return { conversations, isLoading, rename, remove, archive }
}
