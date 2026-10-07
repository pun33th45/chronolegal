import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { useQuery, useQueryClient, keepPreviousData } from '@tanstack/react-query'
import { motion, AnimatePresence } from 'framer-motion'
import toast from 'react-hot-toast'
import {
  BotMessageSquare,
  Calendar,
  ChevronLeft,
  ChevronRight,
  FileText,
  Gavel,
  Layers,
  Library,
  Scale,
  Search,
  Trash2,
  Upload,
  GitCompareArrows,
} from 'lucide-react'
import { analyticsApi, casesApi, searchApi } from '@/services/api'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { Select } from '@/components/ui/Select'
import { Modal } from '@/components/ui/Modal'
import { Skeleton } from '@/components/ui/Skeleton'
import { EmptyState } from '@/components/ui/EmptyState'
import { ErrorState } from '@/components/ui/ErrorState'
import { PageHeader } from '@/components/ui/PageHeader'
import { MetricCard, MetricCardSkeleton } from '@/components/ui/MetricCard'
import { displayCaseName, courtLabel, formatCount, yearOf } from '@/lib/caseMeta'
import type { LegalCaseSummary } from '@/types'

const PAGE_SIZE = 10

type SortBy = 'recent' | 'name' | 'chunks'

export default function KnowledgeBasePage() {
  const qc = useQueryClient()

  const [searchInput, setSearchInput] = useState('')
  const [q, setQ] = useState('')
  const [court, setCourt] = useState('')
  const [sortBy, setSortBy] = useState<SortBy>('recent')
  const [page, setPage] = useState(1)

  // Debounce the search box so every keystroke doesn't fire a request.
  useEffect(() => {
    const t = setTimeout(() => {
      setQ(searchInput.trim())
      setPage(1)
    }, 350)
    return () => clearTimeout(t)
  }, [searchInput])

  const listParams = {
    page,
    page_size: PAGE_SIZE,
    q: q || undefined,
    court: court || undefined,
    sort_by: sortBy,
  }

  const {
    data: cases,
    isLoading: casesLoading,
    isFetching: casesFetching,
    isError: casesError,
    refetch: refetchCases,
  } = useQuery({
    queryKey: ['knowledge-base', listParams],
    queryFn: () => casesApi.list(listParams),
    // Keep showing the current results while a new search/filter/page
    // request is in flight (DB round trips here can take several real
    // seconds) instead of clearing to a full skeleton grid on every
    // keystroke — isFetching below drives a small inline indicator instead.
    placeholderData: keepPreviousData,
  })

  const { data: totalCount } = useQuery({
    queryKey: ['knowledge-base-count', { q: listParams.q, court: listParams.court }],
    queryFn: () => casesApi.count({ q: listParams.q, court: listParams.court }),
    placeholderData: keepPreviousData,
  })

  // Real aggregate counts across the WHOLE knowledge base (not just the
  // current filtered/paginated page) — the existing analytics endpoint
  // already computes these from the database/Chroma, not fabricated here.
  const { data: stats } = useQuery({
    queryKey: ['analytics', 'dashboard'],
    queryFn: analyticsApi.dashboard,
    staleTime: 60_000,
  })

  const { data: filters } = useQuery({
    queryKey: ['search-filters'],
    queryFn: searchApi.filters,
    staleTime: 5 * 60_000,
  })

  const [chunksCase, setChunksCase] = useState<LegalCaseSummary | null>(null)
  const [deleteCase, setDeleteCase] = useState<LegalCaseSummary | null>(null)
  const [isDeleting, setIsDeleting] = useState(false)
  const deletingRef = useRef(false)

  async function confirmDelete() {
    // Ref, not state: blocks a second click that lands before re-render.
    if (!deleteCase || deletingRef.current) return
    deletingRef.current = true
    setIsDeleting(true)
    const deletedId = deleteCase.case_id
    try {
      await casesApi.delete(deletedId)
      // Remove it from every cached Knowledge Base page right away, then
      // refetch lists, counts and statistics in the background.
      qc.setQueriesData<LegalCaseSummary[]>({ queryKey: ['knowledge-base'] }, (old) =>
        old?.filter((c) => c.case_id !== deletedId),
      )
      // Deleting the last judgment on a later page would otherwise leave an
      // empty page that reads as "no judgments at all".
      if (page > 1 && cases?.length === 1) setPage((p) => p - 1)
      setDeleteCase(null)
      toast.success('Judgment deleted successfully.')
      await Promise.all([
        qc.invalidateQueries({ queryKey: ['knowledge-base'] }),
        qc.invalidateQueries({ queryKey: ['knowledge-base-count'] }),
        qc.invalidateQueries({ queryKey: ['analytics', 'dashboard'] }),
        qc.invalidateQueries({ queryKey: ['cases'] }),
      ])
    } catch (err: unknown) {
      const status = (err as { response?: { status?: number } })?.response?.status
      if (status === 403) {
        toast.error('Only the account that uploaded this judgment can delete it.')
      } else if (status === 404) {
        toast.error('This judgment no longer exists.')
        setDeleteCase(null)
        qc.invalidateQueries({ queryKey: ['knowledge-base'] })
      } else {
        // Modal stays open so the user can retry; nothing was deleted.
        toast.error('Unable to delete this judgment. Please try again.')
      }
    } finally {
      deletingRef.current = false
      setIsDeleting(false)
    }
  }

  const totalPages = totalCount ? Math.max(1, Math.ceil(totalCount / PAGE_SIZE)) : 1
  const hasActiveFilters = !!q || !!court

  return (
    <div className="p-6 md:p-8 max-w-6xl mx-auto space-y-6">
      <PageHeader
        eyebrow="Legal Research Workspace"
        title="Knowledge Base"
        description="Manage the judgments indexed in your legal research knowledge base."
      />

      {/* Stats — each card tracks its own query's loading state
          independently (stats and courts come from separate endpoints with
          different latency), so one being ready never shows next to a
          placeholder dash for another. */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {stats ? (
          <MetricCard icon={FileText} label="Total Judgments" value={stats.total_cases} />
        ) : (
          <MetricCardSkeleton />
        )}
        {stats ? (
          <MetricCard icon={Layers} label="Indexed Chunks" value={stats.total_embeddings} />
        ) : (
          <MetricCardSkeleton />
        )}
        {filters ? (
          <MetricCard icon={Scale} label="Courts" value={filters.courts.length} />
        ) : (
          <MetricCardSkeleton />
        )}
        {stats ? (
          <MetricCard icon={Library} label="Ready / Indexed" value={stats.total_cases} />
        ) : (
          <MetricCardSkeleton />
        )}
      </div>

      {/* Controls */}
      <div className="flex flex-col sm:flex-row gap-3">
        <div className="flex-1 relative">
          <Input
            placeholder="Search judgments by case name..."
            leftIcon={<Search className="w-4 h-4" />}
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
          />
          {casesFetching && !casesLoading && (
            <span className="absolute right-3 top-1/2 -translate-y-1/2 h-3.5 w-3.5 rounded-full border-2 border-primary/30 border-t-primary animate-spin" />
          )}
        </div>
        <div className="w-full sm:w-48">
          <Select
            value={court}
            onChange={(e) => {
              setCourt(e.target.value)
              setPage(1)
            }}
          >
            <option value="">All Courts</option>
            {filters?.courts.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </Select>
        </div>
        <div className="w-full sm:w-48">
          <Select
            value={sortBy}
            onChange={(e) => {
              setSortBy(e.target.value as SortBy)
              setPage(1)
            }}
          >
            <option value="recent">Recently Added</option>
            <option value="name">Case Name</option>
            <option value="chunks">Chunk Count</option>
          </Select>
        </div>
      </div>

      {/* List */}
      {casesLoading ? (
        <div className="space-y-3">
          {Array(4).fill(0).map((_, i) => (
            <Skeleton key={i} className="h-28 rounded-xl" />
          ))}
        </div>
      ) : casesError ? (
        <ErrorState
          description="Unable to load the knowledge base."
          onRetry={() => refetchCases()}
        />
      ) : !cases || cases.length === 0 ? (
        hasActiveFilters ? (
          <EmptyState
            icon={<Search className="w-5 h-5" />}
            title="No judgments match these filters."
            description="Try a different search term or clear the filters."
          />
        ) : (
          <EmptyState
            icon={<Library className="w-5 h-5" />}
            title="No judgments in your knowledge base yet."
            description="Upload a judgment to start researching."
            action={
              <Link to="/upload">
                <Button className="gap-2">
                  <Upload className="w-4 h-4" />
                  Upload Judgment
                </Button>
              </Link>
            }
          />
        )
      ) : (
        <>
          <div className="space-y-3">
            {cases.map((c) => (
              <JudgmentCard
                key={c.case_id}
                caseData={c}
                onViewChunks={() => setChunksCase(c)}
                onDelete={() => setDeleteCase(c)}
              />
            ))}
          </div>

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="flex items-center justify-between pt-2">
              <p className="text-xs text-muted-foreground">
                Page {page} of {totalPages} · {totalCount} judgment{totalCount === 1 ? '' : 's'}
              </p>
              <div className="flex gap-2">
                <Button
                  variant="secondary"
                  size="sm"
                  disabled={page <= 1}
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                >
                  <ChevronLeft className="w-4 h-4" />
                </Button>
                <Button
                  variant="secondary"
                  size="sm"
                  disabled={page >= totalPages}
                  onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                >
                  <ChevronRight className="w-4 h-4" />
                </Button>
              </div>
            </div>
          )}
        </>
      )}

      {/* Chunk Explorer */}
      <ChunkExplorerModal caseData={chunksCase} onClose={() => setChunksCase(null)} />

      {/* Delete confirmation */}
      <Modal
        open={!!deleteCase}
        onClose={() => { if (!isDeleting) setDeleteCase(null) }}
        title="Delete judgment?"
        description="This will remove the judgment and its indexed passages from your knowledge base. This action cannot be undone."
        size="sm"
      >
        {deleteCase && (
          <div className="space-y-4">
            <div className="rounded-lg border border-border bg-muted/30 p-3 text-sm space-y-1">
              <p className="font-medium text-foreground">{displayCaseName(deleteCase.case_name)}</p>
              {deleteCase.source_file && (
                <p className="text-xs text-muted-foreground">{deleteCase.source_file}</p>
              )}
              <p className="text-xs text-muted-foreground">
                {deleteCase.chunk_count} indexed chunk{deleteCase.chunk_count === 1 ? '' : 's'}
              </p>
            </div>
            <div className="flex justify-end gap-2">
              <Button variant="secondary" size="sm" onClick={() => setDeleteCase(null)} disabled={isDeleting}>
                Cancel
              </Button>
              <Button variant="destructive" size="sm" onClick={confirmDelete} loading={isDeleting} disabled={isDeleting}>
                {isDeleting ? 'Deleting…' : 'Delete Judgment'}
              </Button>
            </div>
          </div>
        )}
      </Modal>
    </div>
  )
}

function JudgmentCard({
  caseData,
  onViewChunks,
  onDelete,
}: {
  caseData: LegalCaseSummary
  onViewChunks: () => void
  onDelete: () => void
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      className="legal-card p-4"
    >
      <div className="flex flex-col lg:flex-row lg:items-center gap-4">
        <div className="min-w-0 flex-1">
          <div className="flex items-start gap-2">
            <Link
              to={`/cases/${caseData.case_id}`}
              className="font-serif text-[15px] font-semibold text-foreground leading-snug hover:text-primary transition-colors line-clamp-2 break-words"
            >
              {displayCaseName(caseData.case_name)}
            </Link>
            <Badge variant={caseData.is_embedded ? 'gold' : 'secondary'} className="shrink-0 mt-0.5">
              {caseData.is_embedded ? 'Indexed' : 'Processing'}
            </Badge>
          </div>
          <p className="mt-1 text-sm text-muted-foreground">
            {courtLabel(caseData.court) ?? 'Court not recorded'}
            <span className="mx-1.5 text-border">•</span>
            {yearOf(caseData.judgment_date) ?? 'Year not recorded'}
          </p>
          <div className="flex flex-wrap items-center gap-x-4 gap-y-1 mt-2 text-xs text-muted-foreground">
            <span className="flex items-center gap-1">
              <Layers className="w-3 h-3" /> {formatCount(caseData.chunk_count)} chunks
            </span>
            {caseData.judges && caseData.judges.length > 0 && (
              <span className="flex items-center gap-1 min-w-0">
                <Gavel className="w-3 h-3 shrink-0" />
                <span className="truncate">
                  {caseData.judges.slice(0, 2).join(', ')}
                  {caseData.judges.length > 2 ? ` +${caseData.judges.length - 2}` : ''}
                </span>
              </span>
            )}
            {caseData.source_file && (
              <span className="flex items-center gap-1 min-w-0 max-w-full">
                <FileText className="w-3 h-3 shrink-0" />
                <span className="truncate">{caseData.source_file}</span>
              </span>
            )}
            <span className="flex items-center gap-1">
              <Calendar className="w-3 h-3" /> Added {new Date(caseData.created_at).toLocaleDateString('en-IN')}
            </span>
          </div>
        </div>

        <div className="flex items-center gap-2 flex-shrink-0 flex-wrap">
          <Link to={`/cases/${caseData.case_id}`}>
            <Button variant="secondary" size="sm">View Case</Button>
          </Link>
          <Link to={`/chat?case=${caseData.case_id}&name=${encodeURIComponent(displayCaseName(caseData.case_name))}`}>
            <Button variant="secondary" size="sm" className="gap-1.5">
              <BotMessageSquare className="w-3.5 h-3.5" />
              Research
            </Button>
          </Link>
          <Link to={`/compare?a=${caseData.case_id}`}>
            <Button variant="ghost" size="sm" className="gap-1.5" disabled={!caseData.is_embedded}>
              <GitCompareArrows className="w-3.5 h-3.5" />
              Compare
            </Button>
          </Link>
          <Button variant="ghost" size="sm" onClick={onViewChunks}>
            Chunks
          </Button>
          {/* Shown only when the backend says this user may delete it
              (uploader or admin) — never an action that would just 403. */}
          {caseData.can_delete && (
            <Button
              variant="ghost"
              size="sm"
              onClick={onDelete}
              aria-label={`Delete judgment "${displayCaseName(caseData.case_name)}"`}
              title="Delete this judgment"
              className="gap-1.5 text-muted-foreground hover:text-destructive hover:bg-destructive/10"
            >
              <Trash2 className="w-3.5 h-3.5" />
              Delete
            </Button>
          )}
        </div>
      </div>
    </motion.div>
  )
}

function ChunkExplorerModal({
  caseData,
  onClose,
}: {
  caseData: LegalCaseSummary | null
  onClose: () => void
}) {
  const [page, setPage] = useState(1)

  useEffect(() => {
    if (caseData) setPage(1)
  }, [caseData])

  const { data: chunks, isLoading } = useQuery({
    queryKey: ['case-chunks', caseData?.case_id, page],
    queryFn: () => casesApi.getChunks(caseData!.case_id, page, 10),
    enabled: !!caseData,
  })

  const totalPages = caseData ? Math.max(1, Math.ceil(caseData.chunk_count / 10)) : 1

  return (
    <Modal
      open={!!caseData}
      onClose={onClose}
      title="Indexed Chunks"
      description={caseData ? `${displayCaseName(caseData.case_name)} — split into ${formatCount(caseData.chunk_count)} passages and indexed for retrieval.` : undefined}
      size="lg"
    >
      <div className="space-y-3 max-h-[60vh] overflow-y-auto">
        {isLoading ? (
          Array(5).fill(0).map((_, i) => <Skeleton key={i} className="h-16 rounded-lg" />)
        ) : chunks && chunks.length > 0 ? (
          <AnimatePresence mode="popLayout">
            {chunks.map((chunk) => (
              <motion.div
                key={chunk.id}
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                className="rounded-lg border border-border p-3 text-sm"
              >
                <div className="flex items-center justify-between gap-2 mb-1.5">
                  <span className="text-xs font-semibold text-primary">
                    Passage {chunk.chunk_index + 1}
                  </span>
                  <Link
                    to={`/cases/${caseData!.case_id}?passage=${chunk.chunk_index}`}
                    className="text-[11px] font-medium text-muted-foreground hover:text-primary transition-colors"
                  >
                    Open in judgment →
                  </Link>
                </div>
                <p className="text-foreground/80 text-xs leading-relaxed line-clamp-4">
                  {chunk.content}
                </p>
              </motion.div>
            ))}
          </AnimatePresence>
        ) : (
          <p className="text-sm text-muted-foreground py-6 text-center">No chunks found.</p>
        )}
      </div>

      {totalPages > 1 && (
        <div className="flex items-center justify-between pt-3 mt-3 border-t border-border">
          <p className="text-xs text-muted-foreground">
            Page {page} of {totalPages}
          </p>
          <div className="flex gap-2">
            <Button
              variant="secondary"
              size="sm"
              disabled={page <= 1}
              onClick={() => setPage((p) => Math.max(1, p - 1))}
            >
              <ChevronLeft className="w-4 h-4" />
            </Button>
            <Button
              variant="secondary"
              size="sm"
              disabled={page >= totalPages}
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
            >
              <ChevronRight className="w-4 h-4" />
            </Button>
          </div>
        </div>
      )}
    </Modal>
  )
}
