import { useState, useCallback } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { searchApi } from '@/services/api'
import { useDebounce } from './useDebounce'
import type { SearchFilters, SearchResponse } from '@/types'

interface UseSearchOptions {
  searchType?: string
  topK?: number
}

export function useSearch(options: UseSearchOptions = {}) {
  const [query, setQuery] = useState('')
  const [filters, setFilters] = useState<SearchFilters>({})
  const debouncedQuery = useDebounce(query, 400)

  const mutation = useMutation({
    mutationFn: (q: string) =>
      searchApi.search({
        query: q,
        top_k: options.topK ?? 10,
        search_type: options.searchType ?? 'hybrid',
        filters: Object.fromEntries(
          Object.entries(filters).filter(([, v]) => v != null && v !== ''),
        ),
      }),
  })

  const search = useCallback(
    (q?: string) => {
      const term = q ?? query
      if (!term.trim()) return
      mutation.mutate(term)
    },
    [query, mutation],
  )

  // Auto-suggest
  const { data: suggestions } = useQuery({
    queryKey: ['suggestions', debouncedQuery],
    queryFn: () => searchApi.suggestions(debouncedQuery, 5),
    enabled: debouncedQuery.length >= 3,
    staleTime: 30_000,
  })

  return {
    query,
    setQuery,
    filters,
    setFilters,
    search,
    results: mutation.data,
    isSearching: mutation.isPending,
    error: mutation.error,
    suggestions: suggestions ?? [],
  }
}
