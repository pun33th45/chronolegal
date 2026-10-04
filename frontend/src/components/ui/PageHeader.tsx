import { type ReactNode } from 'react'
import { cn } from '@/lib/utils'

interface PageHeaderProps {
  eyebrow?: string
  title: ReactNode
  description?: ReactNode
  actions?: ReactNode
  className?: string
}

export function PageHeader({ eyebrow, title, description, actions, className }: PageHeaderProps) {
  return (
    <div className={cn('space-y-4', className)}>
      <div>
        {eyebrow && (
          <p className="text-xs font-semibold text-primary uppercase tracking-wider mb-1.5">
            {eyebrow}
          </p>
        )}
        <h1 className="font-serif text-2xl md:text-3xl font-bold text-foreground text-balance">
          {title}
        </h1>
        {description && (
          <p className="text-muted-foreground mt-2 max-w-2xl text-[15px] leading-relaxed">
            {description}
          </p>
        )}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-3">{actions}</div>}
    </div>
  )
}
