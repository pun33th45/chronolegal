import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useMutation, useQuery } from '@tanstack/react-query'
import { motion, AnimatePresence } from 'framer-motion'
import { Calendar, ChevronDown, Filter, Loader2, Scale, Search, X } from 'lucide-react'
import { searchApi } from '@/services/api'
import { cn } from '@/utils/cn'
import type { SearchFilters, SearchResult } from '@/types'

const SEARCH_TYPES = [
  { value: 'hybrid', label: 'Hybrid' },
  { value: 'semantic', label: 'Semantic' },
  { value: 'keyword', label: 'Keyword' },
]

export default function SearchPage() {
  const [query, setQuery] = useState('')
  const [searchType, setSearchType] = useState('hybrid')
  const [showFilters, setShowFilters] = useState(false)
  const [filters, setFilters] = useState<SearchFilters>({})
  const [topK, setTopK] = useState(10)

  const { data: filterOptions } = useQuery({
    queryKey: ['search', 'filters'],
    queryFn: searchApi.filters,
  })

  const searchMutation = useMutation({
    mutationFn: () =>
      searchApi.search({
        query,
        top_k: topK,
        search_type: searchType,
        filters: Object.fromEntries(
          Object.entries(filters).filter(([, v]) => v != null && v !== ''),
        ),
      }),
  })

  function handleSearch(e: React.FormEvent) {
    e.preventDefault()
    if (!query.trim()) return
    searchMutation.mutate()
  }

  return (
    <div className="p-6 max-w-5xl mx-auto space-y-6">
      <div>
        <h2 className="text-xl font-bold text-foreground mb-1">Search Legal Cases</h2>
        <p className="text-sm text-muted-foreground">
          Semantic search across thousands of Indian legal judgments
        </p>
      </div>

      {/* Search bar */}
      <form onSubmit={handleSearch} className="space-y-3">
        <div className="flex gap-3">
          <div className="flex-1 relative">
            <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search legal judgments semantically..."
              className="w-full pl-11 pr-4 py-3 bg-card border border-border rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-primary/50 focus:border-primary"
            />
          </div>
          <select
            value={searchType}
            onChange={(e) => setSearchType(e.target.value)}
            className="px-3 py-2 bg-card border border-border rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-primary/50"
          >
            {SEARCH_TYPES.map((t) => (
              <option key={t.value} value={t.value}>{t.label}</option>
            ))}
          </select>
          <button
            type="button"
            onClick={() => setShowFilters(!showFilters)}
            className={cn(
              'flex items-center gap-2 px-4 py-2 rounded-xl border text-sm transition-colors',
              showFilters
                ? 'border-primary bg-primary/10 text-primary'
                : 'border-border text-muted-foreground hover:text-foreground',
            )}
          >
            <Filter className="w-4 h-4" />
            Filters
          </button>
          <button
            type="submit"
            disabled={!query.trim() || searchMutation.isPending}
            className="px-6 py-2 bg-primary text-primary-foreground rounded-xl text-sm font-medium hover:bg-primary/90 disabled:opacity-50 transition-colors flex items-center gap-2"
          >
            {searchMutation.isPending ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <Search className="w-4 h-4" />
            )}
            Search
          </button>
        </div>

        {/* Filters panel */}
        <AnimatePresence>
          {showFilters && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: 'auto' }}
              exit={{ opacity: 0, height: 0 }}
              className="glass rounded-xl p-4 overflow-hidden"
            >
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div>
                  <label className="text-xs font-medium text-muted-foreground mb-1.5 block">Court</label>
                  <select
                    value={filters.court || ''}
                    onChange={(e) => setFilters({ ...filters, court: e.target.value || null })}
                    className="w-full px-3 py-2 bg-card border border-border rounded-lg text-sm"
                  >
                    <option value="">All Courts</option>
                    {filterOptions?.courts?.map((c: string) => (
                      <option key={c} value={c}>{c}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="text-xs font-medium text-muted-foreground mb-1.5 block">Date From</label>
                  <input
                    type="date"
                    value={filters.date_from || ''}
                    onChange={(e) => setFilters({ ...filters, date_from: e.target.value || null })}
                    className="w-full px-3 py-2 bg-card border border-border rounded-lg text-sm"
                  />
                </div>
                <div>
                  <label className="text-xs font-medium text-muted-foreground mb-1.5 block">Date To</label>
                  <input
                    type="date"
                    value={filters.date_to || ''}
                    onChange={(e) => setFilters({ ...filters, date_to: e.target.value || null })}
                    className="w-full px-3 py-2 bg-card border border-border rounded-lg text-sm"
                  />
                </div>
                <div>
                  <label className="text-xs font-medium text-muted-foreground mb-1.5 block">Results</label>
                  <select
                    value={topK}
                    onChange={(e) => setTopK(Number(e.target.value))}
                    className="w-full px-3 py-2 bg-card border border-border rounded-lg text-sm"
                  >
                    {[5, 10, 20, 30, 50].map((n) => (
                      <option key={n} value={n}>Top {n}</option>
                    ))}
                  </select>
                </div>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </form>

      {/* Results */}
      {searchMutation.data && (
        <div className="space-y-4">
          <div className="flex items-center justify-between text-sm text-muted-foreground">
            <span>
              {searchMutation.data.total_results} results in {searchMutation.data.latency_ms}ms
              {searchMutation.data.rewritten_query && (
                <span className="ml-2 text-primary/70">
                  → "{searchMutation.data.rewritten_query}"
                </span>
              )}
            </span>
          </div>

          {searchMutation.data.results.map((result, i) => (
            <SearchResultCard key={result.chunk_id || i} result={result} rank={i + 1} />
          ))}
        </div>
      )}

      {searchMutation.data?.results.length === 0 && (
        <div className="text-center py-16 text-muted-foreground">
          <Scale className="w-12 h-12 mx-auto mb-4 opacity-30" />
          <p>No results found for "{query}"</p>
          <p className="text-sm mt-1">Try different keywords or adjust filters</p>
        </div>
      )}
    </div>
  )
}

function SearchResultCard({ result, rank }: { result: SearchResult; rank: number }) {
  const [expanded, setExpanded] = useState(false)

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: rank * 0.04 }}
      className="legal-card"
    >
      <div className="flex items-start justify-between gap-4">
        <div className="flex items-start gap-3 flex-1">
          <span className="text-xs font-bold text-muted-foreground bg-muted w-6 h-6 rounded flex items-center justify-center flex-shrink-0 mt-0.5">
            {rank}
          </span>
          <div className="flex-1">
            <Link
              to={`/cases/${result.case_id}`}
              className="font-semibold text-foreground hover:text-primary transition-colors"
            >
              {result.case_name}
            </Link>
            <div className="flex flex-wrap gap-2 mt-1.5">
              {result.court && (
                <span className="text-xs text-muted-foreground">{result.court}</span>
              )}
              {result.judgment_date && (
                <span className="text-xs text-muted-foreground flex items-center gap-1">
                  <Calendar className="w-3 h-3" />
                  {result.judgment_date}
                </span>
              )}
              {result.acts?.slice(0, 2).map((act) => (
                <span key={act} className="citation-badge">{act}</span>
              ))}
            </div>

            <p className={cn(
              'text-sm text-muted-foreground mt-2 leading-relaxed',
              !expanded && 'line-clamp-3',
            )}>
              {result.chunk_content}
            </p>
            {result.chunk_content.length > 200 && (
              <button
                onClick={() => setExpanded(!expanded)}
                className="text-xs text-primary hover:underline mt-1"
              >
                {expanded ? 'Show less' : 'Show more'}
              </button>
            )}
          </div>
        </div>

        <div className="text-right flex-shrink-0">
          <div className="text-sm font-semibold text-primary">
            {(result.similarity_score * 100).toFixed(0)}%
          </div>
          <div className="text-xs text-muted-foreground">match</div>
        </div>
      </div>
    </motion.div>
  )
}
