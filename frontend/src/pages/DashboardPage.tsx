import { Link } from 'react-router-dom'
import { motion } from 'framer-motion'
import { useQuery } from '@tanstack/react-query'
import {
  ArrowRight,
  BarChart3,
  ChevronRight,
  FileText,
  FileUp,
  Gavel,
  Layers,
  Scale,
  Search,
} from 'lucide-react'
import { analyticsApi, casesApi } from '@/services/api'
import { useAuthStore } from '@/store/authStore'
import { Button } from '@/components/ui/Button'
import { PageHeader } from '@/components/ui/PageHeader'
import { MetricCard, MetricCardSkeleton } from '@/components/ui/MetricCard'
import { ErrorState } from '@/components/ui/ErrorState'
import { EmptyState } from '@/components/ui/EmptyState'

const RESEARCH_STARTERS = [
  'What happened in Kesavananda Bharati v. State of Kerala?',
  'Explain the doctrine of basic structure.',
  'What are the fundamental rights guaranteed under Article 21?',
  'Compare the reasoning across your indexed judgments on preventive detention.',
]

export default function DashboardPage() {
  const { user } = useAuthStore()
  const {
    data: analytics,
    isLoading: analyticsLoading,
    isError: analyticsError,
    refetch: refetchAnalytics,
  } = useQuery({
    queryKey: ['analytics', 'dashboard'],
    queryFn: analyticsApi.dashboard,
    staleTime: 5 * 60 * 1000,
  })

  const { data: recentCases, isLoading: casesLoading } = useQuery({
    queryKey: ['cases', 'recent'],
    queryFn: () => casesApi.list({ page_size: 5, sort_by: 'recent' }),
  })

  const hour = new Date().getHours()
  const greeting = hour < 12 ? 'Good morning' : hour < 17 ? 'Good afternoon' : 'Good evening'
  const firstName = user?.full_name?.split(' ')[0] || user?.username

  const metrics = analytics
    ? [
        { label: 'Indexed Judgments', value: analytics.total_cases.toLocaleString(), icon: Scale },
        { label: 'Indexed Chunks', value: analytics.total_embeddings.toLocaleString(), icon: Layers },
        { label: 'Courts', value: analytics.top_courts.length.toLocaleString(), icon: Gavel },
        { label: 'Research Queries', value: analytics.total_searches.toLocaleString(), icon: Search },
      ]
    : []

  return (
    <div className="p-6 md:p-8 max-w-6xl mx-auto space-y-10">
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.35 }}
      >
        <PageHeader
          eyebrow="Legal Research Workspace"
          title={`${greeting}, ${firstName}`}
          description="Search your indexed judgments, upload new cases, and generate evidence-backed legal answers."
          actions={
            <>
              <Link to="/upload">
                <Button size="lg" className="gap-2">
                  <FileUp className="w-4 h-4" />
                  Upload Judgment
                </Button>
              </Link>
              <Link to="/search">
                <Button size="lg" variant="secondary" className="gap-2">
                  <Search className="w-4 h-4" />
                  Search Knowledge Base
                </Button>
              </Link>
            </>
          }
        />
      </motion.div>

      {/* Knowledge base overview */}
      <div>
        <SectionLabel>Knowledge Base Overview</SectionLabel>
        {analyticsError ? (
          <ErrorState
            variant="banner"
            description="Unable to load knowledge base statistics."
            onRetry={() => refetchAnalytics()}
          />
        ) : (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            {analyticsLoading
              ? Array(4).fill(0).map((_, i) => <MetricCardSkeleton key={i} />)
              : metrics.map((m) => (
                  <MetricCard key={m.label} icon={m.icon} label={m.label} value={m.value} />
                ))}
          </div>
        )}
      </div>

      {/* Recent judgments */}
      <div>
        <div className="flex items-end justify-between mb-3">
          <div>
            <SectionLabel className="mb-0.5">Recent Judgments</SectionLabel>
            <p className="text-xs text-muted-foreground">Recently indexed legal documents</p>
          </div>
          <Link
            to="/knowledge-base"
            className="text-xs font-medium text-primary hover:underline flex items-center gap-1 flex-shrink-0"
          >
            View all
            <ChevronRight className="w-3 h-3" />
          </Link>
        </div>

        {casesLoading ? (
          <div className="rounded-xl border border-border divide-y divide-border overflow-hidden">
            {Array(3).fill(0).map((_, i) => (
              <div key={i} className="flex items-center gap-3 p-4">
                <div className="skeleton h-8 w-8 rounded-lg flex-shrink-0" />
                <div className="flex-1 space-y-2">
                  <div className="skeleton h-3.5 w-1/3 rounded" />
                  <div className="skeleton h-3 w-1/4 rounded" />
                </div>
              </div>
            ))}
          </div>
        ) : recentCases && recentCases.length > 0 ? (
          <div className="rounded-xl border border-border divide-y divide-border overflow-hidden bg-card">
            {recentCases.map((c) => (
              <Link
                key={c.case_id}
                to={`/cases/${c.case_id}`}
                className="flex items-center gap-3 p-4 hover:bg-accent/50 transition-colors group"
              >
                <div className="w-8 h-8 rounded-lg bg-accent flex items-center justify-center flex-shrink-0">
                  <FileText className="w-3.5 h-3.5 text-primary" />
                </div>
                <div className="min-w-0 flex-1">
                  <p className="font-serif font-medium text-foreground truncate">{c.case_name}</p>
                  <div className="flex flex-wrap items-center gap-x-3 gap-y-0.5 mt-0.5 text-xs text-muted-foreground">
                    {c.court && <span>{c.court}</span>}
                    {c.judgment_date && <span>{c.judgment_date}</span>}
                    <span>{c.chunk_count} chunks</span>
                  </div>
                </div>
                <span className="hidden sm:flex items-center gap-1 text-xs font-medium text-muted-foreground group-hover:text-primary transition-colors flex-shrink-0">
                  View Case
                  <ArrowRight className="w-3.5 h-3.5" />
                </span>
              </Link>
            ))}
          </div>
        ) : (
          <EmptyState
            icon={<FileUp className="w-5 h-5" />}
            title="No judgments in the knowledge base yet."
            description="Upload one to make it searchable and ask grounded questions about it."
            action={
              <Link to="/upload">
                <Button size="sm">Upload Judgment</Button>
              </Link>
            }
          />
        )}
      </div>

      {/* Research starters */}
      <div>
        <SectionLabel className="mb-0.5">Research Starters</SectionLabel>
        <p className="text-xs text-muted-foreground mb-3">
          Jump into a research question about your indexed judgments
        </p>
        <div className="grid sm:grid-cols-2 gap-2">
          {RESEARCH_STARTERS.map((prompt) => (
            <Link
              key={prompt}
              to={`/chat?q=${encodeURIComponent(prompt)}`}
              className="flex items-center gap-3 p-3.5 rounded-lg border border-border bg-card hover:border-primary/40 hover:bg-accent/40 transition-all group"
            >
              <span className="text-sm text-foreground/90 flex-1 leading-snug">{prompt}</span>
              <ArrowRight className="w-3.5 h-3.5 text-muted-foreground group-hover:text-primary group-hover:translate-x-0.5 transition-all flex-shrink-0" />
            </Link>
          ))}
        </div>
      </div>

      <Link
        to="/analytics"
        className="flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground transition-colors w-fit"
      >
        <BarChart3 className="w-4 h-4" />
        View corpus analytics & trends
      </Link>
    </div>
  )
}

function SectionLabel({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <p className={`text-xs font-semibold text-muted-foreground uppercase tracking-wider ${className ?? ''}`}>
      {children}
    </p>
  )
}
