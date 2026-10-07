import { useEffect, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { useAuthStore } from '@/store/authStore'
import { authApi } from '@/services/api'
import { Button } from '@/components/ui/Button'
import { GoogleSignInSection, googleErrorMessage } from '@/components/auth/GoogleSignIn'
import {
  AUTH_PRIMARY_BUTTON,
  AuthField,
  AuthHeading,
  AuthLayout,
  FormAlert,
  PasswordToggle,
  validateFields,
  type FieldMessages,
} from '@/components/auth/AuthLayout'
import { getAuthErrorMessage } from '@/lib/authErrors'
import toast from 'react-hot-toast'

const STEPS = [
  { label: 'Judgment', detail: 'The source text' },
  { label: 'Knowledge Base', detail: 'Indexed passages' },
  { label: 'Retrieved Evidence', detail: 'What the case says' },
  { label: 'Grounded Answer', detail: 'Cited to the record' },
]

const FIELD_MESSAGES: FieldMessages = {
  email: {
    valueMissing: 'Enter your email address.',
    typeMismatch: 'Enter a valid email address, like name@example.com.',
  },
  password: { valueMissing: 'Enter your password.' },
}

export default function LoginPage() {
  const navigate = useNavigate()
  const { setTokens } = useAuthStore()
  const [form, setForm] = useState({ email: '', password: '' })
  const [showPass, setShowPass] = useState(false)
  const [loading, setLoading] = useState(false)
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({})
  const [formError, setFormError] = useState<{ title: string; message: string } | null>(null)
  const [searchParams, setSearchParams] = useSearchParams()
  // Set when Google sign-in matched an existing email/password account: the
  // user confirms that account's password once to link Google to it.
  const [googleLink, setGoogleLink] = useState<{ code: string; email: string } | null>(null)

  useEffect(() => {
    const oauthError = searchParams.get('oauth_error')
    if (oauthError) {
      setFormError({ title: "Couldn't sign in with Google", message: googleErrorMessage(oauthError) })
      setSearchParams({}, { replace: true })
    }
  }, [searchParams, setSearchParams])

  useEffect(() => {
    const fragment = new URLSearchParams(window.location.hash.slice(1))
    const code = fragment.get('google_link')
    if (!code) return
    const email = fragment.get('email') ?? ''
    window.history.replaceState(null, '', window.location.pathname)
    setGoogleLink({ code, email })
    setForm((f) => ({ ...f, email }))
  }, [])

  function update(field: 'email' | 'password', value: string) {
    setForm((f) => ({ ...f, [field]: value }))
    if (fieldErrors[field]) {
      setFieldErrors((prev) => {
        const next = { ...prev }
        delete next[field]
        return next
      })
    }
  }

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault()
    if (loading) return
    setFormError(null)
    const errors = validateFields(e.currentTarget, FIELD_MESSAGES)
    setFieldErrors(errors)
    if (Object.keys(errors).length > 0) return

    setLoading(true)
    try {
      const data = googleLink
        ? await authApi.googleLink(googleLink.code, form.password)
        : await authApi.login(form.email, form.password)
      setTokens(data.access_token, data.refresh_token, data.user)
      toast.success(googleLink ? 'Google account linked. Welcome back!' : 'Welcome back!')
      navigate('/dashboard')
    } catch (err: unknown) {
      setFormError({
        title: googleLink ? "Couldn't link your account" : "Couldn't sign you in",
        message: getAuthErrorMessage(
          err,
          googleLink
            ? 'Something went wrong while linking your account. Please try again.'
            : 'Something went wrong while signing in. Please try again.',
        ),
      })
    } finally {
      setLoading(false)
    }
  }

  return (
    <AuthLayout
      eyebrow="Legal Research Platform"
      headline={['Legal research,', 'grounded in the law.']}
      description="Search judgments, retrieve the evidence that matters, and research with answers grounded in the cases you provide."
      steps={STEPS}
    >
      <AuthHeading
        eyebrow="Welcome back"
        title="Continue your research."
        description="Sign in to return to your legal research workspace."
      />

      {googleLink && (
        <div className="mb-6 rounded-md border border-[#E0D7C6] border-l-[3px] border-l-[#C8A951] bg-[#FBF8F1] px-4 py-3 text-sm leading-relaxed text-[#4A5468]">
          An account with <span className="font-medium text-legal-navy">{googleLink.email}</span> already
          exists. Enter its password once to link your Google account — afterwards you can sign in
          either way.
        </div>
      )}

      {formError && <FormAlert title={formError.title} message={formError.message} />}

      <form onSubmit={handleSubmit} noValidate className="space-y-5">
        <AuthField
          id="email"
          label="Email"
          type="email"
          autoComplete="email"
          inputMode="email"
          value={form.email}
          onChange={(e) => update('email', e.target.value)}
          placeholder="you@example.com"
          required
          readOnly={!!googleLink}
          error={fieldErrors.email}
        />

        <AuthField
          id="password"
          label="Password"
          type={showPass ? 'text' : 'password'}
          autoComplete="current-password"
          value={form.password}
          onChange={(e) => update('password', e.target.value)}
          placeholder="Enter your password"
          required
          error={fieldErrors.password}
          trailing={<PasswordToggle visible={showPass} onToggle={() => setShowPass(!showPass)} />}
        />

        <Button type="submit" size="lg" loading={loading} disabled={loading} className={AUTH_PRIMARY_BUTTON}>
          {loading ? (googleLink ? 'Linking account…' : 'Signing in…') : googleLink ? 'Link Google & Sign In' : 'Sign In'}
        </Button>
      </form>

      {googleLink ? (
        <button
          type="button"
          onClick={() => {
            setGoogleLink(null)
            setForm({ email: '', password: '' })
            setFieldErrors({})
            setFormError(null)
          }}
          className="mt-5 w-full rounded-md py-2 text-center text-sm text-muted-foreground transition-colors hover:text-legal-navy focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#C8A951]/60"
        >
          Cancel linking
        </button>
      ) : (
        <GoogleSignInSection />
      )}

      <p className="mt-10 border-t border-[#ECE6DA] pt-6 text-sm text-muted-foreground">
        Don't have an account?{' '}
        <Link
          to="/register"
          className="inline-block py-1.5 font-medium text-legal-navy underline decoration-[#C8A951] decoration-1 underline-offset-4 transition-colors hover:decoration-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#C8A951]/60 rounded-sm"
        >
          Create account
        </Link>
      </p>
    </AuthLayout>
  )
}
