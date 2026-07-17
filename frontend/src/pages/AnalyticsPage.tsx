import { useQuery } from '@tanstack/react-query'
import { motion } from 'framer-motion'
import {
  Bar,
  BarChart,
  Cell,
  Legend,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { analyticsApi } from '@/services/api'
import { Skeleton } from '@/components/ui/Skeleton'

const COLORS = ['#C8A951', '#0E7C7B', '#6366f1', '#ec4899', '#f97316', '#84cc16']

export default function AnalyticsPage() {
  const { data, isLoading } = useQuery({
    queryKey: ['analytics', 'dashboard'],
    queryFn: analyticsApi.dashboard,
  })

  if (isLoading) {
    return (
      <div className="p-6 space-y-6">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {Array(4).fill(0).map((_, i) => (
            <Skeleton key={i} className="h-24 rounded-xl" />
          ))}
        </div>
        <div className="grid md:grid-cols-2 gap-6">
          {Array(4).fill(0).map((_, i) => (
            <Skeleton key={i} className="h-64 rounded-xl" />
          ))}
        </div>
      </div>
    )
  }

  if (!data) return null

  return (
    <div className="p-6 space-y-6 max-w-7xl mx-auto">
      <div>
        <h2 className="text-xl font-bold text-foreground mb-1">Legal Analytics</h2>
        <p className="text-sm text-muted-foreground">
          Insights from the ChronoLegal corpus
        </p>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {[
          { label: 'Total Cases', value: data.total_cases.toLocaleString() },
          { label: 'Indexed Chunks', value: data.total_embeddings.toLocaleString() },
          { label: 'Total Users', value: data.total_users.toLocaleString() },
          { label: 'Total Searches', value: data.total_searches.toLocaleString() },
        ].map((s, i) => (
          <motion.div
            key={s.label}
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.08 }}
            className="glass rounded-xl p-4"
          >
            <p className="text-xs text-muted-foreground mb-1">{s.label}</p>
            <p className="text-2xl font-bold gold-text">{s.value}</p>
          </motion.div>
        ))}
      </div>

      <div className="grid md:grid-cols-2 gap-6">
        {/* Case Trends */}
        <div className="glass rounded-xl p-5">
          <h3 className="text-sm font-semibold text-foreground mb-4">Case Volume by Year</h3>
          <ResponsiveContainer width="100%" height={220}>
            <LineChart data={data.case_trends}>
              <XAxis dataKey="year" tick={{ fill: '#64748b', fontSize: 11 }} />
              <YAxis tick={{ fill: '#64748b', fontSize: 11 }} />
              <Tooltip
                contentStyle={{
                  background: 'hsl(222, 47%, 8%)',
                  border: '1px solid hsl(217, 33%, 18%)',
                  borderRadius: '8px',
                  color: '#fff',
                }}
              />
              <Line
                type="monotone"
                dataKey="count"
                stroke="#C8A951"
                strokeWidth={2}
                dot={{ fill: '#C8A951', r: 3 }}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>

        {/* Top Courts */}
        <div className="glass rounded-xl p-5">
          <h3 className="text-sm font-semibold text-foreground mb-4">Top Courts</h3>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={data.top_courts.slice(0, 8)} layout="vertical">
              <XAxis type="number" tick={{ fill: '#64748b', fontSize: 11 }} />
              <YAxis
                dataKey="court"
                type="category"
                width={140}
                tick={{ fill: '#64748b', fontSize: 10 }}
                tickFormatter={(v: string) => v.length > 20 ? v.slice(0, 20) + '…' : v}
              />
              <Tooltip
                contentStyle={{
                  background: 'hsl(222, 47%, 8%)',
                  border: '1px solid hsl(217, 33%, 18%)',
                  borderRadius: '8px',
                  color: '#fff',
                }}
              />
              <Bar dataKey="count" fill="#C8A951" radius={[0, 4, 4, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* Top Acts */}
        <div className="glass rounded-xl p-5">
          <h3 className="text-sm font-semibold text-foreground mb-4">Most Referenced Acts</h3>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={data.top_acts.slice(0, 10)}>
              <XAxis
                dataKey="name"
                tick={{ fill: '#64748b', fontSize: 9 }}
                tickFormatter={(v: string) => v.length > 15 ? v.slice(0, 15) + '…' : v}
                angle={-20}
                textAnchor="end"
              />
              <YAxis tick={{ fill: '#64748b', fontSize: 11 }} />
              <Tooltip
                contentStyle={{
                  background: 'hsl(222, 47%, 8%)',
                  border: '1px solid hsl(217, 33%, 18%)',
                  borderRadius: '8px',
                  color: '#fff',
                }}
              />
              <Bar dataKey="count" fill="#0E7C7B" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* Decision Types */}
        <div className="glass rounded-xl p-5">
          <h3 className="text-sm font-semibold text-foreground mb-4">Decision Types</h3>
          {data.decision_types.length > 0 ? (
            <ResponsiveContainer width="100%" height={220}>
              <PieChart>
                <Pie
                  data={data.decision_types}
                  dataKey="count"
                  nameKey="decision_type"
                  cx="50%"
                  cy="50%"
                  outerRadius={80}
                  label={({ decision_type, percentage }) =>
                    `${decision_type?.slice(0, 10)} (${percentage?.toFixed(1)}%)`
                  }
                  labelLine={false}
                >
                  {data.decision_types.map((_, i) => (
                    <Cell key={i} fill={COLORS[i % COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip
                  contentStyle={{
                    background: 'hsl(222, 47%, 8%)',
                    border: '1px solid hsl(217, 33%, 18%)',
                    borderRadius: '8px',
                    color: '#fff',
                  }}
                />
              </PieChart>
            </ResponsiveContainer>
          ) : (
            <div className="flex items-center justify-center h-[220px] text-muted-foreground text-sm">
              No decision type data yet
            </div>
          )}
        </div>
      </div>

      {/* Top Keywords */}
      <div className="glass rounded-xl p-5">
        <h3 className="text-sm font-semibold text-foreground mb-4">Top Legal Keywords</h3>
        <div className="flex flex-wrap gap-2">
          {data.top_keywords.map((kw, i) => {
            const size = Math.max(0.7, Math.min(1.4, kw.count / (data.top_keywords[0]?.count || 1) * 1.4))
            return (
              <span
                key={kw.name}
                className="px-3 py-1.5 rounded-full border border-primary/20 bg-primary/5 text-primary cursor-default transition-colors hover:bg-primary/15"
                style={{ fontSize: `${size * 0.875}rem` }}
              >
                {kw.name}
                <span className="text-primary/50 ml-1 text-xs">({kw.count})</span>
              </span>
            )
          })}
        </div>
      </div>
    </div>
  )
}
