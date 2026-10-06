// Display helpers for case metadata. They never invent values: anything the
// backend didn't record comes back as null so callers show an honest fallback.

// Placeholder the upload pipeline stores when NER found no court.
const COURT_PLACEHOLDERS = new Set(['uploaded document'])

export function courtLabel(court: string | null | undefined): string | null {
  const c = court?.trim()
  return c && !COURT_PLACEHOLDERS.has(c.toLowerCase()) ? c : null
}

export function yearOf(judgmentDate: string | null | undefined): string | null {
  const m = judgmentDate?.match(/^(\d{4})/)
  return m ? m[1] : null
}

export function formatCount(n: number | null | undefined): string {
  return typeof n === 'number' ? n.toLocaleString('en-IN') : '—'
}

/**
 * Human-readable display title. When a judgment's stored name is only a raw
 * filename (no spaces, e.g. "minerva_mills_judgment.txt" — uploads where no
 * case title was detected), drop the extension and turn separators into
 * spaces. This only reformats the existing text; it never invents a title.
 */
export function displayCaseName(name: string | null | undefined): string {
  const n = (name ?? '').trim()
  if (!n) return 'Untitled judgment'
  if (/\s/.test(n) || !/[_-]/.test(n)) return n
  return n
    .replace(/\.(pdf|docx?|txt)$/i, '')
    .split(/[_-]+/)
    .filter(Boolean)
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(' ')
}

export function formatJudgmentDate(judgmentDate: string | null | undefined): string | null {
  if (!judgmentDate) return null
  const d = new Date(judgmentDate)
  return Number.isNaN(d.getTime())
    ? null
    : d.toLocaleDateString('en-IN', { day: 'numeric', month: 'long', year: 'numeric' })
}
