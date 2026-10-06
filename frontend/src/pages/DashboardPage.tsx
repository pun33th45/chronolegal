import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import { useQuery } from '@tanstack/react-query'
import { ArrowRight, FileUp, MessageSquareText, Search } from 'lucide-react'
import { analyticsApi, casesApi, chatApi } from '@/services/api'
import { useAuthStore } from '@/store/authStore'
import { Button } from '@/components/ui/Button'
import { Skeleton } from '@/components/ui/Skeleton'
import { ErrorState } from '@/components/ui/ErrorState'
import { courtLabel, displayCaseName, formatCount, formatJudgmentDate } from '@/lib/caseMeta'
import type { AnalyticsDashboard, Conversation, LegalCaseSummary } from '@/types'

const fade = { initial: { opacity: 0, y: 6 }, animate: { opacity: 1, y: 0 }, transition: { duration: 0.2 } }

function relativeTime(iso: string): string {
  const mins = Math.round((Date.now() - new Date(iso).getTime()) / 60_000)
  if (mins < 1) return 'Just now'
  if (mins < 60) return `${mins} min ago`
  const hours = Math.round(mins / 60)
  if (hours < 24) return `${hours} h ago`
  const days = Math.round(hours / 24)
  if (days < 7) return days === 1 ? 'Yesterday' : `${days} days ago`
  return new Date(iso).toLocaleDateString('en-IN', { day: 'numeric', month: 'short' })
}

export default function DashboardPage() {
  const { user } = useAuthStore()

  // Same queries (and cache keys) the Dashboard already used.
  const analytics = useQuery({
    queryKey: ['analytics', 'dashboard'],
    queryFn: analyticsApi.dashboard,
    staleTime: 5 * 60 * 1000,
  })
  const recent = useQuery({
    queryKey: ['cases', 'recent'],
    queryFn: () => casesApi.list({ page_size: 5, sort_by: 'recent' }),
  })
  // The user's own research questions (conversation titles), sharing the
  // Legal AI Chat page's cache entry.
  const conversations = useQuery({
    queryKey: ['conversations'],
    queryFn: () => chatApi.getConversations(),
    staleTime: 30_000,
  })

  const hour = new Date().getHours()
  const greeting = hour < 12 ? 'Good morning' : hour < 17 ? 'Good afternoon' : 'Good evening'
  const firstName = user?.full_name?.split(' ')[0] || user?.username
  const corpusEmpty = analytics.data?.total_cases === 0

  return (
    <div className="px-4 sm:px-6 md:px-8 py-6 md:py-10 max-w-6xl mx-auto">
      <motion.header {...fade} className="mb-8">
        <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-primary mb-2">
          Legal Research Workspace
        </p>
        <h1 className="font-serif text-3xl md:text-[2.5rem] font-bold text-foreground leading-tight">
          {greeting}
          {firstName ? `, ${firstName}` : ''}.
        </h1>
        <p className="text-muted-foreground mt-2 max-w-2xl">
          Search your indexed case law, explore judgments, or start a new research question.
        </p>
      </motion.header>

      {corpusEmpty ? (
        <EmptyCorpus />
      ) : (
        <div className="grid grid-cols-1 xl:grid-cols-12 gap-x-10 gap-y-10">
          <motion.section {...fade} className="xl:col-span-8" aria-label="Start research">
            <ResearchEntry />
          </motion.section>

          <motion.aside {...fade} className="xl:col-span-4" aria-labelledby="kb-heading">
            <KnowledgeBaseSummary
              data={analytics.data}
              loading={analytics.isLoading}
              failed={analytics.isError}
              onRetry={() => analytics.refetch()}
            />
          </motion.aside>

          <motion.section {...fade} className="xl:col-span-8" aria-labelledby="recent-heading">
            <RecentlyIndexed
              cases={recent.data}
              loading={recent.isLoading}
              failed={recent.isError}
              onRetry={() => recent.refetch()}
            />
          </motion.section>

          <motion.aside {...fade} className="xl:col-span-4 space-y-10">
            <RecentResearch conversations={conversations.data} loading={conversations.isLoading} />
            {analytics.data && <CorpusContext data={analytics.data} />}
          </motion.aside>
        </div>
      )}
    </div>
  )
}

// ─── Research entry ──────────────────────────────────────────────────────────

function ResearchEntry() {
  const navigate = useNavigate()
  const [query, setQuery] = useState('')

  function submit(e: React.FormEvent) {
    e.preventDefault()
    const q = query.trim()
    navigate(q ? `/search?q=${encodeURIComponent(q)}` : '/search')
  }

  return (
    <div className="rounded-2xl border border-border bg-card px-5 py-6 sm:px-8 sm:py-8 shadow-sm transition-[box-shadow,border-color] duration-200 focus-within:shadow-md focus-within:border-legal-gold/50">
      <form onSubmit={submit}>
        <label htmlFor="dashboard-research" className="font-serif text-xl sm:text-2xl font-semibold text-foreground">
          What are you researching?
        </label>
        <p className="text-sm text-muted-foreground mt-1.5">
          Search judgments, legal principles, constitutional provisions, or case law.
        </p>
        <div className="mt-5 flex flex-col lg:flex-row gap-3">
          <div className="relative flex-1">
            <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" aria-hidden="true" />
            <input
              id="dashboard-research"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="e.g. basic structure doctrine"
              autoComplete="off"
              className="w-full h-12 pl-11 pr-4 rounded-xl border border-input bg-background text-[15px] text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary transition-colors"
            />
          </div>
          <Button type="submit" size="lg" className="h-12 px-6 gap-2 shrink-0 whitespace-nowrap">
            Search Knowledge Base
            <ArrowRight className="w-4 h-4" />
          </Button>
        </div>
      </form>

      <div className="mt-6 pt-5 border-t border-border flex flex-col lg:flex-row lg:items-center gap-3 lg:justify-between">
        <p className="text-sm text-muted-foreground">
          Prefer to ask a question?{' '}
          <Link to="/chat" className="font-medium text-foreground hover:text-primary transition-colors whitespace-nowrap">
            Open Legal AI Chat →
          </Link>
        </p>
        <Link to="/upload" className="self-start lg:self-auto shrink-0">
          <Button variant="secondary" size="sm" className="gap-1.5 whitespace-nowrap">
            <FileUp className="w-3.5 h-3.5" />
            Upload Judgment
          </Button>
        </Link>
      </div>
    </div>
  )
}

// ─── Knowledge base ──────────────────────────────────────────────────────────

function SectionLabel({ id, children }: { id?: string; children: React.ReactNode }) {
  return (
    <h2 id={id} className="text-[11px] font-semibold uppercase tracking-[0.14em] text-muted-foreground mb-4">
      {children}
    </h2>
  )
}

function KnowledgeBaseSummary({
  data,
  loading,
  failed,
  onRetry,
}: {
  data?: AnalyticsDashboard
  loading: boolean
  failed: boolean
  onRetry: () => void
}) {
  return (
    <div className="xl:pt-2">
      <SectionLabel id="kb-heading">Knowledge Base</SectionLabel>
      {loading ? (
        <div className="space-y-4">
          {Array(3).fill(0).map((_, i) => <Skeleton key={i} className="h-9 w-3/4 rounded-lg" />)}
        </div>
      ) : failed || !data ? (
        <ErrorState variant="banner" description="Unable to load your knowledge base summary." onRetry={onRetry} />
      ) : (
        <>
          <dl className="space-y-4">
            <Figure value={formatCount(data.total_cases)} label={data.total_cases === 1 ? 'judgment' : 'judgments'} />
            <Figure value={formatCount(data.total_embeddings)} label="indexed passages" />
            <Figure
              value={formatCount(data.top_courts.length)}
              label={data.top_courts.length === 1 ? 'court represented' : 'courts represented'}
            />
          </dl>
          <Link
            to="/knowledge-base"
            className="mt-6 inline-flex items-center gap-1.5 text-sm font-medium text-foreground hover:text-primary transition-colors group"
          >
            Explore Knowledge Base
            <ArrowRight className="w-3.5 h-3.5 transition-transform group-hover:translate-x-0.5" />
          </Link>
        </>
      )}
    </div>
  )
}

function Figure({ value, label }: { value: string; label: string }) {
  return (
    <div className="flex items-baseline gap-2.5">
      <dt className="sr-only">{label}</dt>
      <dd className="font-serif text-3xl font-bold text-foreground tabular-nums leading-none">{value}</dd>
      <dd className="text-sm text-muted-foreground" aria-hidden="true">{label}</dd>
    </div>
  )
}

// ─── Recently indexed ────────────────────────────────────────────────────────

function RecentlyIndexed({
  cases,
  loading,
  failed,
  onRetry,
}: {
  cases?: LegalCaseSummary[]
  loading: boolean
  failed: boolean
  onRetry: () => void
}) {
  return (
    <div>
      <div className="flex items-baseline justify-between">
        <SectionLabel id="recent-heading">Recently Indexed</SectionLabel>
        <Link to="/knowledge-base" className="text-xs font-medium text-muted-foreground hover:text-primary transition-colors">
          View all
        </Link>
      </div>

      {loading ? (
        <div className="divide-y divide-border border-y border-border">
          {Array(4).fill(0).map((_, i) => (
            <div key={i} className="py-4 space-y-2">
              <Skeleton className="h-4 w-2/3 rounded" />
              <Skeleton className="h-3 w-1/3 rounded" />
            </div>
          ))}
        </div>
      ) : failed ? (
        <ErrorState variant="banner" description="Unable to load recent judgments." onRetry={onRetry} />
      ) : !cases || cases.length === 0 ? (
        <p className="text-sm text-muted-foreground py-6 border-y border-border">
          No judgments have been indexed yet.{' '}
          <Link to="/upload" className="font-medium text-foreground hover:text-primary">Upload one →</Link>
        </p>
      ) : (
        <ul className="divide-y divide-border border-y border-border">
          {cases.map((c) => {
            const court = courtLabel(c.court)
            const date = formatJudgmentDate(c.judgment_date)
            return (
              <li key={c.case_id}>
                <Link
                  to={`/cases/${c.case_id}`}
                  className="group flex flex-col sm:flex-row sm:items-center gap-1 sm:gap-6 py-4 -mx-3 px-3 rounded-lg hover:bg-accent/50 transition-colors duration-150"
                >
                  <div className="min-w-0 flex-1">
                    <p className="font-serif text-[15px] font-semibold text-foreground leading-snug group-hover:text-primary transition-colors break-words">
                      {displayCaseName(c.case_name)}
                    </p>
                    <p className="text-xs text-muted-foreground mt-1">
                      {court ?? 'Court not recorded'} · {date ?? 'Date not recorded'}
                    </p>
                  </div>
                  <div className="flex items-center gap-4 text-xs text-muted-foreground shrink-0">
                    <span className="tabular-nums">
                      {formatCount(c.chunk_count)} indexed {c.chunk_count === 1 ? 'passage' : 'passages'}
                    </span>
                    <span className="inline-flex items-center gap-1 font-medium text-foreground group-hover:text-primary transition-colors">
                      View case
                      <ArrowRight className="w-3.5 h-3.5 transition-transform group-hover:translate-x-0.5" />
                    </span>
                  </div>
                </Link>
              </li>
            )
          })}
        </ul>
      )}
    </div>
  )
}

// ─── Recent research (the user's own conversations) ──────────────────────────

function RecentResearch({ conversations, loading }: { conversations?: Conversation[]; loading: boolean }) {
  if (loading) {
    return (
      <div>
        <SectionLabel>Recent Research</SectionLabel>
        <div className="space-y-3">
          {Array(3).fill(0).map((_, i) => <Skeleton key={i} className="h-9 rounded-lg" />)}
        </div>
      </div>
    )
  }
  const items = (conversations ?? [])
    .filter((c) => c.message_count > 0 && c.title && c.title !== 'New Conversation')
    .sort((a, b) => b.updated_at.localeCompare(a.updated_at))
    .slice(0, 4)
  if (items.length === 0) return null // no real research history yet

  return (
    <div>
      <SectionLabel>Recent Research</SectionLabel>
      <ul className="space-y-1">
        {items.map((c) => (
          <li key={c.id}>
            <Link
              to={`/chat/${c.id}`}
              className="group flex items-start gap-2.5 -mx-2 px-2 py-2 rounded-lg hover:bg-accent/50 transition-colors duration-150"
            >
              <MessageSquareText className="w-3.5 h-3.5 mt-0.5 text-muted-foreground shrink-0" aria-hidden="true" />
              <span className="min-w-0">
                <span className="block text-sm text-foreground leading-snug line-clamp-2 group-hover:text-primary transition-colors">
                  {c.title}
                </span>
                <span className="block text-[11px] text-muted-foreground mt-0.5">{relativeTime(c.updated_at)}</span>
              </span>
            </Link>
          </li>
        ))}
      </ul>
    </div>
  )
}

// ─── Corpus context ──────────────────────────────────────────────────────────

function CorpusContext({ data }: { data: AnalyticsDashboard }) {
  const years = data.case_trends.map((t) => t.year)
  const span = years.length
    ? years[0] === years[years.length - 1]
      ? `${years[0]}`
      : `${years[0]} – ${years[years.length - 1]}`
    : null
  const court = data.top_courts[0]?.court
  if (!span && !court) return null
  return (
    <div className="border-l-2 border-legal-gold/60 pl-4">
      <SectionLabel>Your Corpus</SectionLabel>
      {span && (
        <p className="text-sm text-foreground">
          Judgments spanning <span className="font-serif font-semibold">{span}</span>
        </p>
      )}
      {court && <p className="text-sm text-muted-foreground mt-1">Mostly from the {court}</p>}
      <Link to="/analytics" className="mt-3 inline-block text-xs font-medium text-muted-foreground hover:text-primary transition-colors">
        View corpus analytics →
      </Link>
    </div>
  )
}

// ─── Empty knowledge base ────────────────────────────────────────────────────

function EmptyCorpus() {
  return (
    <motion.div {...fade} className="rounded-2xl border border-dashed border-legal-gold/40 bg-accent/30 px-6 py-14 text-center">
      <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-primary">Your knowledge base is empty</p>
      <p className="font-serif text-xl sm:text-2xl font-semibold text-foreground mt-3 max-w-lg mx-auto">
        Upload your first judgment to begin building your legal research corpus.
      </p>
      <Link to="/upload" className="inline-block mt-6">
        <Button size="lg" className="gap-2">
          Upload Judgment
          <ArrowRight className="w-4 h-4" />
        </Button>
      </Link>
    </motion.div>
  )
}
