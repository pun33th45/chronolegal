import { type ReactNode } from 'react'
import { cn } from '@/lib/utils'

interface MetricCardProps {
  icon: React.ElementType
  label: string
  value: ReactNode
  hint?: string
  className?: string
}

export function MetricCard({ icon: Icon, label, value, hint, className }: MetricCardProps) {
  return (
    <div className={cn('rounded-xl border border-border bg-card p-4', className)}>
      <div className="flex items-center justify-between mb-2.5">
        <p className="text-xs text-muted-foreground font-medium">{label}</p>
        <div className="w-7 h-7 rounded-md bg-accent flex items-center justify-center flex-shrink-0">
          <Icon className="w-3.5 h-3.5 text-primary" />
        </div>
      </div>
      <p className="text-2xl font-bold text-foreground tabular-nums leading-none">{value}</p>
      {hint && <p className="text-xs text-muted-foreground mt-1.5">{hint}</p>}
    </div>
  )
}

export function MetricCardSkeleton() {
  return (
    <div className="rounded-xl border border-border bg-card p-4">
      <div className="flex items-center justify-between mb-2.5">
        <div className="skeleton h-3 w-16 rounded" />
        <div className="skeleton h-7 w-7 rounded-md" />
      </div>
      <div className="skeleton h-7 w-12 rounded" />
    </div>
  )
}
