import { Link } from 'react-router-dom'
import { motion } from 'framer-motion'
import { useQuery } from '@tanstack/react-query'
import { BarChart3, Bot, FileUp, Gavel, Layers, Scale, Search } from 'lucide-react'
import { analyticsApi, casesApi } from '@/services/api'
import { useAuthStore } from '@/store/authStore'
import { Button } from '@/components/ui/Button'
import { Skeleton } from '@/components/ui/Skeleton'
import { ErrorState } from '@/components/ui/ErrorState'
import { EmptyState } from '@/components/ui/EmptyState'

const SUGGESTED_PROMPTS = [
  'What are the fundamental rights guaranteed by the Indian Constitution?',
  'Explain the doctrine of promissory estoppel in Indian contract law.',
  'What happened in the Kesavananda Bharati case?',
  'Landmark judgments on Article 21 right to life.',
  'How does the Supreme Court interpret preventive detention laws?',
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
    queryFn: () => casesApi.list({ page_size: 4 }),
  })

  const hour = new Date().getHours()
  const greeting = hour < 12 ? 'Good morning' : hour < 17 ? 'Good afternoon' : 'Good evening'

  const stats = analytics
    ? [
        { label: 'Indexed Cases', value: analytics.total_cases.toLocaleString(), icon: Scale },
        { label: 'Indexed Chunks', value: analytics.total_embeddings.toLocaleString(), icon: Layers },
        { label: 'Available Courts', value: analytics.top_courts.length.toLocaleString(), icon: Gavel },
        { label: 'Total Searches', value: analytics.total_searches.toLocaleString(), icon: Search },
      ]
    : []

  return (
    <div className="p-6 max-w-6xl mx-auto space-y-8">
      {/* Welcome */}
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4 }}
        className="space-y-4"
      >
        <div>
          <h2 className="text-2xl font-bold text-foreground">
            {greeting}, {user?.full_name?.split(' ')[0] || user?.username}
          </h2>
          <p className="text-muted-foreground mt-1 max-w-2xl">
            Upload a judgment, build a searchable legal knowledge base, and ask questions backed by
            retrieved evidence.
          </p>
        </div>
        <div className="flex flex-wrap gap-3">
          <Link to="/upload">
            <Button size="lg" className="gap-2">
              <FileUp className="w-4 h-4" />
              Upload Judgment
            </Button>
          </Link>
          <Link to="/search">
            <Button size="lg" variant="secondary" className="gap-2">
              <Search className="w-4 h-4" />
              Research Cases
            </Button>
          </Link>
        </div>
      </motion.div>

      {/* Knowledge base overview */}
      <div>
        <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider mb-4">
          Knowledge Base
        </h3>
        {analyticsError ? (
          <ErrorState
            variant="banner"
            description="Unable to load knowledge base statistics."
            onRetry={() => refetchAnalytics()}
          />
        ) : (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.2 }}
            className="grid grid-cols-2 md:grid-cols-4 gap-4"
          >
            {analyticsLoading
              ? Array(4)
                  .fill(0)
                  .map((_, i) => <Skeleton key={i} className="h-[76px] rounded-xl" />)
              : stats.map((stat) => (
                  <div key={stat.label} className="glass rounded-xl p-4">
                    <div className="flex items-center justify-between mb-2">
                      <p className="text-xs text-muted-foreground">{stat.label}</p>
                      <stat.icon className="w-4 h-4 text-muted-foreground" />
                    </div>
                    <p className="text-xl font-bold text-foreground">{stat.value}</p>
                  </div>
                ))}
          </motion.div>
        )}
      </div>

      {/* Recent cases */}
      <div>
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider">
            Recent Cases
          </h3>
        </div>
        {casesLoading ? (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {Array(2)
              .fill(0)
              .map((_, i) => <Skeleton key={i} className="h-24 rounded-xl" />)}
          </div>
        ) : recentCases && recentCases.length > 0 ? (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {recentCases.map((c) => (
              <Link key={c.case_id} to={`/cases/${c.case_id}`} className="legal-card block">
                <p className="font-medium text-foreground line-clamp-1">{c.case_name}</p>
                <div className="flex flex-wrap gap-x-3 gap-y-1 mt-2 text-xs text-muted-foreground">
                  {c.court && <span>{c.court}</span>}
                  {c.judgment_date && <span>{c.judgment_date}</span>}
                </div>
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

      {/* Suggested prompts */}
      <div>
        <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider mb-4">
          Suggested Questions
        </h3>
        <div className="space-y-2">
          {SUGGESTED_PROMPTS.map((prompt) => (
            <Link
              key={prompt}
              to={`/chat?q=${encodeURIComponent(prompt)}`}
              className="flex items-center gap-3 p-3 rounded-lg border border-border hover:border-primary/30 hover:bg-primary/5 transition-all group"
            >
              <Bot className="w-4 h-4 text-muted-foreground group-hover:text-primary flex-shrink-0" />
              <span className="text-sm text-muted-foreground group-hover:text-foreground transition-colors">
                {prompt}
              </span>
            </Link>
          ))}
        </div>
      </div>

      {/* Secondary link */}
      <Link to="/analytics" className="flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground transition-colors w-fit">
        <BarChart3 className="w-4 h-4" />
        View corpus analytics & trends
      </Link>
    </div>
  )
}
