import { useState } from 'react'
import { ChevronDown, ChevronUp, ExternalLink, Scale, Calendar, Gavel } from 'lucide-react'
import { motion, AnimatePresence } from 'framer-motion'
import { Badge } from '@/components/ui/Badge'
import { cn } from '@/lib/utils'
import type { Citation } from '@/types'

interface CitationCardProps {
  citation: Citation
  index: number
  className?: string
}

export function CitationCard({ citation, index, className }: CitationCardProps) {
  const [expanded, setExpanded] = useState(false)
  const excerpt = citation.chunk_text ?? citation.content
  const relevanceScore = citation.relevance_score ?? citation.similarity_score

  return (
    <div className={cn('citation-badge rounded-lg overflow-hidden', className)}>
      <button
        onClick={() => setExpanded((v) => !v)}
        className="w-full flex items-start gap-3 p-3 text-left hover:bg-white/5 transition-colors"
      >
        <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-legal-gold/20 text-xs font-bold text-legal-gold">
          {index + 1}
        </span>
        <div className="min-w-0 flex-1">
          <p className="text-sm font-medium text-foreground line-clamp-2">{citation.case_name}</p>
          {citation.citation_text && (
            <p className="mt-0.5 text-xs text-muted">{citation.citation_text}</p>
          )}
        </div>
        <span className="mt-0.5 shrink-0 text-muted">
          {expanded ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
        </span>
      </button>

      <AnimatePresence>
        {expanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="overflow-hidden"
          >
            <div className="border-t border-white/10 px-3 pb-3 pt-2 space-y-2.5">
              {excerpt && (
                <blockquote className="text-xs text-foreground/80 italic border-l-2 border-legal-gold/50 pl-3 line-clamp-4">
                  "{excerpt}"
                </blockquote>
              )}

              <div className="flex flex-wrap gap-2">
                {citation.court && (
                  <div className="flex items-center gap-1 text-xs text-muted">
                    <Scale className="h-3 w-3" />
                    {citation.court}
                  </div>
                )}
                {citation.year && (
                  <div className="flex items-center gap-1 text-xs text-muted">
                    <Calendar className="h-3 w-3" />
                    {citation.year}
                  </div>
                )}
                {citation.decision_type && (
                  <div className="flex items-center gap-1 text-xs text-muted">
                    <Gavel className="h-3 w-3" />
                    {citation.decision_type}
                  </div>
                )}
              </div>

              {relevanceScore !== undefined && (
                <div className="flex items-center gap-2">
                  <span className="text-xs text-muted">Relevance</span>
                  <div className="flex-1 h-1 rounded-full bg-white/10">
                    <div
                      className="h-1 rounded-full bg-legal-gold/70"
                      style={{ width: `${Math.round(relevanceScore * 100)}%` }}
                    />
                  </div>
                  <Badge variant="gold" className="text-[10px]">
                    {Math.round(relevanceScore * 100)}%
                  </Badge>
                </div>
              )}

              {citation.case_id && (
                <a
                  href={`/cases/${citation.case_id}`}
                  className="inline-flex items-center gap-1 text-xs text-primary hover:underline"
                  onClick={(e) => e.stopPropagation()}
                >
                  View full case <ExternalLink className="h-3 w-3" />
                </a>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
