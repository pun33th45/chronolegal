import { Link } from 'react-router-dom'
import { motion } from 'framer-motion'
import { useQuery } from '@tanstack/react-query'
import { BarChart3, Bot, Clock, Scale, Search, TrendingUp } from 'lucide-react'
import { analyticsApi } from '@/services/api'
import { useAuthStore } from '@/store/authStore'

const SUGGESTED_PROMPTS = [
  'What are the fundamental rights guaranteed by the Indian Constitution?',
  'Explain the doctrine of promissory estoppel in Indian contract law.',
  'What happened in the Kesavananda Bharati case?',
  'Landmark judgments on Article 21 right to life.',
  'How does the Supreme Court interpret preventive detention laws?',
]

export default function DashboardPage() {
  const { user } = useAuthStore()
  const { data: analytics } = useQuery({
    queryKey: ['analytics', 'dashboard'],
    queryFn: analyticsApi.dashboard,
    staleTime: 5 * 60 * 1000,
  })

  const hour = new Date().getHours()
  const greeting = hour < 12 ? 'Good morning' : hour < 17 ? 'Good afternoon' : 'Good evening'

  return (
    <div className="p-6 max-w-6xl mx-auto space-y-8">
      {/* Greeting */}
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4 }}
      >
        <h2 className="text-2xl font-bold text-foreground">
          {greeting}, {user?.full_name?.split(' ')[0] || user?.username} 👋
        </h2>
        <p className="text-muted-foreground mt-1">
          What legal question can ChronoLegal AI help you research today?
        </p>
      </motion.div>

      {/* Quick action cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {[
          {
            to: '/chat',
            icon: Bot,
            title: 'Ask Legal AI',
            desc: 'Chat with AI about any legal topic',
            color: 'bg-primary/10 text-primary',
          },
          {
            to: '/search',
            icon: Search,
            title: 'Search Cases',
            desc: 'Semantic search across judgments',
            color: 'bg-legal-teal/10 text-legal-teal',
          },
          {
            to: '/analytics',
            icon: BarChart3,
            title: 'Analytics',
            desc: 'Explore legal trends & insights',
            color: 'bg-purple-500/10 text-purple-400',
          },
        ].map((card, i) => (
          <motion.div
            key={card.to}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.1 }}
          >
            <Link to={card.to} className="legal-card block group hover:scale-[1.02] transition-transform">
              <div className={`w-10 h-10 rounded-lg ${card.color} flex items-center justify-center mb-3`}>
                <card.icon className="w-5 h-5" />
              </div>
              <h3 className="font-semibold text-foreground group-hover:text-primary transition-colors">
                {card.title}
              </h3>
              <p className="text-sm text-muted-foreground mt-1">{card.desc}</p>
            </Link>
          </motion.div>
        ))}
      </div>

      {/* Stats overview */}
      {analytics && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.3 }}
          className="grid grid-cols-2 md:grid-cols-4 gap-4"
        >
          {[
            { label: 'Legal Judgments', value: analytics.total_cases.toLocaleString(), icon: Scale },
            { label: 'Indexed Passages', value: analytics.total_embeddings.toLocaleString(), icon: TrendingUp },
            { label: 'Total Searches', value: analytics.total_searches.toLocaleString(), icon: Search },
            { label: 'Avg Response', value: `${Math.round(analytics.avg_search_latency_ms)}ms`, icon: Clock },
          ].map((stat) => (
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
    </div>
  )
}
