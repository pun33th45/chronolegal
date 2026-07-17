import { X } from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { Select } from '@/components/ui/Select'
import { Input } from '@/components/ui/Input'
import type { SearchFilters } from '@/types'

interface FilterPanelProps {
  filters: SearchFilters
  onChange: (filters: SearchFilters) => void
  onReset: () => void
}

const COURTS = [
  'Supreme Court of India',
  'High Court of Delhi',
  'High Court of Bombay',
  'High Court of Madras',
  'High Court of Calcutta',
  'High Court of Allahabad',
  'High Court of Karnataka',
  'High Court of Rajasthan',
]

const DECISION_TYPES = ['Allowed', 'Dismissed', 'Partly Allowed', 'Disposed', 'Settled']

const SEARCH_TYPES = [
  { value: 'hybrid', label: 'Hybrid (Recommended)' },
  { value: 'semantic', label: 'Semantic' },
  { value: 'keyword', label: 'Keyword (BM25)' },
]

export function FilterPanel({ filters, onChange, onReset }: FilterPanelProps) {
  const hasFilters = Object.values(filters).some((v) => v != null && v !== '')

  return (
    <div className="rounded-xl border border-border bg-surface p-4 space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-foreground">Filters</h3>
        {hasFilters && (
          <Button
            variant="ghost"
            size="xs"
            onClick={onReset}
            className="text-muted gap-1 hover:text-foreground"
          >
            <X className="h-3 w-3" /> Reset
          </Button>
        )}
      </div>

      <Select
        label="Search Type"
        value={filters.search_type ?? 'hybrid'}
        onChange={(e) => onChange({ ...filters, search_type: e.target.value })}
      >
        {SEARCH_TYPES.map((t) => (
          <option key={t.value} value={t.value}>
            {t.label}
          </option>
        ))}
      </Select>

      <Select
        label="Court"
        value={filters.court ?? ''}
        onChange={(e) => onChange({ ...filters, court: e.target.value || undefined })}
        placeholder="All courts"
      >
        {COURTS.map((c) => (
          <option key={c} value={c}>
            {c}
          </option>
        ))}
      </Select>

      <Select
        label="Decision Type"
        value={filters.decision_type ?? ''}
        onChange={(e) => onChange({ ...filters, decision_type: e.target.value || undefined })}
        placeholder="Any decision"
      >
        {DECISION_TYPES.map((d) => (
          <option key={d} value={d}>
            {d}
          </option>
        ))}
      </Select>

      <div className="grid grid-cols-2 gap-2">
        <Input
          label="Year from"
          type="number"
          min={1950}
          max={2024}
          placeholder="1950"
          value={filters.year_from ?? ''}
          onChange={(e) =>
            onChange({ ...filters, year_from: e.target.value ? Number(e.target.value) : undefined })
          }
        />
        <Input
          label="Year to"
          type="number"
          min={1950}
          max={2024}
          placeholder="2024"
          value={filters.year_to ?? ''}
          onChange={(e) =>
            onChange({ ...filters, year_to: e.target.value ? Number(e.target.value) : undefined })
          }
        />
      </div>

      <Input
        label="Act / Legislation"
        placeholder="e.g. Constitution of India"
        value={filters.act ?? ''}
        onChange={(e) => onChange({ ...filters, act: e.target.value || undefined })}
      />
    </div>
  )
}
