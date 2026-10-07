import { forwardRef, type InputHTMLAttributes, type ReactNode } from 'react'
import { MotionConfig, motion } from 'framer-motion'
import { AlertCircle, Eye, EyeOff } from 'lucide-react'
import { cn } from '@/lib/utils'

// Shared presentation for the Login and Register pages: an editorial brand
// panel beside the form on desktop, collapsing to a compact brand header on
// tablet/mobile. Purely visual — all auth logic stays in the pages.

export interface AuthStep {
  label: string
  detail: string
}

interface AuthLayoutProps {
  eyebrow: string
  headline: [string, string]
  description: string
  steps: AuthStep[]
  children: ReactNode
}

const LOGO_ALT = 'ChronoLegal — Legal Research Platform'

// Primary auth action in deep navy, keeping gold to accents (eyebrows, focus
// rings, numerals) on these pages.
export const AUTH_PRIMARY_BUTTON =
  'h-12 w-full rounded-md bg-legal-navy text-[15px] text-white hover:bg-legal-navy-light active:scale-[0.99] focus-visible:ring-offset-2 focus-visible:ring-[#C8A951]/70 disabled:opacity-80'

export function AuthLayout({ eyebrow, headline, description, steps, children }: AuthLayoutProps) {
  return (
    <MotionConfig reducedMotion="user">
      <div className="min-h-screen bg-card lg:grid lg:grid-cols-[40%_minmax(0,1fr)] xl:grid-cols-[44%_minmax(0,1fr)]">
        {/* Editorial panel (desktop). A warm "paper" surface rather than a
            dark gradient, so the navy/gold logo sits on the light background
            it was designed for. */}
        <aside className="hidden lg:flex lg:sticky lg:top-0 lg:h-screen flex-col justify-between border-r border-[#E6DFD1] bg-[#F5F0E6] px-10 py-10 xl:px-16 xl:py-12">
          <img src="/chronolegal-logo.png" alt={LOGO_ALT} className="h-11 w-auto self-start object-contain" />

          <div className="max-w-[440px]">
            <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-[#8A6A1F]">{eyebrow}</p>
            <h2 className="mt-4 font-serif text-[2rem] xl:text-[2.85rem] font-semibold leading-[1.12] text-legal-navy">
              {headline[0]}
              <br />
              {headline[1]}
            </h2>
            <p className="mt-5 text-[15px] leading-relaxed text-[#4A5468]">{description}</p>

            <ol className="mt-10 border-t border-[#E0D7C6]">
              {steps.map((step, i) => (
                <li key={step.label} className="flex items-baseline gap-5 border-b border-[#E0D7C6] py-3.5">
                  <span className="w-6 shrink-0 font-serif text-sm tabular-nums text-[#8A6A1F]">
                    {String(i + 1).padStart(2, '0')}
                  </span>
                  <span className="text-[12px] font-semibold uppercase tracking-[0.14em] text-legal-navy">
                    {step.label}
                  </span>
                  <span className="ml-auto hidden xl:block text-[13px] text-[#6B7385]">{step.detail}</span>
                </li>
              ))}
            </ol>
          </div>

          <p className="font-serif text-[15px] text-[#4A5468]">Research with evidence. Not assumptions.</p>
        </aside>

        <main className="flex min-h-screen flex-col lg:min-h-0">
          {/* Compact brand header (tablet/mobile) — logo, headline and one
              sentence; the workflow detail is left to the desktop panel. */}
          <header className="lg:hidden border-b border-[#E6DFD1] bg-[#F5F0E6] px-5 py-6 sm:px-10 sm:py-8">
            <div className="mx-auto max-w-[420px]">
              <img src="/chronolegal-logo.png" alt={LOGO_ALT} className="h-8 w-auto object-contain" />
              <p className="mt-5 font-serif text-xl sm:text-2xl font-semibold leading-snug text-legal-navy">
                {headline[0]} {headline[1]}
              </p>
              <p className="mt-2 text-sm leading-relaxed text-[#4A5468]">{description}</p>
            </div>
          </header>

          <div className="flex flex-1 items-center justify-center px-5 py-10 sm:px-10 sm:py-14 lg:px-12 lg:py-16">
            <motion.div
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.22, ease: 'easeOut' }}
              className="w-full max-w-[420px]"
            >
              {children}
            </motion.div>
          </div>
        </main>
      </div>
    </MotionConfig>
  )
}

export function AuthHeading({ eyebrow, title, description }: { eyebrow: string; title: string; description: string }) {
  return (
    <div className="mb-8">
      <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-[#8A6A1F]">{eyebrow}</p>
      <h1 className="mt-3 font-serif text-[1.75rem] sm:text-[2rem] font-semibold leading-tight text-legal-navy">
        {title}
      </h1>
      <p className="mt-2 text-[15px] leading-relaxed text-muted-foreground">{description}</p>
    </div>
  )
}

interface AuthFieldProps extends InputHTMLAttributes<HTMLInputElement> {
  id: string
  label: string
  hint?: string
  error?: string
  trailing?: ReactNode
}

export const AuthField = forwardRef<HTMLInputElement, AuthFieldProps>(
  ({ id, label, hint, error, trailing, className, ...props }, ref) => {
    const hintId = hint ? `${id}-help` : undefined
    const errorId = error ? `${id}-error` : undefined
    const describedBy = [errorId, hintId].filter(Boolean).join(' ') || undefined
    return (
      <div>
        <label htmlFor={id} className="mb-2 block text-[13px] font-medium text-legal-navy">
          {label}
        </label>
        <div className="relative">
          <input
            ref={ref}
            id={id}
            aria-invalid={error ? true : undefined}
            aria-describedby={describedBy}
            className={cn(
              'h-12 w-full rounded-md border bg-[#FBFAF7] px-3.5 text-[15px] text-foreground placeholder:text-[#9AA1AE]',
              'transition-[border-color,box-shadow,background-color] duration-150',
              'focus:outline-none focus:bg-white focus:border-legal-navy focus:ring-[3px] focus:ring-[#C8A951]/30',
              'read-only:opacity-70',
              error ? 'border-destructive/70 focus:border-destructive focus:ring-destructive/15' : 'border-[#D9D3C7] hover:border-[#C4BCAD]',
              trailing && 'pr-12',
              className,
            )}
            {...props}
          />
          {trailing && <div className="absolute inset-y-0 right-1.5 flex items-center">{trailing}</div>}
        </div>
        {error && (
          <p id={errorId} className="mt-2 flex items-start gap-1.5 text-[13px] text-destructive">
            <AlertCircle className="mt-[1px] h-3.5 w-3.5 shrink-0" aria-hidden="true" />
            <span>{error}</span>
          </p>
        )}
        {hint && (
          <p id={hintId} className="mt-2 text-[13px] leading-snug text-muted-foreground">
            {hint}
          </p>
        )}
      </div>
    )
  },
)
AuthField.displayName = 'AuthField'

export function PasswordToggle({ visible, onToggle }: { visible: boolean; onToggle: () => void }) {
  return (
    <button
      type="button"
      onClick={onToggle}
      aria-label={visible ? 'Hide password' : 'Show password'}
      aria-pressed={visible}
      className="flex h-9 w-9 items-center justify-center rounded-md text-[#6B7385] transition-colors hover:bg-[#F0EBE1] hover:text-legal-navy focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#C8A951]/60"
    >
      {visible ? <EyeOff className="h-4 w-4" aria-hidden="true" /> : <Eye className="h-4 w-4" aria-hidden="true" />}
    </button>
  )
}

export function FormAlert({ title, message }: { title: string; message: string }) {
  return (
    <motion.div
      role="alert"
      initial={{ opacity: 0, y: -4 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.18 }}
      className="mb-6 flex gap-3 rounded-md border border-destructive/25 border-l-[3px] border-l-destructive bg-destructive/[0.04] px-4 py-3"
    >
      <AlertCircle className="mt-0.5 h-4 w-4 shrink-0 text-destructive" aria-hidden="true" />
      <div className="text-sm leading-relaxed">
        <p className="font-medium text-legal-navy">{title}</p>
        <p className="text-[#4A5468]">{message}</p>
      </div>
    </motion.div>
  )
}

type ValidityKey = 'valueMissing' | 'typeMismatch' | 'tooShort' | 'patternMismatch'
export type FieldMessages = Record<string, Partial<Record<ValidityKey, string>>>

/**
 * Runs the inputs' own HTML constraints (required, type, minLength, pattern —
 * unchanged from before) and returns inline messages instead of the browser's
 * native bubbles. Focuses the first invalid field.
 */
export function validateFields(form: HTMLFormElement, messages: FieldMessages): Record<string, string> {
  const errors: Record<string, string> = {}
  let first: HTMLInputElement | null = null
  for (const id of Object.keys(messages)) {
    const el = form.querySelector<HTMLInputElement>(`#${id}`)
    if (!el || el.validity.valid) continue
    const key = (Object.keys(messages[id]) as ValidityKey[]).find((k) => el.validity[k])
    errors[id] = (key && messages[id][key]) || el.validationMessage
    first ??= el
  }
  first?.focus()
  return errors
}
