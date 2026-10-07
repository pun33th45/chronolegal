import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { authApi } from '@/services/api'
import { Spinner } from '@/components/ui/Spinner'

// User-facing messages for the fixed error codes the backend's Google
// callback can return in ?oauth_error= (see auth.py / google_auth_service.py).
export const GOOGLE_ERROR_MESSAGES: Record<string, string> = {
  cancelled: 'Google sign-in was cancelled.',
  expired: 'Your Google sign-in took too long. Please try again.',
  invalid_state: "Google sign-in couldn't be verified. Please try again.",
  email_not_verified: "Your Google account's email address isn't verified.",
  account_conflict: 'This email is already linked to a different Google account.',
  account_disabled: 'This account has been disabled.',
  unavailable: "Couldn't reach Google. Please try again in a moment.",
  not_configured: "Google sign-in isn't available right now.",
  failed: 'Google sign-in failed. Please try again.',
}

export function googleErrorMessage(code: string | null): string {
  return (code && GOOGLE_ERROR_MESSAGES[code]) || GOOGLE_ERROR_MESSAGES.failed
}

function GoogleLogo() {
  // Official multicolor "G" mark.
  return (
    <svg viewBox="0 0 48 48" className="w-[18px] h-[18px]" aria-hidden="true">
      <path fill="#EA4335" d="M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5z" />
      <path fill="#4285F4" d="M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65z" />
      <path fill="#FBBC05" d="M10.53 28.59c-.48-1.45-.76-2.99-.76-4.59s.27-3.14.76-4.59l-7.98-6.19C.92 16.46 0 20.12 0 24c0 3.88.92 7.54 2.56 10.78l7.97-6.19z" />
      <path fill="#34A853" d="M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2.15 1.45-4.92 2.3-8.16 2.3-6.26 0-11.57-4.22-13.47-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48z" />
    </svg>
  )
}

/**
 * "──── or ────" divider plus a "Continue with Google" button, styled to
 * Google's light-theme branding (white fill, #747775 outline, multicolor G)
 * at the same height as the form's primary button.
 *
 * Google sign-in is a known, permanent part of this product, so the button
 * is shown by default (while the `/auth/providers` check is loading, and
 * even if that check fails outright — e.g. the backend is temporarily
 * unreachable). It's hidden only on the one signal that actually means
 * "this deployment doesn't offer Google sign-in": a *successful* response
 * that explicitly says `google: false`. That keeps a flaky or cold-started
 * backend from silently erasing a core sign-in option.
 */
export function GoogleSignInSection() {
  const [redirecting, setRedirecting] = useState(false)
  const { data, isSuccess, isError } = useQuery({
    queryKey: ['auth-providers'],
    queryFn: authApi.providers,
    staleTime: Infinity,
    retry: false,
  })

  if (isSuccess && !data?.google) return null

  return (
    <>
      <div className="flex items-center gap-3 my-5" role="separator">
        <div className="h-px flex-1 bg-border" />
        <span className="text-xs uppercase tracking-wider text-muted-foreground">or</span>
        <div className="h-px flex-1 bg-border" />
      </div>
      <a
        href={authApi.googleSignInUrl}
        onClick={() => setRedirecting(true)}
        aria-disabled={redirecting}
        className="w-full h-11 inline-flex items-center justify-center gap-3 rounded-lg border border-[#747775] bg-white text-[#1F1F1F] text-sm font-medium hover:bg-[#F8F9FA] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/60 transition-colors aria-disabled:pointer-events-none aria-disabled:opacity-70"
      >
        {redirecting ? <Spinner size="sm" /> : <GoogleLogo />}
        {redirecting ? 'Connecting to Google…' : 'Continue with Google'}
      </a>
      {isError && (
        <p className="mt-2.5 text-xs text-center text-muted-foreground">
          Google sign-in may be temporarily unavailable.
        </p>
      )}
    </>
  )
}
