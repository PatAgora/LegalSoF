// Resolve the API base URL.
//
// Production (single-service deploy): backend serves the frontend bundle, so
// the API lives at the SAME origin as the page - base URL must be empty so
// fetch('/api/v1/...') stays on this host.
//
// We deliberately ignore VITE_API_BASE_URL when running on a *.railway.app
// host. A previous build accidentally baked a stale separate-backend URL into
// the bundle, and env-var changes only take effect on the next rebuild -
// this guard makes the running bundle robust regardless of what was baked.
//
// Local dev still honours VITE_API_BASE_URL if you point the frontend at a
// detached backend.
function resolveApiBase(): string {
  if (typeof window !== 'undefined' && window.location?.hostname) {
    const host = window.location.hostname
    if (host.endsWith('.railway.app') || host.endsWith('.up.railway.app')) {
      return ''
    }
  }
  const envUrl = import.meta.env.VITE_API_BASE_URL
  return (envUrl && typeof envUrl === 'string') ? envUrl : ''
}

export const API_BASE_URL = resolveApiBase()

// ---------------------------------------------------------------------------
// Token storage - the single place tokens are read and written.
// The legacy localStorage keys remain the source of truth so existing
// reads keep working; the auth store no longer duplicates the tokens.
// ---------------------------------------------------------------------------

const ACCESS_TOKEN_KEY = 'access_token'
const REFRESH_TOKEN_KEY = 'refresh_token'
export const SESSION_EXPIRED_KEY = 'session_expired'

export function getAccessToken(): string | null {
  return localStorage.getItem(ACCESS_TOKEN_KEY)
}

export function getRefreshToken(): string | null {
  return localStorage.getItem(REFRESH_TOKEN_KEY)
}

export function setStoredTokens(accessToken: string, refreshToken?: string | null) {
  localStorage.setItem(ACCESS_TOKEN_KEY, accessToken)
  if (refreshToken) localStorage.setItem(REFRESH_TOKEN_KEY, refreshToken)
}

export function clearStoredTokens() {
  localStorage.removeItem(ACCESS_TOKEN_KEY)
  localStorage.removeItem(REFRESH_TOKEN_KEY)
}

// ---------------------------------------------------------------------------
// Token refresh - single-flight so concurrent 401s trigger ONE refresh.
// ---------------------------------------------------------------------------

let refreshInFlight: Promise<boolean> | null = null

/** Attempt to rotate the token pair. Resolves true on success. */
export function refreshTokens(): Promise<boolean> {
  if (!refreshInFlight) {
    refreshInFlight = (async (): Promise<boolean> => {
      const refreshToken = getRefreshToken()
      if (!refreshToken) return false
      try {
        const r = await fetch(`${API_BASE_URL}/api/v1/auth/refresh`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ refresh_token: refreshToken }),
        })
        if (!r.ok) return false
        const data = await r.json().catch(() => null)
        if (!data?.access_token) return false
        setStoredTokens(data.access_token, data.refresh_token || refreshToken)
        return true
      } catch {
        return false
      }
    })().finally(() => {
      refreshInFlight = null
    })
  }
  return refreshInFlight
}

/** Clear auth state, flag the reason, and send the user to the login page. */
function handleSessionExpired() {
  clearStoredTokens()
  localStorage.removeItem('auth-storage')
  try { sessionStorage.setItem(SESSION_EXPIRED_KEY, '1') } catch { /* private mode */ }
  if (window.location.pathname !== '/login') {
    window.location.href = '/login'
  }
}

export function getAuthHeaders(extra?: Record<string, string>): Record<string, string> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...extra,
  }
  const token = getAccessToken()
  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }
  return headers
}

interface AuthFetchConfig {
  // When true, a 401 is returned to the caller untouched - no refresh
  // attempt, no redirect. Used by background polls (notifications,
  // module config) so they never eject a user mid-typing; the next
  // user-initiated request takes the refresh/redirect path instead.
  silentAuthFailure?: boolean
}

function buildRequest(url: string, options?: RequestInit): Promise<Response> {
  const token = getAccessToken()
  const headers = new Headers(options?.headers)
  if (token) {
    headers.set('Authorization', `Bearer ${token}`)
  }
  if (!headers.has('Content-Type') && options?.body && typeof options.body === 'string') {
    headers.set('Content-Type', 'application/json')
  }
  return fetch(url, { ...options, headers })
}

/**
 * Fetch wrapper that adds auth headers and transparently refreshes an
 * expired access token: on 401 it attempts one token refresh (deduped
 * across concurrent calls) and retries the original request once. If
 * the refresh fails the session is treated as expired and the user is
 * redirected to the login page with an explanatory message.
 */
export async function authFetch(
  url: string,
  options?: RequestInit,
  config?: AuthFetchConfig,
): Promise<Response> {
  const response = await buildRequest(url, options)
  if (response.status !== 401) return response

  if (config?.silentAuthFailure) return response

  const refreshed = await refreshTokens()
  if (refreshed) {
    const retried = await buildRequest(url, options)
    if (retried.status !== 401) return retried
  }

  handleSessionExpired()
  return response
}

class ApiClient {
  async login(email: string, password: string) {
    const response = await fetch(`${API_BASE_URL}/api/v1/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password }),
    })
    if (!response.ok) {
      const data = await response.json().catch(() => ({}))
      throw { response: { data } }
    }
    return response.json()
  }

  /**
   * Complete an MFA-pending login. `mfaToken` is the short-lived token
   * returned by /auth/login when the account has MFA enabled
   * ({ mfa_required: true, mfa_token }); on success the backend returns
   * the same Token shape as a normal login.
   */
  async loginMfa(mfaToken: string, totpCode: string) {
    const response = await fetch(`${API_BASE_URL}/api/v1/auth/login/mfa`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ mfa_token: mfaToken, totp_code: totpCode }),
    })
    if (!response.ok) {
      const data = await response.json().catch(() => ({}))
      throw { response: { data } }
    }
    return response.json()
  }

  async logout() {
    // Best-effort server-side logout; local state is cleared regardless.
    try {
      await authFetch(`${API_BASE_URL}/api/v1/auth/logout`, { method: 'POST' }, { silentAuthFailure: true })
    } catch { /* non-blocking */ }
  }

  async getCurrentUser() {
    const response = await authFetch(`${API_BASE_URL}/api/v1/auth/me`)
    if (!response.ok) {
      throw new Error('Failed to get current user')
    }
    return response.json()
  }
}

export const api = new ApiClient()
