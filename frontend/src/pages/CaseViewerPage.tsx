import { useEffect, useMemo, useRef, useState } from 'react'
import { Link, useParams, useSearchParams } from 'react-router-dom'
import { useQuery, useMutation } from '@tanstack/react-query'
import { motion } from 'framer-motion'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import {
  ArrowRight,
  BotMessageSquare,
  Calendar,
  Clock,
  FileText,
  Gavel,
  List,
  Loader2,
  Quote,
  ScanSearch,
  Scale,
  Tag,
  X,
} from 'lucide-react'
import { casesApi, summaryApi, nerApi, timelineApi } from '@/services/api'
import { Skeleton } from '@/components/ui/Skeleton'
import { EmptyState } from '@/components/ui/EmptyState'
import { ErrorState } from '@/components/ui/ErrorState'
import { cn } from '@/utils/cn'
import type { CasePassage, LegalEntities, SummaryType } from '@/types'
import { displayCaseName } from '@/lib/caseMeta'

const SUMMARY_TYPES: { value: SummaryType; label: string }[] = [
  { value: 'concise', label: 'Concise' },
  { value: 'detailed', label: 'Detailed' },
  { value: 'bullet', label: 'Bullet Points' },
]

type ViewerTab = 'judgment' | 'entities' | 'timeline' | 'summary'

const ENTITY_LABELS: Partial<Record<keyof LegalEntities, string>> = {
  judges: 'Judges',
  courts: 'Courts',
  acts: 'Acts',
  sections: 'Sections',
  organizations: 'Organizations',
  dates: 'Dates',
  locations: 'Locations',
  parties: 'Parties',
}

// Indian Kanoon's raw export prefixes judgments with a citation-count line
// like "[Cites 98, Cited by 467]" — real, useful metadata, but it isn't part
// of the judgment text itself, so it's parsed out of the body and shown as a
// small metadata item instead. If the pattern isn't present, nothing is
// shown or inferred.
function extractCitationCounts(text: string): { cites: string; citedBy: string } | null {
  const m = text.slice(0, 300).match(/\[?\s*Cites\s+(\d+)\s*,?\s*Cited by\s+(\d+)\s*\]?/i)
  if (!m) return null
  return { cites: m[1], citedBy: m[2] }
}

function stripCitationHeader(text: string): string {
  return text.replace(/^\s*\[?\s*Cites\s+\d+\s*,?\s*Cited by\s+\d+\s*\]?\s*/i, '')
}

// The stored text is extracted straight from PDFs/HTML with the source's
// own line wrapping intact (a hard \r\n roughly every 60-80 characters, not
// at paragraph boundaries). Rendering that verbatim with white-space:pre
// produces a wall of oddly short lines instead of real paragraphs, so
// paragraphs are identified by blank-line gaps and the wrapping within each
// one is collapsed to let the browser reflow it naturally — the words
// themselves are never changed.
function splitIntoParagraphs(text: string): string[] {
  return text
    .split(/\r?\n\s*\r?\n/)
    .map((p) => p.replace(/\r?\n/g, ' ').replace(/\s+/g, ' ').trim())
    .filter(Boolean)
}

function formatDate(value: string | null | undefined): string | null {
  if (!value) return null
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return value
  return d.toLocaleDateString('en-GB', { day: 'numeric', month: 'long', year: 'numeric' })
}

export default function CaseViewerPage() {
  const { caseId } = useParams<{ caseId: string }>()
  const [searchParams, setSearchParams] = useSearchParams()
  // ?passage=<chunk index> — set by a citation's "View Source" link.
  const passageParam = searchParams.get('passage')
  const passageIndex = passageParam !== null && /^\d+$/.test(passageParam) ? Number(passageParam) : null
  const [activeTab, setActiveTab] = useState<ViewerTab>('judgment')
  const [summaryType, setSummaryType] = useState<SummaryType>('concise')

  const { data: caseData, isLoading, isError, refetch } = useQuery({
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

  const { data: passage, isLoading: passageLoading, isError: passageError } = useQuery({
    queryKey: ['case-passage', caseId, passageIndex],
    queryFn: () => casesApi.getPassage(caseId!, passageIndex!),
    enabled: !!caseId && passageIndex !== null,
    retry: false,
  })

  const citationCounts = useMemo(
    () => (caseData?.full_text ? extractCitationCounts(caseData.full_text) : null),
    [caseData?.full_text],
  )
  const paragraphs = useMemo(() => {
    if (!caseData?.full_text) return []
    const body = citationCounts ? stripCitationHeader(caseData.full_text) : caseData.full_text
    return splitIntoParagraphs(body)
  }, [caseData?.full_text, citationCounts])

  // The paragraph of the full judgment that contains the referenced passage.
  const highlightedParagraph = useMemo(
    () => (passage ? findPassageParagraph(paragraphs, passage.content) : -1),
    [paragraphs, passage],
  )
  const highlightRef = useRef<HTMLParagraphElement | null>(null)
  useEffect(() => {
    if (highlightedParagraph >= 0 && activeTab === 'judgment') {
      highlightRef.current?.scrollIntoView({ behavior: 'smooth', block: 'center' })
    }
  }, [highlightedParagraph, activeTab])

  function clearPassage() {
    const next = new URLSearchParams(searchParams)
    next.delete('passage')
    setSearchParams(next, { replace: true })
  }

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

  if (isError) {
    return (
      <ErrorState
        description="Unable to retrieve this case from the knowledge base."
        onRetry={() => refetch()}
      />
    )
  }

  if (!caseData) {
    return (
      <EmptyState
        title="Case not found"
        description="This case may have been removed, or the link may be incorrect."
      />
    )
  }

  const formattedDate = formatDate(caseData.judgment_date)

  return (
    <div className="flex flex-col lg:flex-row gap-6 p-6 max-w-7xl mx-auto">
      {/* Main content */}
      <div className="flex-1 min-w-0 space-y-4">
        {/* Header */}
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          className="rounded-xl border border-border bg-card p-6"
        >
          <div className="flex items-center justify-between gap-3 flex-wrap">
            <h1 className="font-serif text-xl font-bold text-foreground">
              {displayCaseName(caseData.case_name)}
            </h1>
            <Link
              to={`/chat?case=${caseData.case_id}&name=${encodeURIComponent(displayCaseName(caseData.case_name))}`}
              className="flex items-center gap-1.5 text-xs font-medium px-3 py-1.5 rounded-lg bg-primary text-primary-foreground hover:bg-primary/90 transition-colors flex-shrink-0"
            >
              <BotMessageSquare className="w-3.5 h-3.5" />
              Research in Chat
              <ArrowRight className="w-3 h-3" />
            </Link>
          </div>
          {caseData.source_file && (
            <span className="inline-flex items-center gap-1.5 text-[11px] text-muted-foreground mt-2.5">
              <ScanSearch className="w-3 h-3" />
              Metadata extracted via NER
            </span>
          )}
        </motion.div>

        {/* Tabs */}
        <div className="flex gap-1 border-b border-border">
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
                'relative flex items-center gap-1.5 px-4 py-2.5 text-sm transition-colors outline-none',
                activeTab === tab.id
                  ? 'text-primary font-medium'
                  : 'text-muted-foreground hover:text-foreground',
              )}
            >
              <tab.icon className="w-3.5 h-3.5" />
              {tab.label}
              {activeTab === tab.id && (
                <motion.div
                  layoutId="case-viewer-tab"
                  className="absolute left-0 right-0 -bottom-px h-0.5 bg-primary rounded-full"
                  transition={{ type: 'spring', stiffness: 400, damping: 30 }}
                />
              )}
            </button>
          ))}
        </div>

        {/* Tab Content */}
        {activeTab === 'judgment' && passageIndex !== null && (
          <ReferencedPassage
            loading={passageLoading}
            failed={passageError}
            passage={passage}
            locatedInJudgment={highlightedParagraph >= 0}
            onJump={() => highlightRef.current?.scrollIntoView({ behavior: 'smooth', block: 'center' })}
            onClose={clearPassage}
          />
        )}

        {activeTab === 'judgment' && (
          <div className="rounded-xl border border-border bg-card overflow-hidden">
            {/* Document header */}
            <div className="px-8 pt-8 pb-6 border-b border-border text-center">
              {caseData.court && (
                <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-3">
                  {caseData.court}
                </p>
              )}
              <h2 className="font-serif text-lg font-bold text-foreground leading-snug max-w-xl mx-auto text-balance">
                {displayCaseName(caseData.case_name)}
              </h2>
              {formattedDate && (
                <p className="text-sm text-muted-foreground mt-2">{formattedDate}</p>
              )}
              {citationCounts && (
                <div className="flex items-center justify-center gap-3 mt-4 text-[11px] text-muted-foreground">
                  <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-muted">
                    <Quote className="w-2.5 h-2.5" />
                    Cites {citationCounts.cites}
                  </span>
                  <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-muted">
                    <Quote className="w-2.5 h-2.5" />
                    Cited by {citationCounts.citedBy}
                  </span>
                </div>
              )}
            </div>

            {/* Document body — a real reflowed document, not a code block */}
            <div className="px-8 py-8">
              {paragraphs.length > 0 ? (
                <div className="max-w-[72ch] mx-auto space-y-4">
                  {paragraphs.map((para, i) => (
                    <p
                      key={i}
                      ref={i === highlightedParagraph ? highlightRef : undefined}
                      className={cn(
                        'text-foreground/90 leading-[1.8] text-[15px]',
                        i === highlightedParagraph &&
                          'rounded-md bg-legal-gold/10 ring-1 ring-legal-gold/40 -mx-3 px-3 py-2 scroll-mt-24',
                      )}
                    >
                      {para}
                    </p>
                  ))}
                </div>
              ) : caseData.summary ? (
                <p className="max-w-[72ch] mx-auto text-foreground/90 leading-[1.8] text-[15px]">
                  {caseData.summary}
                </p>
              ) : (
                <p className="text-muted-foreground text-center py-12">Full text not available.</p>
              )}
            </div>
          </div>
        )}

        {activeTab === 'entities' && (
          <div className="rounded-xl border border-border bg-card p-6">
            {nerMutation.isPending && (
              <div className="flex items-center gap-2 text-muted-foreground text-sm">
                <Loader2 className="w-4 h-4 animate-spin" />
                Extracting entities...
              </div>
            )}
            {nerMutation.data && (
              <div className="grid sm:grid-cols-2 gap-x-8 gap-y-5">
                {(Object.entries(ENTITY_LABELS) as [keyof LegalEntities, string][]).map(([key, label]) => {
                  const list = nerMutation.data?.[key] ?? []
                  return (
                    <div key={key} className="space-y-2">
                      <h4 className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wider">
                        {label}
                      </h4>
                      {list.length > 0 ? (
                        <div className="flex flex-wrap gap-1.5">
                          {/* Real NER extraction can return the same value
                              twice within one category — index is part of
                              the key so that doesn't collide. */}
                          {list.map((v, i) => (
                            <span
                              key={`${key}-${i}`}
                              className="inline-block text-xs px-2 py-1 rounded-md bg-muted text-foreground/80 break-words max-w-full"
                            >
                              {v}
                            </span>
                          ))}
                        </div>
                      ) : (
                        <p className="text-xs text-muted-foreground/70 italic">No entities detected</p>
                      )}
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
          <div className="rounded-xl border border-border bg-card p-6">
            {!timeline && (
              <div className="flex items-center gap-2 text-muted-foreground text-sm">
                <Loader2 className="w-4 h-4 animate-spin" />
                Generating timeline...
              </div>
            )}
            {timeline && timeline.length > 0 && (
              <div className="space-y-0">
                {timeline.map((event, i) => (
                  <motion.div
                    key={i}
                    initial={{ opacity: 0, x: -12 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: i * 0.05 }}
                    className="flex gap-4"
                  >
                    <div className="flex flex-col items-center">
                      <div className="w-2.5 h-2.5 rounded-full bg-primary ring-4 ring-primary/15 mt-1.5 flex-shrink-0" />
                      {i < timeline.length - 1 && (
                        <div className="w-px flex-1 bg-border my-1" />
                      )}
                    </div>
                    <div className="pb-6">
                      <p className="text-xs text-primary font-semibold mb-1">{event.date}</p>
                      <p className="font-serif text-sm font-medium text-foreground">{event.event}</p>
                      {event.description && (
                        <p className="text-xs text-muted-foreground mt-1 leading-relaxed">
                          {event.description}
                        </p>
                      )}
                    </div>
                  </motion.div>
                ))}
              </div>
            )}
            {timeline?.length === 0 && (
              <p className="text-sm text-muted-foreground">No timeline events extracted.</p>
            )}
          </div>
        )}

        {activeTab === 'summary' && (
          <div className="rounded-xl border border-border bg-card p-6 space-y-5">
            <div className="flex flex-wrap items-center gap-2">
              {SUMMARY_TYPES.map((t) => (
                <button
                  key={t.value}
                  onClick={() => setSummaryType(t.value)}
                  className={cn(
                    'px-3 py-1.5 rounded-lg text-sm transition-colors',
                    summaryType === t.value
                      ? 'bg-primary/15 text-primary font-medium'
                      : 'text-muted-foreground hover:text-foreground bg-muted',
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

            {summaryMutation.isPending && (
              <div className="flex items-center gap-2 text-sm text-muted-foreground py-4">
                <Loader2 className="w-4 h-4 animate-spin" />
                Generating case summary...
              </div>
            )}

            {summaryMutation.data && (
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                className="legal-prose max-w-[72ch]"
              >
                <ReactMarkdown remarkPlugins={[remarkGfm]}>
                  {summaryMutation.data.summary}
                </ReactMarkdown>
              </motion.div>
            )}

            {caseData.summary && !summaryMutation.data && !summaryMutation.isPending && (
              <div className="legal-prose max-w-[72ch]">
                <p className="text-sm text-muted-foreground italic mb-2">Existing summary:</p>
                <ReactMarkdown remarkPlugins={[remarkGfm]}>{caseData.summary}</ReactMarkdown>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Sidebar — case dossier */}
      <div className="w-full lg:w-72 space-y-4 flex-shrink-0">
        <SidebarSection title="Case Information">
          <Field label="Court" value={caseData.court} icon={Scale} />
          <Field label="Date" value={formattedDate} icon={Calendar} />
          <Field label="Case Number" value={caseData.case_number} />
          {caseData.decision_type && (
            <div>
              <p className="text-xs text-muted-foreground mb-1">Decision</p>
              <span className="inline-block text-xs px-2 py-0.5 rounded-md bg-muted text-foreground/80">
                {caseData.decision_type}
              </span>
            </div>
          )}
        </SidebarSection>

        {(caseData.petitioner || caseData.respondent || (caseData.parties && caseData.parties.length > 0)) && (
          <SidebarSection title="Parties">
            {caseData.petitioner || caseData.respondent ? (
              <>
                <Field label="Petitioner" value={caseData.petitioner} />
                <Field label="Respondent" value={caseData.respondent} />
              </>
            ) : (
              <Field label="Parties" value={caseData.parties?.join(' v. ')} />
            )}
          </SidebarSection>
        )}

        {caseData.judges && caseData.judges.length > 0 && (
          <SidebarSection title="Judicial Panel">
            <div className="flex items-start gap-1.5">
              <Gavel className="w-3.5 h-3.5 text-muted-foreground flex-shrink-0 mt-0.5" />
              <ul className="space-y-1">
                {caseData.judges.map((j) => (
                  <li key={j} className="text-foreground text-sm">{j}</li>
                ))}
              </ul>
            </div>
          </SidebarSection>
        )}

        {((caseData.acts && caseData.acts.length > 0) || (caseData.sections && caseData.sections.length > 0)) && (
          <SidebarSection title="Legal References">
            {caseData.acts && caseData.acts.length > 0 && (
              <div className="space-y-1.5">
                <p className="text-xs text-muted-foreground">Acts</p>
                <div className="flex flex-wrap gap-1.5">
                  {caseData.acts.map((act, i) => (
                    <span
                      key={`act-${i}`}
                      className="inline-block text-xs px-2 py-1 rounded-md bg-accent text-accent-foreground break-words max-w-full"
                    >
                      {act}
                    </span>
                  ))}
                </div>
              </div>
            )}
            {caseData.sections && caseData.sections.length > 0 && (
              <div className="space-y-1.5">
                <p className="text-xs text-muted-foreground">Sections</p>
                <div className="flex flex-wrap gap-1.5">
                  {caseData.sections.slice(0, 15).map((s, i) => (
                    <span key={`section-${i}`} className="text-xs px-2 py-0.5 bg-muted rounded text-muted-foreground break-words">
                      {s}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </SidebarSection>
        )}

        <SidebarSection title="Document">
          <Field label="Source File" value={caseData.source_file} icon={FileText} />
          <Field label="Indexed Chunks" value={caseData.chunk_count} />
          {caseData.text_length ? (
            <Field label="Text Length" value={`${caseData.text_length.toLocaleString()} chars`} />
          ) : null}
        </SidebarSection>

        {similar && similar.length > 0 && (
          <SidebarSection title="Similar Cases">
            {similar.slice(0, 5).map((c) => (
              <Link
                key={c.case_id}
                to={`/cases/${c.case_id}`}
                className="block text-xs hover:text-primary transition-colors"
              >
                <p className="font-medium text-foreground">{displayCaseName(c.case_name)}</p>
                {c.court && <p className="text-muted-foreground">{c.court}</p>}
              </Link>
            ))}
          </SidebarSection>
        )}
      </div>
    </div>
  )
}

// Locates a retrieved passage inside the reflowed judgment text. Matching is
// whitespace-insensitive on the passage's opening words (chunking can split
// mid-paragraph, so the paragraph may contain the passage or vice versa).
function normalize(text: string): string {
  return text.replace(/\s+/g, ' ').trim().toLowerCase()
}

function findPassageParagraph(paragraphs: string[], passage: string): number {
  const p = normalize(passage)
  if (p.length < 20) return -1
  const head = p.slice(0, 80)
  const byHead = paragraphs.findIndex((para) => normalize(para).includes(head))
  if (byHead >= 0) return byHead
  return paragraphs.findIndex((para) => {
    const n = normalize(para)
    return n.length >= 40 && p.includes(n.slice(0, 80))
  })
}

function ReferencedPassage({
  loading,
  failed,
  passage,
  locatedInJudgment,
  onJump,
  onClose,
}: {
  loading: boolean
  failed: boolean
  passage: CasePassage | undefined
  locatedInJudgment: boolean
  onJump: () => void
  onClose: () => void
}) {
  return (
    <div className="mb-4 rounded-xl border border-legal-gold/40 bg-legal-gold/5 p-4 sm:p-5">
      <div className="flex items-start justify-between gap-3 mb-2">
        <div>
          <p className="text-[11px] font-semibold uppercase tracking-wider text-legal-gold">
            Referenced Passage
          </p>
          {passage && (
            <p className="text-xs text-muted-foreground mt-0.5">
              Passage {passage.chunk_index + 1}
              {passage.page_number ? ` · Page ${passage.page_number}` : ''}
              {passage.section_header ? ` · ${passage.section_header}` : ''}
            </p>
          )}
        </div>
        <button
          type="button"
          onClick={onClose}
          aria-label="Close referenced passage"
          className="rounded-md p-1 text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
        >
          <X className="w-4 h-4" />
        </button>
      </div>

      {loading ? (
        <div className="space-y-2">
          <Skeleton className="h-3 w-full rounded" />
          <Skeleton className="h-3 w-11/12 rounded" />
          <Skeleton className="h-3 w-4/5 rounded" />
        </div>
      ) : failed || !passage ? (
        <p className="text-sm text-muted-foreground">Source information unavailable for this citation.</p>
      ) : (
        <>
          <blockquote className="text-sm text-foreground/90 leading-relaxed border-l-2 border-legal-gold/60 pl-3 whitespace-pre-line max-h-64 overflow-y-auto">
            {passage.content}
          </blockquote>
          {locatedInJudgment && (
            <button
              type="button"
              onClick={onJump}
              className="mt-3 text-xs font-medium text-primary hover:underline"
            >
              Show in full judgment ↓
            </button>
          )}
        </>
      )}
    </div>
  )
}

function SidebarSection({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="rounded-xl border border-border bg-card p-4 space-y-3 text-sm">
      <h3 className="font-semibold text-foreground text-xs uppercase tracking-wider">{title}</h3>
      <div className="space-y-3">{children}</div>
    </div>
  )
}

function Field({
  label,
  value,
  icon: Icon,
}: {
  label: string
  value: string | number | null | undefined
  icon?: React.ElementType
}) {
  if (value === null || value === undefined || value === '') return null
  return (
    <div>
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className="text-foreground flex items-center gap-1.5">
        {Icon && <Icon className="w-3.5 h-3.5 text-muted-foreground flex-shrink-0" />}
        {value}
      </p>
    </div>
  )
}
