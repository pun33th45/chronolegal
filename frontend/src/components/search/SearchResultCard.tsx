import { useState } from 'react'
import { Scale, Calendar, Gavel, ChevronDown, ChevronUp, BookOpen } from 'lucide-react'
import { motion, AnimatePresence } from 'framer-motion'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { cn } from '@/lib/utils'
import type { SearchResult } from '@/types'

interface SearchResultCardProps {
  result: SearchResult
  rank: number
  className?: string
}

export function SearchResultCard({ result, rank, className }: SearchResultCardProps) {
  const [expanded, setExpanded] = useState(false)
  const dateStr = result.judgment_date ?? result.decision_date
  const matchScore = result.score ?? result.similarity_score
  const excerpt = result.chunk_text ?? result.chunk_content

  return (
    <div className={cn('legal-card rounded-xl p-4 transition-shadow hover:shadow-lg', className)}>
      <div className="flex gap-3">
        <span className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-primary/10 text-xs font-bold text-primary">
          {rank}
        </span>

        <div className="min-w-0 flex-1 space-y-2">
          <div className="flex flex-wrap items-start justify-between gap-2">
            <h3 className="text-base font-semibold text-foreground leading-tight">
              {result.case_name}
            </h3>
            {matchScore !== undefined && (
              <Badge variant="gold" className="shrink-0">
                {Math.round(matchScore * 100)}% match
              </Badge>
            )}
          </div>

          <div className="flex flex-wrap gap-3 text-xs text-muted">
            {result.court && (
              <span className="flex items-center gap-1">
                <Scale className="h-3 w-3" /> {result.court}
              </span>
            )}
            {dateStr && (
              <span className="flex items-center gap-1">
                <Calendar className="h-3 w-3" />
                {new Date(dateStr).toLocaleDateString('en-IN', {
                  year: 'numeric',
                  month: 'short',
                  day: 'numeric',
                })}
              </span>
            )}
            {result.decision_type && (
              <span className="flex items-center gap-1">
                <Gavel className="h-3 w-3" /> {result.decision_type}
              </span>
            )}
          </div>

          {excerpt && (
            <p className={cn('text-sm text-foreground/80', !expanded && 'line-clamp-2')}>
              {excerpt}
            </p>
          )}

          {result.acts && result.acts.length > 0 && (
            <div className="flex flex-wrap gap-1.5">
              {result.acts.slice(0, expanded ? undefined : 3).map((act) => (
                <Badge key={act} variant="teal" className="text-[11px]">
                  {act}
                </Badge>
              ))}
              {!expanded && result.acts.length > 3 && (
                <Badge variant="secondary" className="text-[11px]">
                  +{result.acts.length - 3} more
                </Badge>
              )}
            </div>
          )}

          <AnimatePresence>
            {expanded && result.summary && (
              <motion.div
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: 'auto' }}
                exit={{ opacity: 0, height: 0 }}
                className="overflow-hidden"
              >
                <div className="mt-2 rounded-lg bg-surface-hover p-3">
                  <p className="text-xs font-medium text-muted mb-1">Summary</p>
                  <p className="text-sm text-foreground/80">{result.summary}</p>
                </div>
              </motion.div>
            )}
          </AnimatePresence>

          <div className="flex items-center gap-2 pt-1">
            <Button
              variant="ghost"
              size="xs"
              onClick={() => setExpanded((v) => !v)}
              className="text-muted gap-1"
            >
              {expanded ? (
                <>
                  <ChevronUp className="h-3.5 w-3.5" /> Show less
                </>
              ) : (
                <>
                  <ChevronDown className="h-3.5 w-3.5" /> Show more
                </>
              )}
            </Button>
            <a href={`/cases/${result.case_id}`}>
              <Button variant="ghost" size="xs" className="text-primary gap-1">
                <BookOpen className="h-3.5 w-3.5" /> Open case
              </Button>
            </a>
          </div>
        </div>
      </div>
    </div>
  )
}
