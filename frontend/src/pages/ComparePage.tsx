import { useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { useMutation, useQuery } from '@tanstack/react-query'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { AlertTriangle, ArrowLeftRight, GitCompareArrows, Loader2, Upload } from 'lucide-react'
import { casesApi, compareApi } from '@/services/api'
import { Button } from '@/components/ui/Button'
import { PageHeader } from '@/components/ui/PageHeader'
import { EmptyState } from '@/components/ui/EmptyState'
import { Skeleton } from '@/components/ui/Skeleton'
import { CitationCard } from '@/components/chat/CitationCard'
import { courtLabel, displayCaseName, formatCount, yearOf } from '@/lib/caseMeta'
import { cn } from '@/utils/cn'
import type { Citation, LegalCase, LegalCaseSummary } from '@/types'

function errorMessage(err: unknown): string {
  const detail = (err as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail
  return typeof detail === 'string' ? detail : 'The comparison could not be completed. Please try again.'
}

// Several uploads can share a title; add the date they were added so the
// two options stay distinguishable without exposing internal ids.
function optionLabels(cases: LegalCaseSummary[]): Map<string, string> {
  const counts = new Map<string, number>()
  cases.forEach((c) => counts.set(c.case_name, (counts.get(c.case_name) ?? 0) + 1))
  return new Map(
    cases.map((c) => {
      const extra = [courtLabel(c.court), yearOf(c.judgment_date)].filter(Boolean).join(', ')
      const name = displayCaseName(c.case_name)
      let label = extra ? `${name} (${extra})` : name
      if ((counts.get(c.case_name) ?? 0) > 1) {
        label += ` — added ${new Date(c.created_at).toLocaleDateString('en-IN')}`
      }
      return [c.case_id, label]
    }),
  )
}

export default function ComparePage() {
  const [params, setParams] = useSearchParams()
  const [caseA, setCaseA] = useState(params.get('a') ?? '')
  const [caseB, setCaseB] = useState(params.get('b') ?? '')
  const [question, setQuestion] = useState('')

  const { data: cases, isLoading: casesLoading } = useQuery({
    queryKey: ['compare-case-options'],
    queryFn: () => casesApi.list({ page_size: 100, sort_by: 'name' }),
  })
  const indexed = useMemo(() => (cases ?? []).filter((c) => c.is_embedded), [cases])
  const labels = useMemo(() => optionLabels(indexed), [indexed])

  const { data: detailA } = useQuery({
    queryKey: ['case', caseA],
    queryFn: () => casesApi.get(caseA),
    enabled: !!caseA,
  })
  const { data: detailB } = useQuery({
    queryKey: ['case', caseB],
    queryFn: () => casesApi.get(caseB),
    enabled: !!caseB,
  })

  const comparison = useMutation({
    mutationFn: () => compareApi.compare(caseA, caseB, question.trim() || undefined),
  })

  const sameCase = !!caseA && caseA === caseB
  const canCompare = !!caseA && !!caseB && !sameCase && !comparison.isPending

  function select(side: 'a' | 'b', value: string) {
    if (side === 'a') setCaseA(value)
    else setCaseB(value)
    comparison.reset()
    const next = new URLSearchParams(params)
    if (value) next.set(side, value)
    else next.delete(side)
    setParams(next, { replace: true })
  }

  function swap() {
    setCaseA(caseB)
    setCaseB(caseA)
    comparison.reset()
    const next = new URLSearchParams(params)
    if (caseB) next.set('a', caseB)
    else next.delete('a')
    if (caseA) next.set('b', caseA)
    else next.delete('b')
    setParams(next, { replace: true })
  }

  const citationsA = comparison.data?.citations.filter((c) => c.case_id === caseA) ?? []
  const citationsB = comparison.data?.citations.filter((c) => c.case_id === caseB) ?? []

  return (
    <div className="max-w-5xl mx-auto px-4 sm:px-6 py-6 space-y-6">
      <PageHeader
        eyebrow="Legal Research Workspace"
        title="Case Comparison"
        description="Compare two judgments from your knowledge base, with every point grounded in passages from the judgments themselves."
      />

      {casesLoading ? (
        <Skeleton className="h-40 rounded-xl" />
      ) : indexed.length < 2 ? (
        <EmptyState
          icon={<Upload className="w-5 h-5" />}
          title="Not enough judgments to compare"
          description="Comparison needs at least two indexed judgments in your knowledge base. Upload a judgment to get started."
          action={
            <Link to="/upload">
              <Button size="sm">Upload Judgment</Button>
            </Link>
          }
        />
      ) : (
        <div className="legal-card space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-[1fr_auto_1fr] gap-3 md:items-end">
            <CaseSelect label="Case A" value={caseA} onChange={(v) => select('a', v)} cases={indexed} labels={labels} />
            <button
              type="button"
              onClick={swap}
              disabled={!caseA && !caseB}
              aria-label="Swap cases"
              className="mx-auto md:mb-1 flex h-9 w-9 items-center justify-center rounded-full border border-border text-muted-foreground hover:text-foreground hover:bg-muted disabled:opacity-40 transition-colors"
            >
              <ArrowLeftRight className="w-4 h-4" />
            </button>
            <CaseSelect label="Case B" value={caseB} onChange={(v) => select('b', v)} cases={indexed} labels={labels} />
          </div>

          <div>
            <label htmlFor="compare-question" className="block text-xs font-medium text-muted-foreground mb-1.5">
              Comparison question <span className="font-normal">(optional)</span>
            </label>
            <input
              id="compare-question"
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              maxLength={500}
              placeholder="e.g. How do these judgments treat Parliament's power to amend the Constitution?"
              className="w-full h-10 px-3 bg-card border border-input rounded-lg text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary/40 focus:border-primary transition-colors"
            />
          </div>

          <div className="flex flex-col sm:flex-row sm:items-center gap-3 sm:justify-between">
            <p className="text-xs text-muted-foreground">
              {sameCase
                ? 'Select two different judgments to compare.'
                : !caseA || !caseB
                  ? 'Select two judgments to compare.'
                  : 'Evidence is retrieved separately from each judgment before the comparison is written.'}
            </p>
            <Button onClick={() => comparison.mutate()} disabled={!canCompare} loading={comparison.isPending} className="gap-2 shrink-0">
              <GitCompareArrows className="w-4 h-4" />
              Compare Cases
            </Button>
          </div>
        </div>
      )}

      {caseA && caseB && !sameCase && <MetadataTable a={detailA} b={detailB} />}

      {comparison.isPending && (
        <div className="legal-card flex items-start gap-3" aria-live="polite">
          <Loader2 className="w-4 h-4 mt-0.5 text-primary animate-spin shrink-0" />
          <div>
            <p className="text-sm font-medium text-foreground">Comparing judgments…</p>
            <p className="text-xs text-muted-foreground mt-0.5">
              Retrieving and ranking evidence from both judgments, then writing a cited comparison. This
              usually takes 20–40 seconds.
            </p>
          </div>
        </div>
      )}

      {comparison.isError && (
        <div className="legal-card flex items-start gap-3 border-destructive/30">
          <AlertTriangle className="w-4 h-4 mt-0.5 text-destructive shrink-0" />
          <p className="text-sm text-foreground">{errorMessage(comparison.error)}</p>
        </div>
      )}

      {comparison.data && (
        <div className="space-y-4">
          <div className="legal-card">
            <p className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground mb-3">
              How are these judgments related?
            </p>
            {comparison.data.sufficient_context ? (
              <div className="prose prose-sm max-w-none prose-headings:font-serif prose-headings:text-foreground prose-h3:text-base prose-h3:mt-5 first:prose-h3:mt-0 prose-p:text-foreground/90 prose-li:text-foreground/90">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>{comparison.data.answer}</ReactMarkdown>
              </div>
            ) : (
              <div className="flex items-start gap-2.5 rounded-lg bg-amber-500/10 border border-amber-500/30 p-3">
                <AlertTriangle className="w-4 h-4 mt-0.5 text-amber-600 shrink-0" />
                <p className="text-sm text-foreground">{comparison.data.answer}</p>
              </div>
            )}
          </div>

          {comparison.data.sufficient_context && (
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              <EvidenceColumn title="Evidence from Case A" caseName={detailA && displayCaseName(detailA.case_name)} citations={citationsA} />
              <EvidenceColumn title="Evidence from Case B" caseName={detailB && displayCaseName(detailB.case_name)} citations={citationsB} />
            </div>
          )}
        </div>
      )}
    </div>
  )
}

function CaseSelect({
  label,
  value,
  onChange,
  cases,
  labels,
}: {
  label: string
  value: string
  onChange: (v: string) => void
  cases: LegalCaseSummary[]
  labels: Map<string, string>
}) {
  const id = `compare-${label.replace(' ', '-').toLowerCase()}`
  return (
    <div className="min-w-0">
      <label htmlFor={id} className="block text-xs font-medium text-muted-foreground mb-1.5">
        {label}
      </label>
      <select
        id={id}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-full h-10 px-3 bg-card border border-input rounded-lg text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-primary/40 focus:border-primary transition-colors truncate"
      >
        <option value="">Select a judgment…</option>
        {cases.map((c) => (
          <option key={c.case_id} value={c.case_id}>
            {labels.get(c.case_id) ?? displayCaseName(c.case_name)}
          </option>
        ))}
      </select>
    </div>
  )
}

const NOT_RECORDED = 'Not recorded'

function listOrFallback(items: string[] | null | undefined, max = 4): string {
  if (!items || items.length === 0) return NOT_RECORDED
  return items.length > max ? `${items.slice(0, max).join(', ')} +${items.length - max} more` : items.join(', ')
}

function MetadataTable({ a, b }: { a?: LegalCase; b?: LegalCase }) {
  if (!a || !b) {
    return <Skeleton className="h-48 rounded-xl" />
  }
  const rows: { label: string; a: string; b: string }[] = [
    { label: 'Court', a: courtLabel(a.court) ?? NOT_RECORDED, b: courtLabel(b.court) ?? NOT_RECORDED },
    { label: 'Year', a: yearOf(a.judgment_date) ?? NOT_RECORDED, b: yearOf(b.judgment_date) ?? NOT_RECORDED },
    {
      label: 'Bench',
      a: a.judges?.length ? `${a.judges.length} judge${a.judges.length === 1 ? '' : 's'}` : NOT_RECORDED,
      b: b.judges?.length ? `${b.judges.length} judge${b.judges.length === 1 ? '' : 's'}` : NOT_RECORDED,
    },
    { label: 'Statutes / Acts', a: listOrFallback(a.acts), b: listOrFallback(b.acts) },
    { label: 'Provisions', a: listOrFallback(a.sections), b: listOrFallback(b.sections) },
    { label: 'Decision', a: a.decision_type ?? a.outcome ?? NOT_RECORDED, b: b.decision_type ?? b.outcome ?? NOT_RECORDED },
    { label: 'Indexed passages', a: formatCount(a.chunk_count), b: formatCount(b.chunk_count) },
  ]

  return (
    <div className="rounded-xl border border-border bg-card overflow-hidden">
      <div className="grid grid-cols-[minmax(84px,0.6fr)_1fr_1fr] text-sm">
        <div className="px-3 sm:px-4 py-3 bg-muted/40 border-b border-border" />
        {[a, b].map((c, i) => (
          <div key={c.case_id} className="px-3 sm:px-4 py-3 bg-muted/40 border-b border-l border-border min-w-0">
            <p className="text-[10px] font-semibold uppercase tracking-wider text-primary">Case {i === 0 ? 'A' : 'B'}</p>
            <Link to={`/cases/${c.case_id}`} className="font-serif font-semibold text-foreground hover:text-primary leading-snug line-clamp-2 break-words">
              {displayCaseName(c.case_name)}
            </Link>
          </div>
        ))}
        {rows.map((r) => (
          <div key={r.label} className="contents">
            <div className="px-3 sm:px-4 py-2.5 border-b border-border text-xs font-medium text-muted-foreground">{r.label}</div>
            {[r.a, r.b].map((v, i) => (
              <div
                key={i}
                className={cn(
                  'px-3 sm:px-4 py-2.5 border-b border-l border-border text-xs sm:text-sm break-words min-w-0',
                  v === NOT_RECORDED ? 'text-muted-foreground italic' : 'text-foreground',
                )}
              >
                {v}
              </div>
            ))}
          </div>
        ))}
      </div>
    </div>
  )
}

function EvidenceColumn({
  title,
  caseName,
  citations,
}: {
  title: string
  caseName?: string
  citations: Citation[]
}) {
  return (
    <div className="space-y-2 min-w-0">
      <div>
        <p className="text-xs font-semibold text-foreground">{title}</p>
        {caseName && <p className="text-xs text-muted-foreground truncate">{caseName}</p>}
      </div>
      {citations.length > 0 ? (
        citations.map((c, i) => <CitationCard key={c.chunk_id + i} citation={c} index={i} />)
      ) : (
        <p className="text-xs text-muted-foreground">Source information unavailable.</p>
      )}
    </div>
  )
}
