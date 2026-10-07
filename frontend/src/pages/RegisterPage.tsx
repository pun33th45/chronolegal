import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import { BookOpen, Eye, EyeOff, FileText, Scale, Search } from 'lucide-react'
import { useAuthStore } from '@/store/authStore'
import { authApi } from '@/services/api'
import { Button } from '@/components/ui/Button'
import { GoogleSignInSection } from '@/components/auth/GoogleSignIn'
import { getAuthErrorMessage } from '@/lib/authErrors'
import toast from 'react-hot-toast'

const PIPELINE = [
  { icon: FileText, label: 'Judgment' },
  { icon: BookOpen, label: 'Knowledge Base' },
  { icon: Search, label: 'Retrieved Evidence' },
  { icon: Scale, label: 'Grounded Answer' },
]

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

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (loading) return
    setLoading(true)
    try {
      await authApi.register(form)
      const data = await authApi.login(form.email, form.password)
      setTokens(data.access_token, data.refresh_token, data.user)
      toast.success('Account created! Welcome to ChronoLegal.')
      navigate('/dashboard')
    } catch (err: unknown) {
      toast.error(
        getAuthErrorMessage(err, 'Something went wrong while creating your account. Please try again.'),
      )
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex bg-background">
      {/* Brand panel */}
      <div className="hidden lg:flex lg:w-[45%] bg-legal-gradient flex-col justify-between p-12 relative overflow-hidden">
        <div className="relative z-10">
          {/* Same light-backing treatment as Login — the logo's navy/gold
              wordmark needs a light surface, not this dark gradient. */}
          <div className="inline-block bg-white rounded-lg px-3 py-2">
            <img
              src="/chronolegal-logo.png"
              alt="ChronoLegal — Legal Research Platform"
              className="h-7 w-auto object-contain"
            />
          </div>
        </div>

        <div className="relative z-10 space-y-10">
          <div className="max-w-sm">
            <h2 className="text-2xl font-serif font-bold text-white mb-3 leading-snug">
              Start your legal research journey
            </h2>
            <p className="text-white/70 text-sm leading-relaxed">
              Access landmark Indian legal judgments. Ask questions in plain English and get
              grounded answers with citations.
            </p>
          </div>

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
          <img
            src="/chronolegal-logo.png"
            alt="ChronoLegal — Legal Research Platform"
            className="lg:hidden h-8 w-auto object-contain mb-8"
          />

          <div className="mb-7">
            <h1 className="font-serif text-2xl font-bold text-foreground mb-1.5">Create account</h1>
            <p className="text-muted-foreground text-sm">Join ChronoLegal for free.</p>
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="grid grid-cols-2 gap-3.5">
              <div>
                <label htmlFor="full_name" className="block text-sm font-medium text-foreground/90 mb-1.5">
                  Full Name
                </label>
                <input
                  id="full_name"
                  type="text"
                  autoComplete="name"
                  value={form.full_name}
                  onChange={(e) => setForm({ ...form, full_name: e.target.value })}
                  placeholder="John Doe"
                  className="w-full h-11 px-3.5 bg-card border border-input rounded-lg text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary/40 focus:border-primary transition-colors"
                />
              </div>
              <div>
                <label htmlFor="username" className="block text-sm font-medium text-foreground/90 mb-1.5">
                  Username
                </label>
                <input
                  id="username"
                  type="text"
                  autoComplete="username"
                  value={form.username}
                  onChange={(e) => setForm({ ...form, username: e.target.value })}
                  placeholder="johndoe"
                  required
                  minLength={3}
                  pattern="[a-zA-Z0-9_\-]+"
                  aria-describedby="username-help"
                  className="w-full h-11 px-3.5 bg-card border border-input rounded-lg text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary/40 focus:border-primary transition-colors"
                />
              </div>
            </div>
            <p id="username-help" className="-mt-2.5 text-xs text-muted-foreground">
              Letters, numbers, underscores and hyphens only.
            </p>

            <div>
              <label htmlFor="email" className="block text-sm font-medium text-foreground/90 mb-1.5">
                Email
              </label>
              <input
                id="email"
                type="email"
                autoComplete="email"
                value={form.email}
                onChange={(e) => setForm({ ...form, email: e.target.value })}
                placeholder="you@example.com"
                required
                className="w-full h-11 px-3.5 bg-card border border-input rounded-lg text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary/40 focus:border-primary transition-colors"
              />
            </div>

            <div>
              <label htmlFor="password" className="block text-sm font-medium text-foreground/90 mb-1.5">
                Password
              </label>
              <div className="relative">
                <input
                  id="password"
                  type={showPass ? 'text' : 'password'}
                  autoComplete="new-password"
                  value={form.password}
                  onChange={(e) => setForm({ ...form, password: e.target.value })}
                  placeholder="••••••••"
                  required
                  minLength={8}
                  aria-describedby="password-help"
                  className="w-full h-11 px-3.5 pr-10 bg-card border border-input rounded-lg text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary/40 focus:border-primary transition-colors"
                />
                <button
                  type="button"
                  onClick={() => setShowPass(!showPass)}
                  aria-label={showPass ? 'Hide password' : 'Show password'}
                  aria-pressed={showPass}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground transition-colors"
                >
                  {showPass ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
              <p id="password-help" className="mt-1.5 text-xs text-muted-foreground">
                At least 8 characters, with one uppercase letter and one number.
              </p>
            </div>

            <Button type="submit" size="lg" loading={loading} disabled={loading} className="w-full mt-1">
              {loading ? 'Creating account…' : 'Create Account'}
            </Button>
          </form>

          <GoogleSignInSection />

          <p className="mt-6 text-center text-sm text-muted-foreground">
            Already have an account?{' '}
            <Link to="/login" className="text-primary font-medium hover:underline">
              Sign in
            </Link>
          </p>
        </motion.div>
      </div>
    </div>
  )
}
