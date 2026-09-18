import { AlertTriangle } from 'lucide-react'
import { cn } from '@/lib/utils'
import { Button } from './Button'

interface ErrorStateProps {
  title?: string
  description: string
  onRetry?: () => void
  className?: string
  /** Compact inline banner instead of a centered block — for use inside an existing card/panel. */
  variant?: 'block' | 'banner'
}

export function ErrorState({
  title = 'Something went wrong',
  description,
  onRetry,
  className,
  variant = 'block',
}: ErrorStateProps) {
  if (variant === 'banner') {
    return (
      <div
        className={cn(
          'flex items-center justify-between gap-4 rounded-lg border border-destructive/30 bg-destructive/10 px-4 py-3',
          className,
        )}
      >
        <p className="text-sm text-destructive">{description}</p>
        {onRetry && (
          <Button variant="ghost" size="xs" onClick={onRetry} className="text-destructive shrink-0">
            Try Again
          </Button>
        )}
      </div>
    )
  }

  return (
    <div className={cn('flex flex-col items-center justify-center text-center py-16 px-6', className)}>
      <div className="w-12 h-12 rounded-xl bg-destructive/10 flex items-center justify-center text-destructive mb-4">
        <AlertTriangle className="w-5 h-5" />
      </div>
      <p className="text-sm font-medium text-foreground">{title}</p>
      <p className="text-sm text-muted-foreground mt-1 max-w-sm">{description}</p>
      {onRetry && (
        <Button variant="secondary" size="sm" onClick={onRetry} className="mt-5">
          Try Again
        </Button>
      )}
    </div>
  )
}
