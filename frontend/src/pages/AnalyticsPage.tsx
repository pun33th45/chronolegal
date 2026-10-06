import { useQuery } from '@tanstack/react-query'
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { FileText, Layers, Search, Users } from 'lucide-react'
import { analyticsApi } from '@/services/api'
import { Skeleton } from '@/components/ui/Skeleton'
import { ErrorState } from '@/components/ui/ErrorState'
import { cn } from '@/utils/cn'
import type { AnalyticsDashboard } from '@/types'

// ChronoLegal palette (tailwind.config.ts → colors.legal).
const NAVY = '#0F1B3D'
const GOLD = '#C8A951'

const fmt = (n: number) => n.toLocaleString('en-IN')
const plural = (n: number, one: string, many = `${one}s`) => `${fmt(n)} ${n === 1 ? one : many}`

export default function AnalyticsPage() {
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ['analytics', 'dashboard'],
    queryFn: analyticsApi.dashboard,
  })

  return (
    <div className="p-4 sm:p-6 md:p-8 max-w-6xl mx-auto space-y-10">
      <header className="space-y-1.5">
        <p className="text-xs font-semibold uppercase tracking-wider text-primary">Insights</p>
        <h1 className="font-serif text-2xl sm:text-3xl font-bold text-foreground">Legal Analytics</h1>
        <p className="text-sm text-muted-foreground max-w-2xl">
          Understand your legal corpus at a glance. Insights derived from the judgments indexed in ChronoLegal.
        </p>
      </header>

      {isLoading ? (
        <AnalyticsSkeleton />
      ) : isError || !data ? (
        <ErrorState description="Unable to load analytics right now." onRetry={() => refetch()} />
      ) : (
        <AnalyticsContent data={data} />
      )}
    </div>
  )
}

function AnalyticsContent({ data }: { data: AnalyticsDashboard }) {
  const totalCases = data.total_cases
  const decisionsRecorded = data.decision_types.reduce((sum, d) => sum + d.count, 0)
  const chunksPerCase = totalCases > 0 ? Math.round(data.total_embeddings / totalCases) : null

  return (
    <>
      {/* ── Overview ─────────────────────────────────────────────────────── */}
      <section aria-labelledby="overview-heading">
        <SectionHeading id="overview-heading" title="Overview" />
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
          <StatCard index="01" icon={FileText} value={fmt(totalCases)} label="Total cases" context="Judgments in the knowledge base" />
          <StatCard
            index="02"
            icon={Layers}
            value={fmt(data.total_embeddings)}
            label="Indexed chunks"
            context={chunksPerCase !== null ? `≈ ${fmt(chunksPerCase)} per judgment` : 'Searchable passages'}
          />
          <StatCard index="03" icon={Users} value={fmt(data.total_users)} label="Total users" context="Registered accounts" />
          <StatCard
            index="04"
            icon={Search}
            value={fmt(data.total_searches)}
            label="Case searches"
            context={data.total_searches === 0 ? 'No research activity yet' : 'Queries run from Case Search'}
          />
        </div>
      </section>

      {/* ── Corpus overview ──────────────────────────────────────────────── */}
      <section aria-labelledby="corpus-heading">
        <SectionHeading
          id="corpus-heading"
          title="Corpus Overview"
          subtitle="When the judgments in your knowledge base were delivered."
        />
        <Panel>
          <CaseVolume trends={data.case_trends} undated={data.cases_without_date} />
        </Panel>
      </section>

      {/* ── Courts + outcomes ────────────────────────────────────────────── */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <section aria-labelledby="courts-heading">
          <SectionHeading id="courts-heading" title="Court Distribution" subtitle="Where the indexed judgments come from." />
          <Panel>
            {data.top_courts.length > 0 ? (
              <DistributionList
                items={data.top_courts.map((c) => ({
                  label: c.court,
                  value: c.count,
                  detail: `${c.percentage.toFixed(1)}%`,
                  tooltip: `${c.court}: ${plural(c.count, 'judgment')} (${c.percentage.toFixed(1)}% of all judgments)`,
                }))}
              />
            ) : (
              <EmptyNote>No court information has been recorded yet.</EmptyNote>
            )}
            {data.cases_without_court > 0 && (
              <Footnote>
                {plural(data.cases_without_court, 'uploaded judgment')} {data.cases_without_court === 1 ? 'has' : 'have'} no
                recorded court and {data.cases_without_court === 1 ? 'is' : 'are'} not shown.
              </Footnote>
            )}
          </Panel>
        </section>

        <section aria-labelledby="outcomes-heading">
          <SectionHeading id="outcomes-heading" title="Decision Outcomes" subtitle="How the judgments were disposed of." />
          <Panel>
            {data.decision_types.length > 0 ? (
              <>
                <DistributionList
                  items={data.decision_types.map((d) => ({
                    label: d.decision_type,
                    value: d.count,
                    detail: `${d.percentage.toFixed(1)}%`,
                    tooltip: `${d.decision_type}: ${plural(d.count, 'judgment')} (${d.percentage.toFixed(1)}% of all judgments)`,
                  }))}
                />
                <Footnote>
                  Outcome recorded for {fmt(decisionsRecorded)} of {plural(totalCases, 'judgment')}; percentages are of all
                  judgments.
                </Footnote>
              </>
            ) : (
              <EmptyNote>No decision outcomes have been recorded yet.</EmptyNote>
            )}
          </Panel>
        </section>
      </div>

      {/* ── Legal landscape ──────────────────────────────────────────────── */}
      <section aria-labelledby="landscape-heading">
        <SectionHeading
          id="landscape-heading"
          title="Legal Landscape"
          subtitle="Legislation and legal concepts appearing across the indexed judgments."
        />
        <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">
          <Panel className="lg:col-span-3">
            <PanelTitle>Most referenced legislation</PanelTitle>
            {data.top_acts.length > 0 ? (
              <DistributionList
                items={data.top_acts.slice(0, 8).map((a) => ({
                  label: a.name,
                  value: a.count,
                  detail: plural(a.count, 'judgment'),
                  tooltip: `${a.name}: referenced in ${plural(a.count, 'judgment')}`,
                }))}
              />
            ) : (
              <EmptyNote>No legislation references have been extracted yet.</EmptyNote>
            )}
          </Panel>
          <Panel className="lg:col-span-2">
            <PanelTitle>Top legal concepts</PanelTitle>
            <KeywordCloud keywords={data.top_keywords.slice(0, 15)} />
          </Panel>
        </div>
      </section>

      {/* ── Insights ─────────────────────────────────────────────────────── */}
      <CorpusInsights data={data} />
    </>
  )
}

// ─── Building blocks ─────────────────────────────────────────────────────────

function SectionHeading({ id, title, subtitle }: { id: string; title: string; subtitle?: string }) {
  return (
    <div className="mb-3">
      <h2 id={id} className="text-sm font-semibold text-foreground">
        {title}
      </h2>
      {subtitle && <p className="text-xs text-muted-foreground mt-0.5">{subtitle}</p>}
    </div>
  )
}

function Panel({ children, className }: { children: React.ReactNode; className?: string }) {
  return <div className={cn('rounded-xl border border-border bg-card p-4 sm:p-5 shadow-sm', className)}>{children}</div>
}

function PanelTitle({ children }: { children: React.ReactNode }) {
  return <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-4">{children}</p>
}

function EmptyNote({ children }: { children: React.ReactNode }) {
  return <p className="text-sm text-muted-foreground py-6 text-center">{children}</p>
}

function Footnote({ children }: { children: React.ReactNode }) {
  return <p className="text-[11px] text-muted-foreground mt-4 pt-3 border-t border-border">{children}</p>
}

function StatCard({
  index,
  icon: Icon,
  value,
  label,
  context,
}: {
  index: string
  icon: React.ElementType
  value: string
  label: string
  context: string
}) {
  return (
    <div className="rounded-xl border border-border bg-card p-4 shadow-sm">
      <div className="flex items-center justify-between mb-4">
        <div className="w-8 h-8 rounded-lg bg-accent flex items-center justify-center">
          <Icon className="w-4 h-4 text-primary" />
        </div>
        <span className="text-[11px] font-medium text-muted-foreground/70 tabular-nums">{index}</span>
      </div>
      <p className="font-serif text-2xl sm:text-3xl font-bold text-foreground tabular-nums leading-none">{value}</p>
      <p className="text-sm font-medium text-foreground mt-1.5">{label}</p>
      <p className="text-xs text-muted-foreground mt-0.5">{context}</p>
    </div>
  )
}

type DistributionItem = { label: string; value: number; detail: string; tooltip: string }

/** Readable horizontal bars: full labels (wrapping, never rotated), the
 *  largest value in gold, the rest in navy. */
function DistributionList({ items }: { items: DistributionItem[] }) {
  const max = Math.max(...items.map((i) => i.value), 1)
  return (
    <ul className="space-y-3.5">
      {items.map((item, i) => (
        <li key={item.label} title={item.tooltip}>
          <div className="flex items-baseline justify-between gap-3 mb-1.5">
            <span className="text-sm text-foreground leading-snug line-clamp-2 break-words">{item.label}</span>
            <span className="text-xs text-muted-foreground tabular-nums shrink-0">
              <span className="font-semibold text-foreground">{fmt(item.value)}</span> · {item.detail}
            </span>
          </div>
          <div className="h-2 rounded-full bg-muted overflow-hidden">
            <div
              className="h-full rounded-full transition-[width] duration-500"
              style={{ width: `${Math.max((item.value / max) * 100, 3)}%`, backgroundColor: i === 0 ? GOLD : NAVY, opacity: i === 0 ? 1 : 0.8 }}
            />
          </div>
        </li>
      ))}
    </ul>
  )
}

function CaseVolume({ trends, undated }: { trends: AnalyticsDashboard['case_trends']; undated: number }) {
  const dated = trends.reduce((sum, t) => sum + t.count, 0)
  if (trends.length === 0) {
    return <EmptyNote>No judgment dates have been recorded yet.</EmptyNote>
  }

  const first = trends[0].year
  const last = trends[trends.length - 1].year
  const peak = trends.reduce((a, b) => (b.count > a.count ? b : a))

  return (
    <div className="grid grid-cols-1 lg:grid-cols-[1fr_220px] gap-6">
      {trends.length < 3 ? (
        // Too few years for a meaningful trend — list them instead of a near-empty chart.
        <div className="flex flex-col justify-center">
          <ul className="space-y-2">
            {trends.map((t) => (
              <li key={t.year} className="flex items-center gap-3 text-sm">
                <span className="font-serif font-semibold text-foreground tabular-nums w-12">{t.year}</span>
                <span className="w-2 h-2 rounded-full" style={{ backgroundColor: GOLD }} />
                <span className="text-muted-foreground">{plural(t.count, 'judgment')}</span>
              </li>
            ))}
          </ul>
          <p className="text-xs text-muted-foreground mt-4">
            Your current corpus contains judgments from {plural(trends.length, 'year')}. Add more judgments to see corpus
            growth over time.
          </p>
        </div>
      ) : (
        <div className="h-56 sm:h-64 -ml-2">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={trends} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
              <CartesianGrid vertical={false} stroke="hsl(var(--border))" />
              <XAxis dataKey="year" tickLine={false} axisLine={false} tick={{ fontSize: 12, fill: 'hsl(var(--muted-foreground))' }} />
              <YAxis allowDecimals={false} tickLine={false} axisLine={false} width={28} tick={{ fontSize: 12, fill: 'hsl(var(--muted-foreground))' }} />
              <Tooltip
                cursor={{ fill: 'hsl(var(--accent))' }}
                content={({ active, payload }) =>
                  active && payload?.length ? (
                    <div className="rounded-lg border border-border bg-card px-3 py-2 shadow-md text-xs">
                      <p className="font-semibold text-foreground">{payload[0].payload.year}</p>
                      <p className="text-muted-foreground">{plural(payload[0].payload.count, 'judgment')}</p>
                    </div>
                  ) : null
                }
              />
              <Bar dataKey="count" fill={NAVY} radius={[4, 4, 0, 0]} maxBarSize={48} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      <dl className="grid grid-cols-3 lg:grid-cols-1 gap-4 lg:border-l lg:border-border lg:pl-6 content-center">
        <MiniStat label="Years covered" value={first === last ? `${first}` : `${first}–${last}`} />
        <MiniStat label="Busiest year" value={`${peak.year}`} hint={plural(peak.count, 'judgment')} />
        <MiniStat label="Dated judgments" value={fmt(dated)} hint={undated > 0 ? `${fmt(undated)} undated` : undefined} />
      </dl>
    </div>
  )
}

function MiniStat({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div>
      <dt className="text-[11px] text-muted-foreground uppercase tracking-wider">{label}</dt>
      <dd className="font-serif text-lg font-semibold text-foreground tabular-nums">{value}</dd>
      {hint && <dd className="text-xs text-muted-foreground">{hint}</dd>}
    </div>
  )
}

function KeywordCloud({ keywords }: { keywords: AnalyticsDashboard['top_keywords'] }) {
  if (keywords.length === 0) return <EmptyNote>No legal keywords available.</EmptyNote>
  const max = Math.max(...keywords.map((k) => k.count), 1)
  return (
    <ul className="flex flex-wrap gap-2">
      {keywords.map((k) => {
        const weight = k.count / max // 0–1: more frequent concepts read slightly larger
        return (
          <li
            key={k.name}
            title={`${k.name}: ${plural(k.count, 'judgment')}`}
            className={cn(
              'inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-foreground',
              weight >= 0.99 ? 'border-legal-gold/60 bg-accent text-[13px] font-medium' : 'border-border bg-card text-xs',
            )}
          >
            {k.name}
            <span className="text-[10px] text-muted-foreground tabular-nums">{k.count}</span>
          </li>
        )
      })}
    </ul>
  )
}

function CorpusInsights({ data }: { data: AnalyticsDashboard }) {
  const insights: { label: string; value: string; detail: string }[] = []
  const topCourt = data.top_courts[0]
  if (topCourt) insights.push({ label: 'Most represented court', value: topCourt.court, detail: plural(topCourt.count, 'judgment') })
  const topAct = data.top_acts[0]
  if (topAct) insights.push({ label: 'Most referenced legislation', value: topAct.name, detail: `Referenced in ${plural(topAct.count, 'judgment')}` })
  // Only call a concept "most common" when it genuinely leads (not a tie at the top).
  const [k1, k2] = data.top_keywords
  if (k1 && (!k2 || k1.count > k2.count)) {
    insights.push({ label: 'Most common legal concept', value: k1.name, detail: `Appears in ${plural(k1.count, 'judgment')}` })
  }
  if (data.case_trends.length > 0) {
    const latest = data.case_trends[data.case_trends.length - 1]
    insights.push({ label: 'Most recent judgment year', value: `${latest.year}`, detail: plural(latest.count, 'judgment') })
  }
  if (insights.length === 0) return null

  return (
    <section aria-labelledby="insights-heading">
      <SectionHeading id="insights-heading" title="Corpus Insights" subtitle="Derived directly from the figures above." />
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
        {insights.map((i) => (
          <div key={i.label} className="rounded-xl border border-border bg-card p-4 border-l-2 border-l-legal-gold">
            <p className="text-[11px] text-muted-foreground uppercase tracking-wider">{i.label}</p>
            <p className="font-serif text-[15px] font-semibold text-foreground mt-1.5 leading-snug break-words">{i.value}</p>
            <p className="text-xs text-muted-foreground mt-1">{i.detail}</p>
          </div>
        ))}
      </div>
    </section>
  )
}

function AnalyticsSkeleton() {
  return (
    <div className="space-y-10" aria-busy="true" aria-label="Loading analytics">
      <div>
        <Skeleton className="h-4 w-24 rounded mb-3" />
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
          {Array(4).fill(0).map((_, i) => <Skeleton key={i} className="h-36 rounded-xl" />)}
        </div>
      </div>
      <div>
        <Skeleton className="h-4 w-32 rounded mb-3" />
        <Skeleton className="h-72 rounded-xl" />
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <Skeleton className="h-52 rounded-xl" />
        <Skeleton className="h-52 rounded-xl" />
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">
        <Skeleton className="h-72 rounded-xl lg:col-span-3" />
        <Skeleton className="h-72 rounded-xl lg:col-span-2" />
      </div>
    </div>
  )
}
