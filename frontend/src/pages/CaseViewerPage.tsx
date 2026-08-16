import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { useQuery, useMutation } from '@tanstack/react-query'
import { motion } from 'framer-motion'
import {
  Calendar,
  Clock,
  FileText,
  Gavel,
  List,
  Loader2,
  Scale,
  Tag,
} from 'lucide-react'
import { casesApi, summaryApi, nerApi, timelineApi } from '@/services/api'
import { Skeleton } from '@/components/ui/Skeleton'
import { cn } from '@/utils/cn'
import type { SummaryType } from '@/types'

const SUMMARY_TYPES: { value: SummaryType; label: string }[] = [
  { value: 'concise', label: 'Concise' },
  { value: 'detailed', label: 'Detailed' },
  { value: 'bullet', label: 'Bullet Points' },
]

type ViewerTab = 'judgment' | 'entities' | 'timeline' | 'summary'

export default function CaseViewerPage() {
  const { caseId } = useParams<{ caseId: string }>()
  const [activeTab, setActiveTab] = useState<ViewerTab>('judgment')
  const [summaryType, setSummaryType] = useState<SummaryType>('concise')

  const { data: caseData, isLoading } = useQuery({
    queryKey: ['case', caseId],
    queryFn: () => casesApi.get(caseId!),
    enabled: !!caseId,
  })

  const summaryMutation = useMutation({
    mutationFn: () => summaryApi.generate(caseId!, summaryType),
  })

  const nerMutation = useMutation({
    mutationFn: () => nerApi.extract(caseId),
  })

  const { data: timeline } = useQuery({
    queryKey: ['timeline', caseId],
    queryFn: () => timelineApi.get(caseId!),
    enabled: activeTab === 'timeline' && !!caseId,
  })

  const { data: similar } = useQuery({
    queryKey: ['similar', caseId],
    queryFn: () => casesApi.getSimilar(caseId!, 5),
    enabled: !!caseId,
  })

  if (isLoading) {
    return (
      <div className="p-6 space-y-4">
        <Skeleton className="h-8 w-2/3 rounded-lg" />
        <Skeleton className="h-4 w-1/3 rounded" />
        <div className="grid grid-cols-3 gap-4 mt-6">
          {Array(3).fill(0).map((_, i) => <Skeleton key={i} className="h-16 rounded-xl" />)}
        </div>
        <Skeleton className="h-96 rounded-xl" />
      </div>
    )
  }

  if (!caseData) return <div className="p-6 text-muted-foreground">Case not found</div>

  return (
    <div className="flex gap-6 p-6 max-w-7xl mx-auto">
      {/* Main content */}
      <div className="flex-1 space-y-4">
        {/* Header */}
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          className="glass rounded-xl p-6"
        >
          <h1 className="text-xl font-serif font-bold text-foreground mb-3">
            {caseData.case_name}
          </h1>
          <div className="flex flex-wrap gap-4 text-sm text-muted-foreground">
            {caseData.court && (
              <div className="flex items-center gap-1.5">
                <Scale className="w-4 h-4" />
                {caseData.court}
              </div>
            )}
            {caseData.judgment_date && (
              <div className="flex items-center gap-1.5">
                <Calendar className="w-4 h-4" />
                {caseData.judgment_date}
              </div>
            )}
            {caseData.judges && caseData.judges.length > 0 && (
              <div className="flex items-center gap-1.5">
                <Gavel className="w-4 h-4" />
                {caseData.judges.join(', ')}
              </div>
            )}
            {caseData.case_number && (
              <div className="flex items-center gap-1.5">
                <FileText className="w-4 h-4" />
                {caseData.case_number}
              </div>
            )}
          </div>

          {/* Acts */}
          {caseData.acts && caseData.acts.length > 0 && (
            <div className="flex flex-wrap gap-2 mt-4">
              {caseData.acts.map((act) => (
                <span key={act} className="citation-badge">{act}</span>
              ))}
            </div>
          )}
        </motion.div>

        {/* Tabs */}
        <div className="flex gap-1 p-1 bg-card rounded-xl border border-border">
          {[
            { id: 'judgment', label: 'Judgment', icon: FileText },
            { id: 'entities', label: 'Entities', icon: Tag },
            { id: 'timeline', label: 'Timeline', icon: Clock },
            { id: 'summary', label: 'Summary', icon: List },
          ].map((tab) => (
            <button
              key={tab.id}
              onClick={() => {
                setActiveTab(tab.id as ViewerTab)
                if (tab.id === 'entities' && !nerMutation.data) nerMutation.mutate()
              }}
              className={cn(
                'flex-1 flex items-center justify-center gap-1.5 px-3 py-2 rounded-lg text-sm transition-all',
                activeTab === tab.id
                  ? 'bg-primary/15 text-primary font-medium'
                  : 'text-muted-foreground hover:text-foreground',
              )}
            >
              <tab.icon className="w-3.5 h-3.5" />
              {tab.label}
            </button>
          ))}
        </div>

        {/* Tab Content */}
        <div className="glass rounded-xl p-6">
          {activeTab === 'judgment' && (
            <div className="legal-prose">
              {caseData.full_text ? (
                <pre className="whitespace-pre-wrap font-sans text-sm text-foreground leading-relaxed">
                  {caseData.full_text}
                </pre>
              ) : caseData.summary ? (
                <p>{caseData.summary}</p>
              ) : (
                <p className="text-muted-foreground">Full text not available.</p>
              )}
            </div>
          )}

          {activeTab === 'entities' && (
            <div className="space-y-4">
              {nerMutation.isPending && (
                <div className="flex items-center gap-2 text-muted-foreground">
                  <Loader2 className="w-4 h-4 animate-spin" />
                  Extracting entities...
                </div>
              )}
              {nerMutation.data && (
                <div className="grid md:grid-cols-2 gap-4">
                  {Object.entries(nerMutation.data).map(([key, values]) => {
                    if (!Array.isArray(values) || values.length === 0) return null
                    return (
                      <div key={key} className="space-y-2">
                        <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                          {key.replace('_', ' ')}
                        </h4>
                        <div className="flex flex-wrap gap-1.5">
                          {values.map((v: string) => (
                            <span key={v} className="citation-badge">{v}</span>
                          ))}
                        </div>
                      </div>
                    )
                  })}
                </div>
              )}
              {!nerMutation.data && !nerMutation.isPending && (
                <button
                  onClick={() => nerMutation.mutate()}
                  className="px-4 py-2 bg-primary/10 text-primary rounded-lg text-sm hover:bg-primary/20 transition-colors"
                >
                  Extract Entities
                </button>
              )}
            </div>
          )}

          {activeTab === 'timeline' && (
            <div className="space-y-3">
              {!timeline && (
                <div className="flex items-center gap-2 text-muted-foreground">
                  <Loader2 className="w-4 h-4 animate-spin" />
                  Generating timeline...
                </div>
              )}
              {timeline?.map((event, i) => (
                <motion.div
                  key={i}
                  initial={{ opacity: 0, x: -12 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: i * 0.05 }}
                  className="flex gap-4"
                >
                  <div className="flex flex-col items-center">
                    <div className="w-2 h-2 rounded-full bg-primary mt-1.5" />
                    {i < (timeline.length - 1) && (
                      <div className="w-0.5 flex-1 bg-border mt-1" />
                    )}
                  </div>
                  <div className="pb-4">
                    <div className="text-xs text-primary font-medium mb-0.5">{event.date}</div>
                    <div className="text-sm font-medium text-foreground">{event.event}</div>
                    {event.description && (
                      <div className="text-xs text-muted-foreground mt-0.5">{event.description}</div>
                    )}
                  </div>
                </motion.div>
              ))}
              {timeline?.length === 0 && (
                <p className="text-sm text-muted-foreground">No timeline events extracted.</p>
              )}
            </div>
          )}

          {activeTab === 'summary' && (
            <div className="space-y-4">
              <div className="flex gap-2">
                {SUMMARY_TYPES.map((t) => (
                  <button
                    key={t.value}
                    onClick={() => setSummaryType(t.value)}
                    className={cn(
                      'px-3 py-1.5 rounded-lg text-sm transition-colors',
                      summaryType === t.value
                        ? 'bg-primary/15 text-primary'
                        : 'text-muted-foreground hover:text-foreground bg-accent',
                    )}
                  >
                    {t.label}
                  </button>
                ))}
                <button
                  onClick={() => summaryMutation.mutate()}
                  disabled={summaryMutation.isPending}
                  className="ml-auto px-4 py-1.5 bg-primary text-primary-foreground rounded-lg text-sm font-medium hover:bg-primary/90 disabled:opacity-50 flex items-center gap-2"
                >
                  {summaryMutation.isPending && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
                  Generate
                </button>
              </div>

              {summaryMutation.data && (
                <motion.div
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  className="legal-prose"
                >
                  <p className="whitespace-pre-wrap text-sm leading-relaxed">
                    {summaryMutation.data.summary}
                  </p>
                </motion.div>
              )}

              {caseData.summary && !summaryMutation.data && (
                <div className="legal-prose">
                  <p className="text-sm text-muted-foreground italic mb-2">Existing summary:</p>
                  <p className="text-sm leading-relaxed">{caseData.summary}</p>
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Sidebar */}
      <div className="w-72 space-y-4 flex-shrink-0">
        {/* Metadata card */}
        <div className="glass rounded-xl p-4 space-y-3 text-sm">
          <h3 className="font-semibold text-foreground">Case Details</h3>
          {caseData.petitioner && (
            <div>
              <p className="text-xs text-muted-foreground">Petitioner</p>
              <p className="text-foreground">{caseData.petitioner}</p>
            </div>
          )}
          {caseData.respondent && (
            <div>
              <p className="text-xs text-muted-foreground">Respondent</p>
              <p className="text-foreground">{caseData.respondent}</p>
            </div>
          )}
          {caseData.decision_type && (
            <div>
              <p className="text-xs text-muted-foreground">Decision</p>
              <span className="citation-badge">{caseData.decision_type}</span>
            </div>
          )}
          {caseData.text_length && (
            <div>
              <p className="text-xs text-muted-foreground">Text Length</p>
              <p className="text-foreground">{caseData.text_length.toLocaleString()} chars</p>
            </div>
          )}
          <div>
            <p className="text-xs text-muted-foreground">Chunks Indexed</p>
            <p className="text-foreground">{caseData.chunk_count}</p>
          </div>
        </div>

        {/* Sections */}
        {caseData.sections && caseData.sections.length > 0 && (
          <div className="glass rounded-xl p-4 space-y-2">
            <h3 className="font-semibold text-foreground text-sm">Sections</h3>
            <div className="flex flex-wrap gap-1.5">
              {caseData.sections.slice(0, 15).map((s) => (
                <span key={s} className="text-xs px-2 py-0.5 bg-muted rounded text-muted-foreground">
                  {s}
                </span>
              ))}
            </div>
          </div>
        )}

        {/* Similar cases */}
        {similar && similar.length > 0 && (
          <div className="glass rounded-xl p-4 space-y-3">
            <h3 className="font-semibold text-foreground text-sm">Similar Cases</h3>
            {similar.slice(0, 5).map((c) => (
              <a
                key={c.case_id}
                href={`/cases/${c.case_id}`}
                className="block text-xs hover:text-primary transition-colors"
              >
                <p className="font-medium text-foreground">{c.case_name}</p>
                {c.court && <p className="text-muted-foreground">{c.court}</p>}
              </a>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
