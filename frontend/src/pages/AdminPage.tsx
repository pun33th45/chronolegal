import { useQuery, useMutation } from '@tanstack/react-query'
import { motion } from 'framer-motion'
import { Database, Loader2, RefreshCw, Search, Server, Users, Zap } from 'lucide-react'
import { adminApi } from '@/services/api'
import { Skeleton } from '@/components/ui/Skeleton'
import toast from 'react-hot-toast'

export default function AdminPage() {
  const { data: stats, isLoading, refetch } = useQuery({
    queryKey: ['admin', 'stats'],
    queryFn: adminApi.stats,
    refetchInterval: 30_000,
  })

  const reindexMutation = useMutation({
    mutationFn: adminApi.reindex,
    onSuccess: (data) => {
      toast.success(`Reindexing started: ${data.task_id}`)
    },
    onError: () => toast.error('Reindex failed'),
  })

  if (isLoading) {
    return (
      <div className="p-6 space-y-4">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {Array(8).fill(0).map((_, i) => <Skeleton key={i} className="h-24 rounded-xl" />)}
        </div>
      </div>
    )
  }

  return (
    <div className="p-6 max-w-6xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold text-foreground">Admin Dashboard</h2>
          <p className="text-sm text-muted-foreground">System overview and controls</p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => refetch()}
            className="flex items-center gap-2 px-3 py-2 rounded-lg border border-border text-sm text-muted-foreground hover:text-foreground transition-colors"
          >
            <RefreshCw className="w-4 h-4" />
            Refresh
          </button>
          <button
            onClick={() => reindexMutation.mutate()}
            disabled={reindexMutation.isPending}
            className="flex items-center gap-2 px-4 py-2 rounded-lg bg-primary text-primary-foreground text-sm font-medium hover:bg-primary/90 disabled:opacity-50 transition-colors"
          >
            {reindexMutation.isPending ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <Zap className="w-4 h-4" />
            )}
            Re-index All
          </button>
        </div>
      </div>

      {stats && (
        <>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {[
              { label: 'Total Cases', value: stats.total_cases.toLocaleString(), icon: Database, color: 'text-primary' },
              { label: 'Embedded Cases', value: stats.embedded_cases.toLocaleString(), icon: Zap, color: 'text-green-400' },
              { label: 'Pending Embedding', value: stats.pending_embedding.toLocaleString(), icon: Loader2, color: 'text-yellow-400' },
              { label: 'Total Chunks', value: stats.total_chunks.toLocaleString(), icon: Server, color: 'text-blue-400' },
              { label: 'ChromaDB Vectors', value: stats.chroma_collection_count.toLocaleString(), icon: Database, color: 'text-purple-400' },
              { label: 'Total Users', value: stats.total_users.toLocaleString(), icon: Users, color: 'text-pink-400' },
              { label: 'Searches Today', value: stats.total_searches_today.toLocaleString(), icon: Search, color: 'text-teal-400' },
              { label: 'Avg Latency', value: `${Math.round(stats.avg_latency_ms)}ms`, icon: Zap, color: 'text-orange-400' },
            ].map((stat, i) => (
              <motion.div
                key={stat.label}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: i * 0.05 }}
                className="glass rounded-xl p-4"
              >
                <div className="flex items-center justify-between mb-2">
                  <p className="text-xs text-muted-foreground">{stat.label}</p>
                  <stat.icon className={`w-4 h-4 ${stat.color}`} />
                </div>
                <p className={`text-xl font-bold ${stat.color}`}>{stat.value}</p>
              </motion.div>
            ))}
          </div>

          {/* Embedding progress */}
          <div className="glass rounded-xl p-6">
            <h3 className="text-sm font-semibold text-foreground mb-4">Embedding Progress</h3>
            <div className="space-y-2">
              <div className="flex justify-between text-xs text-muted-foreground">
                <span>{stats.embedded_cases.toLocaleString()} embedded</span>
                <span>{Math.round(stats.embedded_cases / Math.max(stats.total_cases, 1) * 100)}%</span>
              </div>
              <div className="h-2 bg-muted rounded-full overflow-hidden">
                <div
                  className="h-full bg-primary rounded-full transition-all duration-500"
                  style={{
                    width: `${Math.round(stats.embedded_cases / Math.max(stats.total_cases, 1) * 100)}%`
                  }}
                />
              </div>
              <p className="text-xs text-muted-foreground">
                {stats.pending_embedding} cases pending embedding
              </p>
            </div>
          </div>
        </>
      )}
    </div>
  )
}
