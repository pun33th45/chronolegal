import { useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import toast from 'react-hot-toast'
import { authApi } from '@/services/api'
import { useAuthStore } from '@/store/authStore'
import { Spinner } from '@/components/ui/Spinner'

/**
 * Landing point after the backend's Google callback. The backend sends only a
 * single-use, 60-second code in the URL fragment; it is swapped here for the
 * same TokenResponse password login returns, so a Google user ends up in
 * exactly the same auth state as any other user.
 */
export default function GoogleCallbackPage() {
  const navigate = useNavigate()
  const { setTokens } = useAuthStore()
  // The code is single-use; StrictMode runs effects twice in development.
  const started = useRef(false)

  useEffect(() => {
    if (started.current) return
    started.current = true

    const code = new URLSearchParams(window.location.hash.slice(1)).get('code')
    // Drop the fragment from the address bar and history immediately.
    window.history.replaceState(null, '', window.location.pathname)

    if (!code) {
      navigate('/login?oauth_error=failed', { replace: true })
      return
    }

    authApi
      .googleExchange(code)
      .then((data) => {
        setTokens(data.access_token, data.refresh_token, data.user)
        toast.success('Welcome to ChronoLegal!')
        navigate('/dashboard', { replace: true })
      })
      .catch(() => navigate('/login?oauth_error=expired', { replace: true }))
  }, [navigate, setTokens])

  return (
    <div className="min-h-screen flex flex-col items-center justify-center gap-3 bg-background">
      <Spinner />
      <p className="text-sm text-muted-foreground">Signing you in with Google…</p>
    </div>
  )
}
