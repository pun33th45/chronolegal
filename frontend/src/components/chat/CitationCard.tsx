import { useState } from 'react'
import { Link } from 'react-router-dom'
import { ArrowUpRight, ChevronDown } from 'lucide-react'
import { cn } from '@/lib/utils'
import { displayCaseName } from '@/lib/caseMeta'
import { chunkIndexFromId, sourceHref, yearFrom } from '@/lib/citations'
import type { Citation } from '@/types'

interface CitationCardProps {
  citation: Citation
  index: number
  className?: string
  /** Optional label shown above the case name, e.g. "Case A". */
  sideLabel?: string
}

/**
 * One retrieved source behind an answer. Everything shown comes from the
 * citation the backend returned: case, court/date metadata, the passage's
 * position in the judgment (its chunk index), the cross-encoder relevance
 * score and the passage text. Page numbers are shown only when the
 * ingestion pipeline actually recorded one.
 */
export function CitationCard({ citation, index, className, sideLabel }: CitationCardProps) {
  const [expanded, setExpanded] = useState(false)
  const passage = citation.chunk_text ?? citation.content
  const score = citation.relevance_score ?? citation.similarity_score
  const chunkIndex = chunkIndexFromId(citation.chunk_id)
  const year = citation.year ?? yearFrom(citation.date)
  const href = sourceHref(citation)

  const meta = [
    citation.court,
    year,
    citation.page_number ? `Page ${citation.page_number}` : null,
    chunkIndex !== null ? `Passage ${chunkIndex + 1}` : null,
  ].filter(Boolean)

  return (
    <div className={cn('rounded-lg border border-border bg-card overflow-hidden', className)}>
      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        aria-expanded={expanded}
        className="w-full flex items-start gap-3 p-3 text-left hover:bg-muted/40 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-primary/40"
      >
        <span className="mt-0.5 flex h-5 min-w-5 px-1 shrink-0 items-center justify-center rounded-md bg-legal-gold/15 text-[11px] font-semibold text-legal-gold tabular-nums">
          {citation.rank ?? index + 1}
        </span>
        <div className="min-w-0 flex-1">
          {sideLabel && (
            <p className="text-[10px] font-semibold uppercase tracking-wider text-primary mb-0.5">
              {sideLabel}
            </p>
          )}
          <p className="text-sm font-medium text-foreground leading-snug line-clamp-2">
            {citation.case_name ? displayCaseName(citation.case_name) : 'Source information unavailable'}
          </p>
          {meta.length > 0 && (
            <p className="mt-0.5 text-xs text-muted-foreground">{meta.join(' · ')}</p>
          )}
        </div>
        {typeof score === 'number' && (
          <span
            className="mt-0.5 shrink-0 text-[11px] font-medium text-muted-foreground tabular-nums"
            title="Relevance score from the cross-encoder reranker"
          >
            {Math.round(score * 100)}%
          </span>
        )}
        <ChevronDown
          className={cn(
            'mt-0.5 h-4 w-4 shrink-0 text-muted-foreground transition-transform',
            expanded && 'rotate-180',
          )}
        />
      </button>

      {expanded && (
        <div className="border-t border-border px-3 pb-3 pt-3 space-y-3">
          {passage ? (
            <div>
              <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider mb-1.5">
                Relevant passage
              </p>
              <blockquote className="text-[13px] text-foreground/85 leading-relaxed border-l-2 border-legal-gold/60 pl-3 whitespace-pre-line">
                {passage}
              </blockquote>
            </div>
          ) : (
            <p className="text-xs text-muted-foreground">Source information unavailable.</p>
          )}

          <div className="flex items-center justify-between gap-3">
            {typeof score === 'number' ? (
              <p className="text-[11px] text-muted-foreground">
                Relevance {Math.round(score * 100)}% <span className="opacity-70">(reranker score)</span>
              </p>
            ) : (
              <span />
            )}
            {href && (
              <Link
                to={href}
                onClick={(e) => e.stopPropagation()}
                className="inline-flex items-center gap-1 rounded-md border border-border px-2.5 py-1 text-xs font-medium text-foreground hover:bg-muted transition-colors"
              >
                View Source <ArrowUpRight className="h-3 w-3" />
              </Link>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
