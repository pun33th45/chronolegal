import type { Citation } from '@/types'

/** Citation chunk ids are "{case_id}__chunk_{n}" (see RAGPipeline). */
export function chunkIndexFromId(chunkId: string | null | undefined): number | null {
  const m = chunkId?.match(/__chunk_(\d+)$/)
  return m ? Number(m[1]) : null
}

/** First plausible 4-digit year in a date-ish string, if any. */
export function yearFrom(value: string | null | undefined): string | null {
  const m = value?.match(/\b(1[89]\d{2}|20\d{2})\b/)
  return m ? m[1] : null
}

/** Case Viewer URL that opens the exact cited passage, when known. */
export function sourceHref(citation: Pick<Citation, 'case_id' | 'chunk_id'>): string | null {
  if (!citation.case_id) return null
  const idx = chunkIndexFromId(citation.chunk_id)
  return idx === null
    ? `/cases/${citation.case_id}`
    : `/cases/${citation.case_id}?passage=${idx}`
}
