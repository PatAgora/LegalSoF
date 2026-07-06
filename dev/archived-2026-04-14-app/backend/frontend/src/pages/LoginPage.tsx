import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuthStore } from '../stores/authStore'
import { api, setStoredTokens, SESSION_EXPIRED_KEY } from '../lib/api'
import { Button, Alert } from '../components/ui'

const inputCls =
  'w-full px-3 py-2 text-sm bg-white border border-zinc-300 rounded text-zinc-900 placeholder-zinc-400 focus:outline-none focus:ring-2 focus:ring-zinc-400 focus:border-transparent'

export default function LoginPage() {
  const navigate = useNavigate()
  const { login } = useAuthStore()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  // Set by authFetch when a token refresh fails mid-session.
  const [sessionExpired, setSessionExpired] = useState<boolean>(() => {
    try { return sessionStorage.getItem(SESSION_EXPIRED_KEY) === '1' } catch { return false }
  })

  // MFA second step - set when /auth/login answers with
  // { mfa_required: true, mfa_token } instead of tokens.
  const [mfaToken, setMfaToken] = useState<string | null>(null)
  const [mfaCode, setMfaCode] = useState('')
  const mfaInputRef = useRef<HTMLInputElement>(null)
  // Guards the auto-submit effect against double-firing.
  const mfaSubmittingRef = useRef(false)

  /** Store tokens, load the user, and enter the app - shared by both
   *  the plain-password path and the MFA path. */
  const completeLogin = async (response: { access_token: string; refresh_token: string }) => {
    setStoredTokens(response.access_token, response.refresh_token)
    const user = await api.getCurrentUser()
    login(response.access_token, response.refresh_token, user)
    try { sessionStorage.removeItem(SESSION_EXPIRED_KEY) } catch { /* */ }
    setSessionExpired(false)
    navigate('/')
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setLoading(true)

    try {
      const response = await api.login(email, password)
      if (response.mfa_required && response.mfa_token) {
        // Account has two-factor authentication - show the code step.
        setMfaToken(response.mfa_token)
        setMfaCode('')
        return
      }
      await completeLogin(response)
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Login failed. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  const handleMfaSubmit = async (codeArg?: string) => {
    const code = (codeArg ?? mfaCode).trim()
    if (!mfaToken || code.length !== 6 || loading) return
    setError('')
    setLoading(true)
    mfaSubmittingRef.current = true

    try {
      const response = await api.loginMfa(mfaToken, code)
      await completeLogin(response)
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Verification failed. Please try again.')
      setMfaCode('')
      mfaInputRef.current?.focus()
    } finally {
      setLoading(false)
      mfaSubmittingRef.current = false
    }
  }

  // Auto-submit once 6 digits are present (typed or pasted).
  useEffect(() => {
    if (mfaToken && mfaCode.length === 6 && !loading && !mfaSubmittingRef.current) {
      handleMfaSubmit(mfaCode)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mfaCode])

  const handleBackToLogin = () => {
    setMfaToken(null)
    setMfaCode('')
    setError('')
  }

  return (
    <div className="min-h-screen bg-slate-50 flex items-center justify-center p-4">
      <div className="w-full max-w-sm bg-white border border-zinc-200/80 rounded-md shadow-[0_1px_3px_0_rgb(0_0_0/0.04)] p-8">
        <div className="text-center mb-8">
          <div className="font-serif text-4xl font-medium text-zinc-900 mb-3">Agora</div>
          <p className="text-xs text-zinc-500 tracking-wide">Source of Funds Automation</p>
        </div>

        {mfaToken ? (
          /* ------------------------- MFA code step ------------------------ */
          <form
            onSubmit={(e) => { e.preventDefault(); handleMfaSubmit() }}
            className="space-y-5"
          >
            {error && (
              <Alert variant="error">{error}</Alert>
            )}

            <div>
              <label htmlFor="totp" className="block text-xs font-semibold text-zinc-700 mb-1.5">
                Verification code
              </label>
              <p className="text-xs text-zinc-500 mb-2">
                Enter the 6-digit code from your authenticator app.
              </p>
              <input
                id="totp"
                ref={mfaInputRef}
                type="text"
                inputMode="numeric"
                autoComplete="one-time-code"
                autoFocus
                required
                maxLength={6}
                value={mfaCode}
                onChange={(e) => setMfaCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
                className={`${inputCls} text-center text-lg tracking-[0.5em] font-mono`}
                placeholder="••••••"
                aria-label="6-digit verification code"
              />
            </div>

            <Button
              type="submit"
              variant="primary"
              size="md"
              loading={loading}
              disabled={mfaCode.length !== 6}
              className="w-full"
            >
              {loading ? 'Verifying…' : 'Verify'}
            </Button>

            <button
              type="button"
              onClick={handleBackToLogin}
              className="w-full text-center text-xs text-zinc-500 hover:text-zinc-900 transition-colors underline-offset-2 hover:underline"
            >
              Back to sign in
            </button>
          </form>
        ) : (
          /* ------------------------ Credentials step ---------------------- */
          <form onSubmit={handleSubmit} className="space-y-5">
            {sessionExpired && !error && (
              <Alert variant="info">Your session has expired — please sign in again.</Alert>
            )}
            {error && (
              <Alert variant="error">{error}</Alert>
            )}

            <div>
              <label htmlFor="email" className="block text-xs font-semibold text-zinc-700 mb-1.5">
                Email
              </label>
              <input
                id="email"
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className={inputCls}
                placeholder="you@example.com"
              />
            </div>

            <div>
              <label htmlFor="password" className="block text-xs font-semibold text-zinc-700 mb-1.5">
                Password
              </label>
              <input
                id="password"
                type="password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className={inputCls}
                placeholder="••••••••"
              />
            </div>

            <Button
              type="submit"
              variant="primary"
              size="md"
              loading={loading}
              className="w-full"
            >
              {loading ? 'Signing in…' : 'Sign in'}
            </Button>
          </form>
        )}

        <div className="mt-6 text-center text-xs text-zinc-400">
          Contact your administrator for credentials.
        </div>
      </div>
    </div>
  )
}
