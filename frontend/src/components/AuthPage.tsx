import { useState, type FormEvent } from 'react'
import {
  Activity,
  ArrowRight,
  Eye,
  EyeOff,
  LayoutDashboard,
  Monitor,
  ShieldCheck,
} from 'lucide-react'
import { Link, Navigate, useNavigate } from 'react-router-dom'
import { ApiError } from '../api/client'
import { useAuth } from '../auth/useAuth'

interface AuthPageProps {
  mode: 'login' | 'register'
}

export function AuthPage({ mode }: AuthPageProps) {
  const isRegister = mode === 'register'
  const { user, isLoading, signIn, signUp } = useAuth()
  const navigate = useNavigate()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)

  if (!isLoading && user) return <Navigate to="/" replace />

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError('')
    setSubmitting(true)
    try {
      if (isRegister) await signUp(email, password)
      else await signIn(email, password)
      navigate('/', { replace: true })
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : 'Something went wrong. Please try again.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <main className="auth-page">
      <section className="auth-panel">
        <Link className="brand auth-brand" to="/login" aria-label="DevPulse home">
          <span className="brand-mark"><Activity size={21} strokeWidth={2.5} /></span>
          <span>devpulse</span>
        </Link>
        <div className="auth-content">
          <div className="eyebrow"><span className="eyebrow-dot" /> INFRASTRUCTURE, IN FOCUS</div>
          <h1>{isRegister ? 'Build a clearer picture.' : 'Welcome back.'}</h1>
          <p className="auth-subtitle">
            {isRegister
              ? 'Create your workspace and bring every system into view.'
              : 'Sign in to see what’s happening across your infrastructure.'}
          </p>
          <form className="auth-form" onSubmit={handleSubmit}>
            {error && <div className="form-alert" role="alert">{error}</div>}
            <label htmlFor="email">Work email</label>
            <input
              id="email"
              type="email"
              autoComplete="email"
              placeholder="you@company.com"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              required
            />
            <label htmlFor="password">Password</label>
            <div className="password-field">
              <input
                id="password"
                type={showPassword ? 'text' : 'password'}
                autoComplete={isRegister ? 'new-password' : 'current-password'}
                placeholder={isRegister ? 'At least 12 characters' : 'Enter your password'}
                minLength={isRegister ? 12 : undefined}
                maxLength={128}
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                required
              />
              <button
                className="password-toggle"
                type="button"
                onClick={() => setShowPassword((visible) => !visible)}
                aria-label={showPassword ? 'Hide password' : 'Show password'}
              >
                {showPassword ? <EyeOff size={17} /> : <Eye size={17} />}
              </button>
            </div>
            <button className="button button-primary auth-submit" type="submit" disabled={submitting}>
              {submitting ? 'Please wait…' : isRegister ? 'Create workspace' : 'Sign in'}
              {!submitting && <ArrowRight size={17} />}
            </button>
          </form>
          <p className="auth-switch">
            {isRegister ? 'Already have an account?' : 'New to DevPulse?'}{' '}
            <Link to={isRegister ? '/login' : '/register'}>
              {isRegister ? 'Sign in' : 'Create an account'}
            </Link>
          </p>
          <div className="auth-security"><ShieldCheck size={16} /> Protected with encrypted authentication</div>
        </div>
        <footer className="auth-footer">© 2026 DevPulse · Infrastructure clarity</footer>
      </section>
      <aside className="auth-visual" aria-label="DevPulse monitoring overview">
        <div className="visual-orbit orbit-one" />
        <div className="visual-orbit orbit-two" />
        <div className="visual-content">
          <div className="visual-topline"><span>LIVE INFRASTRUCTURE SIGNAL</span><span className="live-tag"><i /> LIVE</span></div>
          <div className="flow-panel">
            <div className="flow-panel-title"><span>One signal. Full context.</span><span className="flow-lock"><ShieldCheck size={15} /> Encrypted</span></div>
            <div className="flow-steps">
              <div className="flow-step"><span className="flow-step-icon"><Monitor size={21} /></span><strong>Your hosts</strong><small>Lightweight agents</small></div>
              <span className="flow-connector"><i /><i /><i /></span>
              <div className="flow-step flow-step-center"><span className="flow-step-icon"><Activity size={21} /></span><strong>DevPulse</strong><small>Live telemetry</small></div>
              <span className="flow-connector"><i /><i /><i /></span>
              <div className="flow-step"><span className="flow-step-icon"><LayoutDashboard size={21} /></span><strong>Your view</strong><small>One clear picture</small></div>
            </div>
            <div className="flow-bottom-note"><span className="flow-pulse" /> Metrics are streamed securely from your infrastructure</div>
          </div>
          <div className="visual-stats">
            <div><span className="visual-stat-icon green"><Activity size={17} /></span><span><strong>Real-time visibility</strong><small>Every metric, one workspace</small></span></div>
            <div><span className="visual-stat-icon purple"><ShieldCheck size={17} /></span><span><strong>Secure by design</strong><small>Your infrastructure stays yours</small></span></div>
          </div>
        </div>
        <div className="visual-caption">Know sooner. Respond smarter.</div>
      </aside>
    </main>
  )
}
