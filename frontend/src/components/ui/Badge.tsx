import { type HTMLAttributes } from 'react'
import { cva, type VariantProps } from 'class-variance-authority'
import { cn } from '@/lib/utils'

const badgeVariants = cva(
  'inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ring-1 ring-inset transition-colors',
  {
    variants: {
      variant: {
        default: 'bg-primary/10 text-primary ring-primary/30',
        secondary: 'bg-surface text-muted-foreground ring-border',
        success: 'bg-green-500/10 text-green-700 ring-green-500/30',
        warning: 'bg-yellow-500/10 text-yellow-700 ring-yellow-500/30',
        danger: 'bg-red-500/10 text-red-700 ring-red-500/30',
        gold: 'bg-legal-gold/10 text-legal-gold ring-legal-gold/30',
        navy: 'bg-legal-navy/10 text-legal-navy ring-blue-500/30',
        teal: 'bg-legal-teal/10 text-legal-teal ring-teal-500/30',
      },
    },
    defaultVariants: { variant: 'default' },
  },
)

export interface BadgeProps
  extends HTMLAttributes<HTMLSpanElement>,
    VariantProps<typeof badgeVariants> {}

export function Badge({ className, variant, ...props }: BadgeProps) {
  return <span className={cn(badgeVariants({ variant }), className)} {...props} />
}
