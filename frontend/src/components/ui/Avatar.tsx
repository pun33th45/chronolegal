import * as RadixAvatar from '@radix-ui/react-avatar'
import { cn } from '@/lib/utils'

interface AvatarProps {
  name?: string | null
  size?: 'sm' | 'md'
  className?: string
}

const sizeMap = { sm: 'h-8 w-8 text-sm', md: 'h-9 w-9 text-sm' }

export function Avatar({ name, size = 'sm', className }: AvatarProps) {
  const initial = name?.trim()?.[0]?.toUpperCase() ?? 'U'
  return (
    <RadixAvatar.Root
      className={cn(
        'inline-flex select-none items-center justify-center rounded-full bg-primary/20 text-primary font-semibold flex-shrink-0',
        sizeMap[size],
        className,
      )}
    >
      <RadixAvatar.Fallback>{initial}</RadixAvatar.Fallback>
    </RadixAvatar.Root>
  )
}
