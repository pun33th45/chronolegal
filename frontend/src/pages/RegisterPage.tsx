import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuthStore } from '@/store/authStore'
import { authApi } from '@/services/api'
import { Button } from '@/components/ui/Button'
import { GoogleSignInSection } from '@/components/auth/GoogleSignIn'
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
  { label: 'Upload', detail: 'Add your judgments' },
  { label: 'Understand', detail: 'Parties, courts, dates' },
  { label: 'Index', detail: 'Searchable passages' },
  { label: 'Research', detail: 'Grounded answers' },
]

const FIELD_MESSAGES: FieldMessages = {
  username: {
    valueMissing: 'Choose a username.',
    tooShort: 'Username must be at least 3 characters.',
    patternMismatch: 'Use only letters, numbers, underscores and hyphens.',
  },
  email: {
    valueMissing: 'Enter your email address.',
    typeMismatch: 'Enter a valid email address, like name@example.com.',
  },
  password: {
    valueMissing: 'Create a password.',
    tooShort: 'Password must be at least 8 characters.',
  },
}

type Field = 'email' | 'username' | 'full_name' | 'password'

export default function RegisterPage() {
  const navigate = useNavigate()
  const { setTokens } = useAuthStore()
  const [form, setForm] = useState({
    email: '',
    username: '',
    full_name: '',
    password: '',
  })
  const [showPass, setShowPass] = useState(false)
  const [loading, setLoading] = useState(false)
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({})
  const [formError, setFormError] = useState<string | null>(null)

  function update(field: Field, value: string) {
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
      await authApi.register(form)
      const data = await authApi.login(form.email, form.password)
      setTokens(data.access_token, data.refresh_token, data.user)
      toast.success('Account created! Welcome to ChronoLegal.')
      navigate('/dashboard')
    } catch (err: unknown) {
      setFormError(
        getAuthErrorMessage(err, 'Something went wrong while creating your account. Please try again.'),
      )
    } finally {
      setLoading(false)
    }
  }

  return (
    <AuthLayout
      eyebrow="Your Case Corpus"
      headline={['Build your legal', 'research corpus.']}
      description="Upload judgments, build a searchable knowledge base, and investigate cases with grounded answers."
      steps={STEPS}
    >
      <AuthHeading
        eyebrow="Get started"
        title="Build your research workspace."
        description="Create your ChronoLegal account and start researching from your own case corpus."
      />

      {formError && <FormAlert title="Couldn't create your account" message={formError} />}

      <form onSubmit={handleSubmit} noValidate className="space-y-5">
        <AuthField
          id="full_name"
          label="Full Name"
          type="text"
          autoComplete="name"
          value={form.full_name}
          onChange={(e) => update('full_name', e.target.value)}
          placeholder="Your full name"
        />

        <AuthField
          id="username"
          label="Username"
          type="text"
          autoComplete="username"
          autoCapitalize="none"
          spellCheck={false}
          value={form.username}
          onChange={(e) => update('username', e.target.value)}
          placeholder="e.g. a_sharma"
          required
          minLength={3}
          pattern="[a-zA-Z0-9_\-]+"
          hint="Letters, numbers, underscores and hyphens only."
          error={fieldErrors.username}
        />

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
          error={fieldErrors.email}
        />

        <AuthField
          id="password"
          label="Password"
          type={showPass ? 'text' : 'password'}
          autoComplete="new-password"
          value={form.password}
          onChange={(e) => update('password', e.target.value)}
          placeholder="Create a password"
          required
          minLength={8}
          hint="At least 8 characters, with one uppercase letter and one number."
          error={fieldErrors.password}
          trailing={<PasswordToggle visible={showPass} onToggle={() => setShowPass(!showPass)} />}
        />

        <Button type="submit" size="lg" loading={loading} disabled={loading} className={AUTH_PRIMARY_BUTTON}>
          {loading ? 'Creating account…' : 'Create Account'}
        </Button>
      </form>

      <GoogleSignInSection />

      <p className="mt-10 border-t border-[#ECE6DA] pt-6 text-sm text-muted-foreground">
        Already have an account?{' '}
        <Link
          to="/login"
          className="inline-block py-1.5 font-medium text-legal-navy underline decoration-[#C8A951] decoration-1 underline-offset-4 transition-colors hover:decoration-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#C8A951]/60 rounded-sm"
        >
          Sign in
        </Link>
      </p>
    </AuthLayout>
  )
}
