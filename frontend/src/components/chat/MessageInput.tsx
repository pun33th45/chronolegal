import { useRef, useEffect, type KeyboardEvent, type FormEvent } from 'react'
import { Send, Square, Paperclip } from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { cn } from '@/lib/utils'

interface MessageInputProps {
  value: string
  onChange: (value: string) => void
  onSubmit: (message: string) => void
  onAbort?: () => void
  isStreaming?: boolean
  placeholder?: string
  disabled?: boolean
  maxLength?: number
  className?: string
}

export function MessageInput({
  value,
  onChange,
  onSubmit,
  onAbort,
  isStreaming = false,
  placeholder = 'Ask a legal question…',
  disabled = false,
  maxLength = 4000,
  className,
}: MessageInputProps) {
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  useEffect(() => {
    const el = textareaRef.current
    if (!el) return
    el.style.height = 'auto'
    el.style.height = `${Math.min(el.scrollHeight, 200)}px`
  }, [value])

  function handleKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      if (!isStreaming && value.trim()) handleSubmit()
    }
  }

  function handleSubmit(e?: FormEvent) {
    e?.preventDefault()
    const msg = value.trim()
    if (!msg || disabled) return
    onSubmit(msg)
  }

  const remaining = maxLength - value.length
  const nearLimit = remaining < 200

  return (
    <form
      onSubmit={handleSubmit}
      className={cn(
        'relative flex flex-col rounded-xl border border-border bg-surface transition-colors',
        'focus-within:border-primary/50 focus-within:ring-1 focus-within:ring-primary/30',
        disabled && 'opacity-60',
        className,
      )}
    >
      <textarea
        ref={textareaRef}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder={placeholder}
        disabled={disabled || isStreaming}
        maxLength={maxLength}
        rows={1}
        className={cn(
          'w-full resize-none bg-transparent px-4 py-3.5 text-sm text-foreground placeholder:text-muted',
          'focus:outline-none',
          'min-h-[52px] max-h-[200px]',
        )}
      />

      <div className="flex items-center justify-between px-3 pb-2.5 pt-0">
        <div className="flex items-center gap-1">
          <Button
            type="button"
            variant="ghost"
            size="icon-sm"
            className="text-muted hover:text-foreground"
            title="Attach document (coming soon)"
            disabled
          >
            <Paperclip className="h-4 w-4" />
          </Button>
          {nearLimit && (
            <span className={cn('text-xs', remaining <= 50 ? 'text-red-400' : 'text-yellow-400')}>
              {remaining} left
            </span>
          )}
        </div>

        {isStreaming ? (
          <Button
            type="button"
            variant="destructive"
            size="sm"
            onClick={onAbort}
            className="gap-1.5"
          >
            <Square className="h-3.5 w-3.5 fill-current" />
            Stop
          </Button>
        ) : (
          <Button
            type="submit"
            size="sm"
            disabled={!value.trim() || disabled}
            className="gap-1.5"
          >
            <Send className="h-3.5 w-3.5" />
            Send
          </Button>
        )}
      </div>
    </form>
  )
}
