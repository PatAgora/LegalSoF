import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuthStore } from '../stores/authStore'
import { api, setStoredTokens, SESSION_EXPIRED_KEY } from '../lib/api'
import { Button, Alert } from '../components/ui'

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

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setLoading(true)

    try {
      const response = await api.login(email, password)
      setStoredTokens(response.access_token, response.refresh_token)
      const user = await api.getCurrentUser()
      login(response.access_token, response.refresh_token, user)
      try { sessionStorage.removeItem(SESSION_EXPIRED_KEY) } catch { /* */ }
      setSessionExpired(false)
      navigate('/')
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Login failed. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-slate-50 flex items-center justify-center p-4">
      <div className="w-full max-w-sm bg-white border border-zinc-200/80 rounded-md shadow-[0_1px_3px_0_rgb(0_0_0/0.04)] p-8">
        <div className="text-center mb-8">
          <div className="font-serif text-4xl font-medium text-zinc-900 mb-3">Agora</div>
          <p className="text-xs text-zinc-500 tracking-wide">Source of Funds Automation</p>
        </div>

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
              className="w-full px-3 py-2 text-sm bg-white border border-zinc-300 rounded text-zinc-900 placeholder-zinc-400 focus:outline-none focus:ring-2 focus:ring-zinc-400 focus:border-transparent"
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
              className="w-full px-3 py-2 text-sm bg-white border border-zinc-300 rounded text-zinc-900 placeholder-zinc-400 focus:outline-none focus:ring-2 focus:ring-zinc-400 focus:border-transparent"
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

        <div className="mt-6 text-center text-xs text-zinc-400">
          Contact your administrator for credentials.
        </div>
      </div>
    </div>
  )
}
