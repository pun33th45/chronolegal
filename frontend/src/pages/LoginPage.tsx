import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import { BookOpen, Eye, EyeOff, FileText, Scale, Search } from 'lucide-react'
import { useAuthStore } from '@/store/authStore'
import { authApi } from '@/services/api'
import { Button } from '@/components/ui/Button'
import toast from 'react-hot-toast'

// FastAPI returns `detail` as a plain string for most errors (e.g. "Incorrect
// email or password"), but as an array of Pydantic error objects for request
// validation failures (422) — rendering that array directly as a toast
// message fails silently/unreadably, so normalize both shapes to one string.
function extractErrorMessage(err: unknown, fallback: string): string {
  const detail = (err as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail) && detail.length > 0) {
    const first = detail[0] as { msg?: unknown }
    if (typeof first?.msg === 'string') return first.msg
  }
  return fallback
}

const PIPELINE = [
  { icon: FileText, label: 'Judgment' },
  { icon: BookOpen, label: 'Knowledge Base' },
  { icon: Search, label: 'Retrieved Evidence' },
  { icon: Scale, label: 'Grounded Answer' },
]

export default function LoginPage() {
  const navigate = useNavigate()
  const { setTokens } = useAuthStore()
  const [form, setForm] = useState({ email: '', password: '' })
  const [showPass, setShowPass] = useState(false)
  const [loading, setLoading] = useState(false)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setLoading(true)
    try {
      const data = await authApi.login(form.email, form.password)
      setTokens(data.access_token, data.refresh_token, data.user)
      toast.success('Welcome back!')
      navigate('/dashboard')
    } catch (err: unknown) {
      toast.error(extractErrorMessage(err, 'Login failed'))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex bg-background">
      {/* Brand panel */}
      <div className="hidden lg:flex lg:w-[45%] bg-legal-gradient flex-col justify-between p-12 relative overflow-hidden">
        <div className="relative z-10">
          {/* The logo's navy/gold wordmark is designed for a light surface —
              "Chrono" would nearly disappear directly on this dark gradient,
              so it gets its own small light backing rather than being
              recolored or filtered. */}
          <div className="inline-block bg-white rounded-lg px-3 py-2">
            <img
              src="/chronolegal-logo.png"
              alt="ChronoLegal — Legal Research Platform"
              className="h-7 w-auto object-contain"
            />
          </div>
        </div>

        <div className="relative z-10 space-y-10">
          <p className="text-white/85 text-xl font-serif leading-relaxed max-w-sm">
            AI-assisted legal research grounded in your indexed case law.
          </p>

          {/* Pipeline visual */}
          <div className="space-y-0">
            {PIPELINE.map((step, i) => (
              <div key={step.label} className="flex items-center gap-3">
                <div className="flex flex-col items-center">
                  <div className="w-8 h-8 rounded-lg bg-white/10 border border-white/15 flex items-center justify-center flex-shrink-0">
                    <step.icon className="w-3.5 h-3.5 text-white/90" />
                  </div>
                  {i < PIPELINE.length - 1 && <div className="w-px h-5 bg-white/15 my-0.5" />}
                </div>
                <p className="text-sm text-white/75 pb-5">{step.label}</p>
              </div>
            ))}
          </div>
        </div>

        <p className="relative z-10 text-white/40 text-xs uppercase tracking-wider">
          AI-powered legal research
        </p>
      </div>

      {/* Form panel */}
      <div className="flex-1 flex items-center justify-center p-6 sm:p-8">
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.3 }}
          className="w-full max-w-[380px]"
        >
          {/* Mobile-only brand mark — this sits on the light form panel
              background, so the logo's own colors work directly. */}
          <img
            src="/chronolegal-logo.png"
            alt="ChronoLegal — Legal Research Platform"
            className="lg:hidden h-8 w-auto object-contain mb-8"
          />

          <div className="mb-7">
            <h1 className="font-serif text-2xl font-bold text-foreground mb-1.5">Welcome back</h1>
            <p className="text-muted-foreground text-sm">Sign in to continue your legal research.</p>
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-foreground/90 mb-1.5">
                Email
              </label>
              <input
                type="email"
                value={form.email}
                onChange={(e) => setForm({ ...form, email: e.target.value })}
                placeholder="you@example.com"
                required
                className="w-full h-11 px-3.5 bg-card border border-input rounded-lg text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary/40 focus:border-primary transition-colors"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-foreground/90 mb-1.5">
                Password
              </label>
              <div className="relative">
                <input
                  type={showPass ? 'text' : 'password'}
                  value={form.password}
                  onChange={(e) => setForm({ ...form, password: e.target.value })}
                  placeholder="••••••••"
                  required
                  className="w-full h-11 px-3.5 pr-10 bg-card border border-input rounded-lg text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary/40 focus:border-primary transition-colors"
                />
                <button
                  type="button"
                  onClick={() => setShowPass(!showPass)}
                  aria-label={showPass ? 'Hide password' : 'Show password'}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground transition-colors"
                >
                  {showPass ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
            </div>

            <Button type="submit" size="lg" loading={loading} className="w-full mt-1">
              {loading ? 'Signing in...' : 'Sign In'}
            </Button>
          </form>

          <p className="mt-6 text-center text-sm text-muted-foreground">
            Don't have an account?{' '}
            <Link to="/register" className="text-primary font-medium hover:underline">
              Create account
            </Link>
          </p>
        </motion.div>
      </div>
    </div>
  )
}
